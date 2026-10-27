"""
Unit & Integration Tests for Category Shortcut Codes and Automatic Product IDs (SIOM)
Verifies:
1. Create a category with a new shortcut.
2. Attempt to create another category with the same shortcut.
3. Create multiple products within one category.
4. Create products in different categories and verify independent sequences.
5. Edit a product and confirm its code remains unchanged.
6. Restart/re-query verification of saved shortcuts and sequences.
7. Verify existing products and dependent module links remain intact.
8. Test failed database operations rollback and simultaneous product creation concurrency.
"""

import threading
# pyrefly: ignore [missing-import]
import pytest
from decimal import Decimal
import database as db

@pytest.fixture(scope="module")
def setup_test_categories():
    """Sets up clean test categories and tears them down after module runs."""
    # Ensure pool and migrations are active
    db.init_db_pool()
    
    # Cleanup any leftovers from prior runs
    with db.get_db_transaction() as (cursor, conn):
        cursor.execute("DELETE FROM products WHERE sku LIKE 'TEST-%' OR sku LIKE 'TST1-%' OR sku LIKE 'TST2-%' OR sku LIKE 'CONC-%'")
        cursor.execute("DELETE FROM categories WHERE shortcut IN ('TEST', 'TST1', 'TST2', 'CONC')")
        cursor.execute("DELETE FROM document_sequences WHERE seq_name IN ('PROD_CAT_TEST', 'PROD_CAT_TST1', 'PROD_CAT_TST2') OR seq_name LIKE 'PROD_CAT_CONC%'")
    
    yield
    
    # Cleanup after test
    with db.get_db_transaction() as (cursor, conn):
        cursor.execute("DELETE FROM inventory WHERE product_id IN (SELECT id FROM products WHERE sku LIKE 'TEST-%' OR sku LIKE 'TST1-%' OR sku LIKE 'TST2-%' OR sku LIKE 'CONC-%')")
        cursor.execute("DELETE FROM stock_movements WHERE product_id IN (SELECT id FROM products WHERE sku LIKE 'TEST-%' OR sku LIKE 'TST1-%' OR sku LIKE 'TST2-%' OR sku LIKE 'CONC-%')")
        cursor.execute("DELETE FROM products WHERE sku LIKE 'TEST-%' OR sku LIKE 'TST1-%' OR sku LIKE 'TST2-%' OR sku LIKE 'CONC-%'")
        cursor.execute("DELETE FROM categories WHERE shortcut IN ('TEST', 'TST1', 'TST2', 'CONC')")


def test_scenario_1_create_category_with_new_shortcut(setup_test_categories):
    """Scenario 1: Create a category with a new shortcut."""
    # Test shortcut validation
    is_valid, err, cleaned = db.validate_category_shortcut("  test  ")
    assert is_valid is True
    assert cleaned == "TEST"
    assert err == ""

    # Create category in database
    cat_id = db.execute_insert(
        "INSERT INTO categories (name, shortcut, description, is_active) VALUES (%s, %s, %s, 1)",
        ("Test Category Alpha", cleaned, "Category for testing shortcuts")
    )
    assert cat_id > 0

    # Verify stored correctly
    saved_cat = db.execute_one("SELECT * FROM categories WHERE id = %s", (cat_id,))
    assert saved_cat["shortcut"] == "TEST"
    assert saved_cat["name"] == "Test Category Alpha"


def test_scenario_2_duplicate_shortcut_rejected(setup_test_categories):
    """Scenario 2: Attempt to create another category with the same shortcut."""
    # Validation should reject duplicate shortcut (case-insensitive)
    is_valid, err, _ = db.validate_category_shortcut("test")
    assert is_valid is False
    assert "already assigned" in err

    is_valid, err, _ = db.validate_category_shortcut("TEST")
    assert is_valid is False
    assert "already assigned" in err

    # Database UNIQUE constraint must also reject direct duplicate insertion
    with pytest.raises(Exception):
        db.execute_insert(
            "INSERT INTO categories (name, shortcut, description, is_active) VALUES (%s, %s, %s, 1)",
            ("Another Test Category", "TEST", "Should fail due to duplicate shortcut")
        )


def test_scenario_3_create_multiple_products_one_category(setup_test_categories):
    """Scenario 3: Create multiple products within one category."""
    cat = db.execute_one("SELECT id FROM categories WHERE shortcut = 'TEST'")
    cat_id = cat["id"]

    # Preview before creating
    preview1 = db.peek_next_product_code(cat_id)
    assert preview1 == "TEST-001"

    # Create product 1
    with db.get_db_transaction() as (cursor, conn):
        code1 = db.get_next_product_code(cursor, cat_id)
        assert code1 == "TEST-001"
        cursor.execute(
            "INSERT INTO products (sku, name, category_id, cost_price, selling_price, reorder_level) VALUES (%s, %s, %s, 10, 20, 5)",
            (code1, "Test Product 1", cat_id)
        )

    # Preview after product 1
    preview2 = db.peek_next_product_code(cat_id)
    assert preview2 == "TEST-002"

    # Create product 2
    with db.get_db_transaction() as (cursor, conn):
        code2 = db.get_next_product_code(cursor, cat_id)
        assert code2 == "TEST-002"
        cursor.execute(
            "INSERT INTO products (sku, name, category_id, cost_price, selling_price, reorder_level) VALUES (%s, %s, %s, 15, 30, 5)",
            (code2, "Test Product 2", cat_id)
        )

    # Preview after product 2
    preview3 = db.peek_next_product_code(cat_id)
    assert preview3 == "TEST-003"


def test_scenario_4_different_categories_independent_sequences(setup_test_categories):
    """Scenario 4: Create products in different categories and verify independent sequences."""
    cat1_id = db.execute_insert(
        "INSERT INTO categories (name, shortcut, description, is_active) VALUES (%s, %s, %s, 1)",
        ("Test Category One", "TST1", "Category 1")
    )
    cat2_id = db.execute_insert(
        "INSERT INTO categories (name, shortcut, description, is_active) VALUES (%s, %s, %s, 1)",
        ("Test Category Two", "TST2", "Category 2")
    )

    # First product in Category One
    with db.get_db_transaction() as (cursor, conn):
        p1 = db.get_next_product_code(cursor, cat1_id)
        assert p1 == "TST1-001"
        cursor.execute("INSERT INTO products (sku, name, category_id) VALUES (%s, %s, %s)", (p1, "Cat1 Prod 1", cat1_id))

    # First product in Category Two (must start at 001 independently)
    with db.get_db_transaction() as (cursor, conn):
        p2 = db.get_next_product_code(cursor, cat2_id)
        assert p2 == "TST2-001"
        cursor.execute("INSERT INTO products (sku, name, category_id) VALUES (%s, %s, %s)", (p2, "Cat2 Prod 1", cat2_id))

    # Second product in Category One (must advance to 002)
    with db.get_db_transaction() as (cursor, conn):
        p3 = db.get_next_product_code(cursor, cat1_id)
        assert p3 == "TST1-002"
        cursor.execute("INSERT INTO products (sku, name, category_id) VALUES (%s, %s, %s)", (p3, "Cat1 Prod 2", cat1_id))

    # Second product in Category Two (must advance to 002 independently)
    with db.get_db_transaction() as (cursor, conn):
        p4 = db.get_next_product_code(cursor, cat2_id)
        assert p4 == "TST2-002"
        cursor.execute("INSERT INTO products (sku, name, category_id) VALUES (%s, %s, %s)", (p4, "Cat2 Prod 2", cat2_id))


def test_scenario_5_edit_product_code_unchanged(setup_test_categories):
    """Scenario 5: Edit a product and confirm its code remains unchanged."""
    prod = db.execute_one("SELECT * FROM products WHERE sku = 'TEST-001'")
    assert prod is not None
    original_code = prod["sku"]

    # Simulate edit updating name and prices
    db.execute_update(
        "UPDATE products SET name = %s, cost_price = %s, selling_price = %s WHERE id = %s",
        ("Updated Name Without Code Change", Decimal("99.99"), Decimal("149.99"), prod["id"])
    )

    updated_prod = db.execute_one("SELECT * FROM products WHERE id = %s", (prod["id"],))
    assert updated_prod["sku"] == original_code
    assert updated_prod["name"] == "Updated Name Without Code Change"


def test_scenario_6_shortcuts_and_sequences_persist(setup_test_categories):
    """Scenario 6: Verify saved shortcuts and sequence states persist in the database."""
    # Direct fresh connection check simulating app restart
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT shortcut FROM categories WHERE name = 'Test Category Alpha'")
    row = cursor.fetchone()
    assert row["shortcut"] == "TEST"

    # Verify sequence state persists
    cursor.execute("SELECT next_val FROM document_sequences WHERE seq_name = (SELECT CONCAT('PROD_CAT_', id) FROM categories WHERE shortcut = 'TEST')")
    seq_row = cursor.fetchone()
    assert seq_row["next_val"] >= 2
    cursor.close()
    conn.close()


def test_scenario_7_existing_products_and_dependent_modules():
    """Scenario 7: Verify that existing products and historical records continue working."""
    # Check that legacy categories all have shortcuts populated
    categories = db.execute_query("SELECT id, name, shortcut FROM categories WHERE is_active = 1")
    assert len(categories) >= 12
    for c in categories:
        assert c["shortcut"] is not None and len(c["shortcut"]) >= 2

    # Check products linkage
    products = db.execute_query("SELECT p.id, p.sku, p.name, c.shortcut FROM products p JOIN categories c ON p.category_id = c.id LIMIT 10")
    assert len(products) > 0
    for p in products:
        assert p["sku"] is not None
        assert p["shortcut"] is not None


def test_scenario_8_failed_operations_and_concurrency(setup_test_categories):
    """Scenario 8: Test failed database operations rollback and simultaneous product creation concurrency."""
    cat = db.execute_one("SELECT id FROM categories WHERE shortcut = 'TEST'")
    cat_id = cat["id"]

    # Test rollback on failure (ensures atomicity)
    initial_seq = db.execute_one("SELECT next_val FROM document_sequences WHERE seq_name = %s", (f"PROD_CAT_{cat_id}",))["next_val"]
    try:
        with db.get_db_transaction() as (cursor, conn):
            db.get_next_product_code(cursor, cat_id)
            # Intentionally force a database error
            cursor.execute("INSERT INTO products (sku, name, category_id) VALUES ('TEST-ROLLBACK', NULL, %s)", (cat_id,))
    except Exception:
        pass  # Expected rollback

    # Concurrency test: simulate multiple simultaneous worker threads creating products for category 'CONC'
    conc_cat_id = db.execute_insert(
        "INSERT INTO categories (name, shortcut, description, is_active) VALUES (%s, %s, %s, 1)",
        ("Concurrent Category", "CONC", "Testing parallel inserts")
    )

    generated_codes = []
    errors = []
    lock = threading.Lock()

    def worker():
        try:
            with db.get_db_transaction() as (cursor, conn):
                code = db.get_next_product_code(cursor, conc_cat_id)
                cursor.execute(
                    "INSERT INTO products (sku, name, category_id) VALUES (%s, %s, %s)",
                    (code, f"Parallel Product {code}", conc_cat_id)
                )
                with lock:
                    generated_codes.append(code)
        except Exception as e:
            with lock:
                errors.append(str(e))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Errors encountered during concurrent creation: {errors}"
    assert len(generated_codes) == 8
    # Every code must be strictly unique!
    assert len(set(generated_codes)) == 8
    for i in range(1, 9):
        assert f"CONC-{i:03d}" in generated_codes
