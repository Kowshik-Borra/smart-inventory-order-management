"""
Database Connector, Connection Pool, and Query Utilities for SIOM.
Uses parameterized queries, connection pooling, transaction managers, logging, and secure hashing.
"""

import os
import re
import logging
import hashlib
import binascii
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple, Union
import mysql.connector
from mysql.connector import pooling, Error
from dotenv import load_dotenv
import streamlit as st

# Configure logging for database operations
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("siom.database")

# Load environment variables
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD")
if DB_PASSWORD is None:
    raise ValueError("Database password not configured. Please set DB_PASSWORD in your environment or .env file.")
DB_NAME = os.getenv("DB_NAME", "smart_inventory_db")

# Optional bcrypt support with secure PBKDF2 fallback
try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False

_connection_pool = None

# ==============================================================================
# Workflow Status Transition Definitions
# ==============================================================================

SALES_ORDER_TRANSITIONS = {
    "Draft": ["Confirmed", "Cancelled"],
    "Confirmed": ["Processing", "Cancelled"],
    "Processing": ["Shipped", "Cancelled"],
    "Shipped": ["Delivered"],
    "Delivered": [],
    "Cancelled": [],
}

PURCHASE_ORDER_TRANSITIONS = {
    "Draft": ["Ordered", "Cancelled"],
    "Ordered": ["Partially Received", "Received", "Cancelled"],
    "Partially Received": ["Received"],
    "Received": [],
    "Cancelled": [],
}


def is_valid_sales_order_transition(current_status: str, new_status: str) -> bool:
    """Checks if a sales order status transition is allowed."""
    if current_status == new_status:
        return True
    return new_status in SALES_ORDER_TRANSITIONS.get(current_status, [])


def is_valid_purchase_order_transition(current_status: str, new_status: str) -> bool:
    """Checks if a purchase order status transition is allowed."""
    if current_status == new_status:
        return True
    return new_status in PURCHASE_ORDER_TRANSITIONS.get(current_status, [])


def get_connection_config() -> Dict[str, Any]:
    """Returns database connection parameters dictionary."""
    return {
        "host": DB_HOST,
        "port": DB_PORT,
        "user": DB_USER,
        "password": DB_PASSWORD,
        "database": DB_NAME,
        "charset": "utf8mb4",
        "collation": "utf8mb4_unicode_ci",
        "autocommit": True,
    }


def init_db_pool(pool_size: int = 5) -> Optional[pooling.MySQLConnectionPool]:
    """Initializes the MySQL connection pool with logging."""
    global _connection_pool
    try:
        ensure_database_exists()
        _connection_pool = pooling.MySQLConnectionPool(
            pool_name="siom_pool",
            pool_size=pool_size,
            pool_reset_session=True,
            **get_connection_config()
        )
        logger.info("MySQL connection pool initialized successfully.")
        apply_migrations()
        return _connection_pool
    except Error as e:
        logger.error(f"Failed to initialize MySQL connection pool: {e}")
        return None


def apply_migrations() -> bool:
    """
    Safely applies database schema migrations idempotently.
    Verifies stock_movements columns and creates document_sequences table.
    """
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(**get_connection_config())
        cursor = conn.cursor(dictionary=True)

        # 1. Ensure document_sequences table exists
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS document_sequences (
                seq_name VARCHAR(50) NOT NULL PRIMARY KEY,
                next_val INT NOT NULL DEFAULT 0,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB;
            """
        )

        # 2. Check if stock_movements table exists in current database
        cursor.execute(
            """
            SELECT TABLE_NAME FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'stock_movements'
            """,
            (DB_NAME,)
        )
        if not cursor.fetchone():
            logger.info("Table 'stock_movements' not found in schema. Skipping column check.")
            clear_query_cache()
            return True

        # 3. Check existing columns in stock_movements
        cursor.execute(
            """
            SELECT COLUMN_NAME FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'stock_movements'
            """,
            (DB_NAME,)
        )
        existing_cols = {row["COLUMN_NAME"].lower() for row in cursor.fetchall()}

        if "created_by_admin_id" not in existing_cols:
            if "created_by" in existing_cols:
                logger.info("Detected legacy column 'created_by' in 'stock_movements'. Migrating to 'created_by_admin_id'...")
                cursor.execute("ALTER TABLE stock_movements CHANGE created_by created_by_admin_id INT NULL")
                logger.info("Successfully executed: ALTER TABLE stock_movements CHANGE created_by created_by_admin_id INT NULL")
            else:
                logger.info("Column 'created_by_admin_id' missing in 'stock_movements'. Adding column...")
                if "notes" in existing_cols:
                    cursor.execute("ALTER TABLE stock_movements ADD COLUMN created_by_admin_id INT NULL AFTER notes")
                else:
                    cursor.execute("ALTER TABLE stock_movements ADD COLUMN created_by_admin_id INT NULL")
                logger.info("Successfully executed: ALTER TABLE stock_movements ADD COLUMN created_by_admin_id INT NULL AFTER notes")
        else:
            logger.info("Column 'created_by_admin_id' is already correctly defined in 'stock_movements'.")

        # 4. Check and ensure Foreign Key constraint on created_by_admin_id -> admins(id)
        cursor.execute(
            """
            SELECT CONSTRAINT_NAME 
            FROM information_schema.KEY_COLUMN_USAGE 
            WHERE TABLE_SCHEMA = %s 
              AND TABLE_NAME = 'stock_movements' 
              AND COLUMN_NAME = 'created_by_admin_id' 
              AND REFERENCED_TABLE_NAME = 'admins'
            """,
            (DB_NAME,)
        )
        fk_exists = cursor.fetchone()

        if not fk_exists:
            logger.info("Foreign key for 'created_by_admin_id' not found. Adding fk_sm_admin constraint...")
            try:
                cursor.execute(
                    """
                    ALTER TABLE stock_movements 
                    ADD CONSTRAINT fk_sm_admin 
                    FOREIGN KEY (created_by_admin_id) REFERENCES admins(id) 
                    ON UPDATE CASCADE ON DELETE SET NULL
                    """
                )
                logger.info("Successfully added constraint 'fk_sm_admin' to 'stock_movements'.")
            except Error as fk_err:
                logger.warning(f"Note on foreign key creation for 'stock_movements': {fk_err}")
        else:
            logger.info(f"Foreign key constraint '{fk_exists['CONSTRAINT_NAME']}' on 'created_by_admin_id' is already present.")

        # 5. Check and migrate categories table for 'shortcut' column & unique constraint
        cursor.execute(
            """
            SELECT TABLE_NAME FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'categories'
            """,
            (DB_NAME,)
        )
        if cursor.fetchone():
            cursor.execute(
                """
                SELECT COLUMN_NAME FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'categories'
                """,
                (DB_NAME,)
            )
            cat_cols = {row["COLUMN_NAME"].lower() for row in cursor.fetchall()}
            if "shortcut" not in cat_cols:
                logger.info("Column 'shortcut' missing in 'categories'. Adding column...")
                cursor.execute("ALTER TABLE categories ADD COLUMN shortcut VARCHAR(10) NULL AFTER name")
                logger.info("Successfully executed: ALTER TABLE categories ADD COLUMN shortcut VARCHAR(10) NULL AFTER name")

            # Backfill any category lacking a shortcut
            DEFAULT_SHORTCUTS = {
                "Computer Systems & Laptops": "COMP",
                "Computer Accessories": "ACC",
                "Mobile & Tablet Accessories": "MOB",
                "Office Equipment": "OFF",
                "Workstation & Furniture": "FURN",
                "Networking Hardware": "NET",
                "Data Storage & Memory": "STOR",
                "Printers & Consumables": "PRNT",
                "Audio & Visual Equipment": "AV",
                "Cables & Adapters": "CAB",
                "Power Protection & UPS": "PWR",
                "Industrial Automation": "IND",
            }
            cursor.execute("SELECT id, name, shortcut FROM categories")
            all_cats = cursor.fetchall()
            cursor.execute("SELECT DISTINCT shortcut FROM categories WHERE shortcut IS NOT NULL AND shortcut != ''")
            used_shortcuts = {r["shortcut"].upper() for r in cursor.fetchall() if r.get("shortcut")}

            for c in all_cats:
                if not c.get("shortcut"):
                    cname = c["name"]
                    cand = DEFAULT_SHORTCUTS.get(cname)
                    if not cand or cand in used_shortcuts:
                        words = [w for w in re.findall(r"[A-Za-z0-9]+", cname) if w]
                        if len(words) >= 3:
                            cand = "".join(w[0] for w in words[:3]).upper()
                        elif len(words) == 2:
                            cand = (words[0][:2] + words[1][:2]).upper()
                        elif words:
                            cand = words[0][:3].upper()
                        else:
                            cand = "CAT"
                        idx = 1
                        base = cand
                        while cand in used_shortcuts:
                            cand = f"{base[:3]}{idx}"
                            idx += 1
                    used_shortcuts.add(cand)
                    cursor.execute("UPDATE categories SET shortcut = %s WHERE id = %s", (cand, c["id"]))
                    logger.info(f"Backfilled shortcut '{cand}' for category '{cname}'.")

            # Ensure UNIQUE constraint and NOT NULL on shortcut
            cursor.execute(
                """
                SELECT CONSTRAINT_NAME FROM information_schema.TABLE_CONSTRAINTS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'categories'
                  AND CONSTRAINT_TYPE = 'UNIQUE' AND CONSTRAINT_NAME = 'uq_category_shortcut'
                """,
                (DB_NAME,)
            )
            if not cursor.fetchone():
                try:
                    cursor.execute("ALTER TABLE categories MODIFY COLUMN shortcut VARCHAR(10) NOT NULL")
                    cursor.execute("ALTER TABLE categories ADD CONSTRAINT uq_category_shortcut UNIQUE (shortcut)")
                    logger.info("Successfully added UNIQUE constraint 'uq_category_shortcut' on categories(shortcut).")
                except Error as err:
                    logger.warning(f"Note on unique constraint for category shortcut: {err}")

            # Initialize document_sequences for each category if not present
            for c in all_cats:
                seq_name = f"PROD_CAT_{c['id']}"
                cursor.execute("SELECT next_val FROM document_sequences WHERE seq_name = %s", (seq_name,))
                if not cursor.fetchone():
                    cursor.execute("SELECT sku FROM products WHERE category_id = %s", (c["id"],))
                    skus = cursor.fetchall()
                    max_num = 0
                    for s in skus:
                        digits = re.findall(r"\d+", s.get("sku") or "")
                        if digits:
                            max_num = max(max_num, int(digits[-1]))
                    cursor.execute("INSERT INTO document_sequences (seq_name, next_val) VALUES (%s, %s)", (seq_name, max_num))
                    logger.info(f"Initialized sequence '{seq_name}' with next_val={max_num}.")

        clear_query_cache()
        return True
    except Exception as e:
        logger.error(f"Error applying database migrations: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()



def ensure_database_exists() -> bool:
    """Creates the database if it doesn't exist."""
    try:
        raw_conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            autocommit=True
        )
        cursor = raw_conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cursor.close()
        raw_conn.close()
        logger.info(f"Verified database `{DB_NAME}` exists.")
        return True
    except Error as err:
        logger.error(f"Error ensuring database exists: {err}")
        return False


def get_connection():
    """Gets a connection from the pool or creates a standalone connection."""
    global _connection_pool
    try:
        if _connection_pool is None:
            init_db_pool()
        if _connection_pool:
            return _connection_pool.get_connection()
        return mysql.connector.connect(**get_connection_config())
    except Error as e:
        logger.warning(f"Connection pool acquisition failed ({e}), falling back to direct connection.")
        return mysql.connector.connect(**get_connection_config())


def clear_query_cache():
    """Clears Streamlit cache after database mutations."""
    try:
        st.cache_data.clear()
    except Exception:
        pass


@contextmanager
def get_db_cursor(commit: bool = True, dictionary: bool = True):
    """Context manager for obtaining a database cursor with automatic cleanup and logging."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=dictionary)
    try:
        yield cursor
        if commit:
            conn.commit()
    except Exception as e:
        logger.error(f"Database error during cursor execution: {e}")
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()


@contextmanager
def get_db_transaction(dictionary: bool = True):
    """
    Context manager for atomic multi-statement operations.
    Rolls back automatically on error and clears cache on commit.
    """
    conn = get_connection()
    conn.autocommit = False
    cursor = conn.cursor(dictionary=dictionary)
    try:
        yield cursor, conn
        conn.commit()
        clear_query_cache()
    except Exception as e:
        logger.error(f"Transaction aborted and rolled back: {e}")
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()


def execute_query(query: str, params: Optional[Union[Tuple, Dict, List]] = None) -> List[Dict[str, Any]]:
    """Executes a SELECT query with parameters and returns a list of dictionaries."""
    with get_db_cursor(commit=False, dictionary=True) as cursor:
        cursor.execute(query, params or ())
        return cursor.fetchall()


@st.cache_data(ttl=45, show_spinner=False)
def execute_cached_query(query: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
    """Executes a cached read-only query with short TTL (45s)."""
    return execute_query(query, params)


def execute_one(query: str, params: Optional[Union[Tuple, Dict, List]] = None) -> Optional[Dict[str, Any]]:
    """Executes a SELECT query and returns the first record or None."""
    with get_db_cursor(commit=False, dictionary=True) as cursor:
        cursor.execute(query, params or ())
        return cursor.fetchone()


def execute_update(query: str, params: Optional[Union[Tuple, Dict, List]] = None) -> int:
    """Executes an UPDATE, DELETE, or INSERT statement and clears cache."""
    with get_db_cursor(commit=True, dictionary=False) as cursor:
        cursor.execute(query, params or ())
        clear_query_cache()
        return cursor.rowcount


def execute_insert(query: str, params: Optional[Union[Tuple, Dict, List]] = None) -> int:
    """Executes an INSERT statement, clears cache, and returns the last inserted ID."""
    with get_db_cursor(commit=True, dictionary=False) as cursor:
        cursor.execute(query, params or ())
        clear_query_cache()
        return cursor.lastrowid


def check_db_connection() -> Tuple[bool, str]:
    """Tests connection to MySQL and returns status and error message if any."""
    try:
        conn = get_connection()
        if conn.is_connected():
            conn.close()
            return True, "Connected successfully to MySQL database."
        return False, "Failed to connect to MySQL."
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False, str(e)


def run_schema_sql(schema_path: str = "schema.sql") -> Tuple[bool, str]:
    """Applies schema.sql to the database if tables need initialization."""
    if not os.path.exists(schema_path):
        return False, f"Schema file {schema_path} not found."

    try:
        ensure_database_exists()
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            autocommit=True
        )
        cursor = conn.cursor()

        with open(schema_path, "r", encoding="utf-8") as f:
            sql_file = f.read()

        clean_lines = []
        for line in sql_file.splitlines():
            line_str = re.sub(r'--.*$', '', line).strip()
            if line_str:
                clean_lines.append(line_str)
        cleaned_sql = " ".join(clean_lines)
        statements = [stmt.strip() for stmt in cleaned_sql.split(";") if stmt.strip()]
        for stmt in statements:
            if stmt.lower().startswith("use ") or stmt.lower().startswith("create database"):
                continue
            cursor.execute(stmt)

        cursor.close()
        conn.close()
        clear_query_cache()
        logger.info("Schema applied successfully.")
        return True, "Schema applied successfully."
    except Exception as e:
        logger.error(f"Failed to apply schema: {e}")
        return False, f"Failed to apply schema: {e}"


# ==============================================================================
# Password Validation, Hashing & Verification Utilities
# ==============================================================================

def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Validates that password is at least 10 characters long,
    contains at least one letter and at least one number.
    """
    if len(password) < 10:
        return False, "Password must be at least 10 characters long."
    if not re.search(r'[A-Za-z]', password):
        return False, "Password must contain at least one letter."
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number."
    return True, "Password meets strength requirements."


def hash_password(password: str) -> str:
    """Hashes a plaintext password using bcrypt or PBKDF2-SHA256."""
    if HAS_BCRYPT:
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
    else:
        salt = os.urandom(16)
        pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
        return "pbkdf2$" + binascii.hexlify(salt).decode("ascii") + "$" + binascii.hexlify(pwd_hash).decode("ascii")


def verify_password(password: str, hashed: str) -> bool:
    """Verifies a plaintext password against the stored secure hash (bcrypt or PBKDF2)."""
    if not hashed or not password:
        return False
    try:
        if hashed.startswith("$2b$") or hashed.startswith("$2a$"):
            if HAS_BCRYPT:
                return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
            return False
        elif hashed.startswith("pbkdf2$"):
            parts = hashed.split("$")
            if len(parts) != 3:
                return False
            salt = binascii.unhexlify(parts[1])
            expected_hash = binascii.unhexlify(parts[2])
            pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
            return pwd_hash == expected_hash
        else:
            logger.warning("Unrecognized password hash scheme or invalid format encountered.")
            return False
    except Exception as e:
        logger.error(f"Error during password verification: {e}")
        return False


# ==============================================================================
# Race-Safe Document Sequence Generators (Atomic Sequences)
# ==============================================================================

def get_next_sequence(cursor, seq_name: str) -> int:
    """
    Atomically increments and returns the next sequence number for a given sequence name.
    Must be called inside an active transaction.
    """
    cursor.execute("SELECT next_val FROM document_sequences WHERE seq_name = %s FOR UPDATE", (seq_name,))
    row = cursor.fetchone()
    if row:
        val = row["next_val"] + 1
        cursor.execute("UPDATE document_sequences SET next_val = %s WHERE seq_name = %s", (val, seq_name))
        return val
    else:
        cursor.execute("INSERT INTO document_sequences (seq_name, next_val) VALUES (%s, 1)", (seq_name,))
        return 1


def get_next_document_number(cursor, prefix: str, year: Optional[int] = None) -> str:
    """
    Generates a race-safe formatted document identifier e.g., 'SO-2026-0001'.
    Must be called inside an active transaction with a cursor.
    """
    import datetime
    current_year = year or datetime.date.today().year
    seq_key = f"{prefix}-{current_year}"
    seq_num = get_next_sequence(cursor, seq_key)
    return f"{prefix}-{current_year}-{seq_num:04d}"


# ==============================================================================
# Category Shortcut Validation & Automatic Product Code Generation
# ==============================================================================

def validate_category_shortcut(shortcut: str, current_category_id: Optional[int] = None) -> Tuple[bool, str, str]:
    """
    Validates and normalizes category shortcut code.
    - Converts to uppercase automatically.
    - Strips leading and trailing whitespace.
    - Enforces uppercase alphanumeric format (2 to 10 characters).
    - Checks uniqueness across all categories in the database.
    Returns: (is_valid: bool, error_message: str, cleaned_shortcut: str)
    """
    if not shortcut or not shortcut.strip():
        return False, "Category Shortcut is required.", ""

    cleaned = shortcut.strip().upper()

    # Enforce uppercase alphanumeric format (2-10 chars, preferably 2-5)
    if not re.match(r"^[A-Z0-9]{2,10}$", cleaned):
        return False, "Category Shortcut must be between 2 and 10 alphanumeric characters (e.g., 'GAM', 'ELE', 'ACC').", ""

    # Check uniqueness against existing categories
    query = "SELECT id, name FROM categories WHERE UPPER(shortcut) = %s"
    params: List[Any] = [cleaned]
    if current_category_id is not None:
        query += " AND id != %s"
        params.append(current_category_id)

    dup = execute_one(query, tuple(params))
    if dup:
        return False, f"Shortcut '{cleaned}' is already assigned to category '{dup['name']}'.", ""

    return True, "", cleaned


def peek_next_product_code(category_id: int) -> str:
    """
    Calculates and returns a preview of the next available product code
    for a given category without consuming or locking the sequence.
    Format: CATEGORY_SHORTCUT-SEQUENCE_NUMBER (e.g., GAM-001)
    """
    cat = execute_one("SELECT id, shortcut FROM categories WHERE id = %s", (category_id,))
    if not cat or not cat.get("shortcut"):
        return "PRD-001"

    shortcut = cat["shortcut"].upper()
    seq_name = f"PROD_CAT_{category_id}"

    seq_row = execute_one("SELECT next_val FROM document_sequences WHERE seq_name = %s", (seq_name,))
    if seq_row:
        candidate_num = int(seq_row["next_val"]) + 1
    else:
        # Scan existing products in this category
        prods = execute_query("SELECT sku FROM products WHERE category_id = %s", (category_id,))
        max_num = 0
        for p in prods:
            digits = re.findall(r"\d+", p.get("sku") or "")
            if digits:
                max_num = max(max_num, int(digits[-1]))
        candidate_num = max_num + 1

    # Ensure no collision with existing products
    while True:
        code = f"{shortcut}-{candidate_num:03d}"
        existing = execute_one("SELECT id FROM products WHERE sku = %s", (code,))
        if not existing:
            return code
        candidate_num += 1


def get_next_product_code(cursor, category_id: int) -> str:
    """
    Atomically reserves and returns the next product code for a category inside an active transaction.
    Format: CATEGORY_SHORTCUT-SEQUENCE_NUMBER (e.g. GAM-001).
    Guarantees independent sequences per category, connection-local concurrency safety via LAST_INSERT_ID,
    and never reuses numbers even if products were deleted previously.
    """
    cursor.execute("SELECT id, shortcut FROM categories WHERE id = %s", (category_id,))
    cat = cursor.fetchone()
    if not cat or not cat.get("shortcut"):
        raise ValueError(f"Category with ID {category_id} not found or has no shortcut.")

    shortcut = cat["shortcut"].upper()
    seq_name = f"PROD_CAT_{category_id}"

    # Atomic insert or increment on document_sequences with connection-local LAST_INSERT_ID
    cursor.execute(
        """
        INSERT INTO document_sequences (seq_name, next_val)
        VALUES (%s, LAST_INSERT_ID(1))
        ON DUPLICATE KEY UPDATE next_val = LAST_INSERT_ID(next_val + 1)
        """,
        (seq_name,)
    )
    cursor.execute("SELECT LAST_INSERT_ID() as val")
    seq_num = int(cursor.fetchone()["val"])

    # Loop until free to avoid collisions with legacy custom SKUs
    while True:
        code = f"{shortcut}-{seq_num:03d}"
        cursor.execute("SELECT id FROM products WHERE sku = %s", (code,))
        if not cursor.fetchone():
            return code
        cursor.execute(
            """
            UPDATE document_sequences 
            SET next_val = LAST_INSERT_ID(next_val + 1) 
            WHERE seq_name = %s
            """,
            (seq_name,)
        )
        cursor.execute("SELECT LAST_INSERT_ID() as val")
        seq_num = int(cursor.fetchone()["val"])




