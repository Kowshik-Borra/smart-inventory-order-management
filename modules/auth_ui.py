"""
Authentication Module: Login, First-Run Setup, Session Management, Rate Limiting, and Profile Management.
"""

import time
import html
import logging
import streamlit as st
import database as db
from modules.ui_components import render_page_header, render_section_header

logger = logging.getLogger("siom.auth")


# Rate Limiting Configuration
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_SECONDS = 300  # 5 minutes


def get_rate_limit_state():
    """Initializes and retrieves rate-limiting state from session."""
    if "login_failed_attempts" not in st.session_state:
        st.session_state["login_failed_attempts"] = 0
    if "login_locked_until" not in st.session_state:
        st.session_state["login_locked_until"] = 0
    return st.session_state["login_failed_attempts"], st.session_state["login_locked_until"]


def render_login_or_setup():
    """Renders either First-Run Setup or Login Form based on DB state."""
    connected, conn_msg = db.check_db_connection()
    if not connected:
        st.error(f"Cannot connect to MySQL Database: {html.escape(str(conn_msg))}")
        st.info(
            "Please check your `.env` configuration, ensure the MySQL server is running, "
            "and that user credentials and port are correct."
        )
        with st.expander("Initialize / Retry Schema"):
            if st.button("Apply Database Schema Now", type="primary"):
                with st.spinner("Applying database schema..."):
                    success, msg = db.run_schema_sql("schema.sql")
                if success:
                    st.toast("Database schema created successfully!", icon="✅")
                    st.rerun()
                else:
                    st.error(f"Error applying schema: {html.escape(str(msg))}")
        return

    try:
        admin_count = db.execute_one("SELECT COUNT(*) as count FROM admins")["count"]
    except Exception as e:
        st.warning(f"Database tables not found or uninitialized: {html.escape(str(e))}")
        if st.button("Initialize Database Schema Now", type="primary"):
            with st.spinner("Initializing schema..."):
                success, msg = db.run_schema_sql("schema.sql")
            if success:
                st.toast("Schema created successfully!", icon="✅")
                st.rerun()
            else:
                st.error(f"Error creating schema: {html.escape(str(msg))}")
        return

    col1, col2, col3 = st.columns([1, 1.8, 1])
    with col2:
        if admin_count == 0:
            render_first_run_setup()
        else:
            render_login_form()


def render_first_run_setup():
    """Initial Administrator Account Setup with strict password strength validation."""
    st.markdown(
        """
        <div class="siom-auth-card">
            <div class="siom-auth-icon">★</div>
            <h2 class="siom-auth-title">Welcome to Smart Inventory (SIOM)</h2>
            <p class="siom-auth-subtitle">First-run setup detected. Create your root Super Administrator account to initialize the system.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    with st.form("first_run_setup_form"):
        full_name = st.text_input("Full Name *", placeholder="e.g. System Administrator")
        username = st.text_input("Username *", placeholder="e.g. admin")
        email = st.text_input("Email Address *", placeholder="e.g. admin@company.com")
        password = st.text_input("Master Password (min 10 chars, letter + number) *", type="password")
        confirm_password = st.text_input("Confirm Password *", type="password")

        submitted = st.form_submit_button("Create Master Admin Account", type="primary", use_container_width=True)
        if submitted:
            if not full_name or not username or not email or not password:
                st.error("Please fill in all required fields.")
                return
            if password != confirm_password:
                st.error("Passwords do not match.")
                return
            
            valid, msg = db.validate_password_strength(password)
            if not valid:
                st.error(msg)
                return

            try:
                hashed = db.hash_password(password)
                db.execute_insert(
                    """
                    INSERT INTO admins (username, email, password_hash, full_name, role, status)
                    VALUES (%s, %s, %s, %s, 'Super Admin', 'Active')
                    """,
                    (username.strip(), email.strip().lower(), hashed, full_name.strip())
                )
                st.toast("Admin account created successfully! You can now log in.", icon="✅")
                st.rerun()
            except Exception as e:
                logger.error(f"Error creating admin account: {e}", exc_info=True)
                st.error("Failed to create master admin account. Ensure username and email are unique.")



def render_login_form():
    """Standard Administrator Login Form with rate-limiting protection."""
    st.markdown(
        """
        <div class="siom-auth-card">
            <div class="siom-auth-icon">❖</div>
            <h2 class="siom-auth-title">Smart Inventory ERP</h2>
            <p class="siom-auth-subtitle">Enterprise Inventory, Procurement & Fulfillment System</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    failed_attempts, locked_until = get_rate_limit_state()
    now = time.time()

    # Check if account/session is currently locked out
    if locked_until > now:
        remaining = int(locked_until - now)
        mins, secs = divmod(remaining, 60)
        st.error(f"🔒 **Account Temporarily Locked**: Too many failed login attempts. Please try again in **{mins}m {secs}s**.")
        return

    with st.form("login_form"):
        username_or_email = st.text_input("Username or Email", placeholder="Enter your username or email")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        login_btn = st.form_submit_button("Sign In to ERP Dashboard", type="primary", use_container_width=True)

        if login_btn:
            if not username_or_email or not password:
                st.error("Please provide both username/email and password.")
                return

            with st.spinner("Authenticating credentials..."):
                admin = db.execute_one(
                    """
                    SELECT id, username, email, password_hash, full_name, role, status
                    FROM admins
                    WHERE (username = %s OR email = %s) AND status = 'Active'
                    """,
                    (username_or_email.strip(), username_or_email.strip().lower())
                )

                if admin and db.verify_password(password, admin["password_hash"]):
                    # Reset rate limiting counters
                    st.session_state["login_failed_attempts"] = 0
                    st.session_state["login_locked_until"] = 0

                    st.session_state["authenticated"] = True
                    st.session_state["admin_id"] = admin["id"]
                    st.session_state["username"] = admin["username"]
                    st.session_state["full_name"] = admin["full_name"]
                    st.session_state["role"] = admin["role"]
                    st.toast(f"Welcome back, {admin['full_name']}!", icon="✅")
                    st.rerun()
                else:
                    st.session_state["login_failed_attempts"] += 1
                    attempts_left = MAX_FAILED_ATTEMPTS - st.session_state["login_failed_attempts"]
                    
                    if st.session_state["login_failed_attempts"] >= MAX_FAILED_ATTEMPTS:
                        st.session_state["login_locked_until"] = time.time() + LOCKOUT_DURATION_SECONDS
                        st.error("🔒 **Account Locked**: 5 consecutive failed login attempts. Access is locked for 5 minutes.")
                    else:
                        st.error(f"Invalid credentials or account inactive. ({attempts_left} attempt(s) remaining before lockout)")


def render_profile_modal():
    """Allows current admin to change their password or view credentials."""
    render_page_header(
        title="Admin Profile & Security",
        subtitle="Manage personal administrator credentials, role access, and active session security.",
        icon="👤"
    )
    
    admin_id = st.session_state.get("admin_id")
    admin = db.execute_one("SELECT id, username, email, full_name, role, created_at FROM admins WHERE id = %s", (admin_id,))
    if not admin:
        st.error("User profile record not found.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**Username:** `{html.escape(admin['username'])}`\n\n**Email:** `{html.escape(admin['email'])}`\n\n**Role:** `{html.escape(admin['role'])}`")
    with col2:
        created_str = admin['created_at'].strftime('%Y-%m-%d %H:%M') if admin.get('created_at') else "N/A"
        st.info(f"**Full Name:** `{html.escape(admin['full_name'])}`\n\n**Member Since:** `{created_str}`")

    render_section_header("Update Account Password", "Must be at least 10 characters long with letters and numbers", "🔒")
    with st.form("change_password_form"):
        old_pass = st.text_input("Current Master Password", type="password")
        new_pass = st.text_input("New Secure Password", type="password")
        confirm_pass = st.text_input("Confirm New Password", type="password")
        update_btn = st.form_submit_button("Update Password", type="primary", use_container_width=True)

        if update_btn:
            curr_record = db.execute_one("SELECT password_hash FROM admins WHERE id = %s", (admin_id,))
            if not db.verify_password(old_pass, curr_record["password_hash"]):
                st.error("Current password is incorrect.")
                return
            if new_pass != confirm_pass:
                st.error("New passwords do not match.")
                return
            
            valid, msg = db.validate_password_strength(new_pass)
            if not valid:
                st.error(msg)
                return

            with st.spinner("Updating password securely..."):
                new_hash = db.hash_password(new_pass)
                db.execute_update("UPDATE admins SET password_hash = %s WHERE id = %s", (new_hash, admin_id))
            st.toast("Password updated successfully!", icon="✅")
