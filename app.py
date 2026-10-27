"""
Smart Inventory & Order Management System (SIOM)
Main Streamlit Application Entrypoint, Role-Based Navigation & Page Router.
"""

import html
import streamlit as st
import database as db
from modules.ui_components import apply_custom_styles, require_role
from modules.auth_ui import render_login_or_setup, render_profile_modal
from modules.dashboard_ui import render_dashboard_page
from modules.categories_ui import render_categories_page
from modules.products_ui import render_products_page
from modules.suppliers_ui import render_suppliers_page
from modules.customers_ui import render_customers_page
from modules.inventory_ui import render_inventory_page
from modules.purchase_orders_ui import render_purchase_orders_page
from modules.sales_orders_ui import render_sales_orders_page
from modules.payments_ui import render_payments_page
from modules.shipments_ui import render_shipments_page
from reports import render_reports_page

# Page Configuration
st.set_page_config(
    page_title="Smart Inventory - Enterprise ERP",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply Centralized Enterprise Design System CSS from assets/style.css
apply_custom_styles()

# Dictionary Page Router with Role-Based Access Permissions
PAGE_ROUTES = {
    "Dashboard": {
        "func": render_dashboard_page,
        "roles": ["Super Admin", "Inventory Manager", "Sales Manager"],
        "title": "Dashboard"
    },
    "Products": {
        "func": render_products_page,
        "roles": ["Super Admin", "Inventory Manager"],
        "title": "Products"
    },
    "Categories": {
        "func": render_categories_page,
        "roles": ["Super Admin", "Inventory Manager"],
        "title": "Categories"
    },
    "Stock": {
        "func": render_inventory_page,
        "roles": ["Super Admin", "Inventory Manager"],
        "title": "Stock"
    },
    "Purchase Orders": {
        "func": render_purchase_orders_page,
        "roles": ["Super Admin", "Inventory Manager"],
        "title": "Purchase Orders"
    },
    "Sales Orders": {
        "func": render_sales_orders_page,
        "roles": ["Super Admin", "Sales Manager"],
        "title": "Sales Orders"
    },
    "Suppliers": {
        "func": render_suppliers_page,
        "roles": ["Super Admin", "Inventory Manager"],
        "title": "Suppliers"
    },
    "Customers": {
        "func": render_customers_page,
        "roles": ["Super Admin", "Sales Manager"],
        "title": "Customers"
    },
    "Payments": {
        "func": render_payments_page,
        "roles": ["Super Admin", "Sales Manager"],
        "title": "Payments"
    },
    "Shipments": {
        "func": render_shipments_page,
        "roles": ["Super Admin", "Sales Manager"],
        "title": "Shipments"
    },
    "Reports": {
        "func": render_reports_page,
        "roles": ["Super Admin", "Inventory Manager", "Sales Manager"],
        "title": "Reports"
    },
    "Profile": {
        "func": render_profile_modal,
        "roles": ["Super Admin", "Inventory Manager", "Sales Manager"],
        "title": "Profile"
    }
}

# Legacy mapping for backwards compatibility
LEGACY_ROUTE_MAP = {
    "Executive Dashboard": "Dashboard",
    "Product Catalog": "Products",
    "Category Management": "Categories",
    "Inventory & Stock": "Stock",
    "Supplier Directory": "Suppliers",
    "Customer Directory": "Customers",
    "Purchase Orders (Inbound)": "Purchase Orders",
    "Sales Orders (Outbound)": "Sales Orders",
    "Payments & Receivables": "Payments",
    "Shipment Tracking": "Shipments",
    "Analytics & Reports": "Reports",
    "Admin Profile & Security": "Profile"
}

# Simplified Sidebar Navigation Hierarchy
SIDEBAR_NAVIGATION = [
    {
        "type": "item",
        "key": "Dashboard",
        "label": "📊 Dashboard",
        "roles": ["Super Admin", "Inventory Manager", "Sales Manager"]
    },
    {
        "type": "group",
        "title": "📦 Inventory",
        "items": [
            {"key": "Products", "label": "Products", "roles": ["Super Admin", "Inventory Manager"]},
            {"key": "Categories", "label": "Categories", "roles": ["Super Admin", "Inventory Manager"]},
            {"key": "Stock", "label": "Stock", "roles": ["Super Admin", "Inventory Manager"]}
        ]
    },
    {
        "type": "group",
        "title": "🛒 Orders",
        "items": [
            {"key": "Purchase Orders", "label": "Purchase Orders", "roles": ["Super Admin", "Inventory Manager"]},
            {"key": "Sales Orders", "label": "Sales Orders", "roles": ["Super Admin", "Sales Manager"]}
        ]
    },
    {
        "type": "group",
        "title": "👥 People",
        "items": [
            {"key": "Suppliers", "label": "Suppliers", "roles": ["Super Admin", "Inventory Manager"]},
            {"key": "Customers", "label": "Customers", "roles": ["Super Admin", "Sales Manager"]}
        ]
    },
    {
        "type": "group",
        "title": "💳 Payments & Delivery",
        "items": [
            {"key": "Payments", "label": "Payments", "roles": ["Super Admin", "Sales Manager"]},
            {"key": "Shipments", "label": "Shipments", "roles": ["Super Admin", "Sales Manager"]}
        ]
    },
    {
        "type": "item",
        "key": "Reports",
        "label": "📈 Reports",
        "roles": ["Super Admin", "Inventory Manager", "Sales Manager"]
    },
    {
        "type": "item",
        "key": "Profile",
        "label": "👤 Profile",
        "roles": ["Super Admin", "Inventory Manager", "Sales Manager"]
    }
]


def render_sidebar():
    """Renders the simplified dark navy sidebar filtered by current user role."""
    user_role = st.session_state.get("role", "Super Admin")
    current_page = st.session_state.get("current_page", "Dashboard")
    if current_page in LEGACY_ROUTE_MAP:
        current_page = LEGACY_ROUTE_MAP[current_page]
        st.session_state["current_page"] = current_page

    with st.sidebar:
        # Brand Header
        st.markdown(
            """
            <div class="siom-brand-header">
                <div class="siom-brand-logo">
                    <div class="siom-brand-icon">📦</div>
                    <div>
                        <div class="siom-brand-name">SIOM</div>
                        <div class="siom-brand-subtitle">Smart Inventory System</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Simplified Navigation Structure
        for entry in SIDEBAR_NAVIGATION:
            if entry["type"] == "item":
                if user_role == "Super Admin" or user_role in entry["roles"]:
                    is_active = (current_page == entry["key"])
                    btn_type = "primary" if is_active else "secondary"
                    if st.button(
                        entry["label"],
                        key=f"nav_btn_{entry['key'].lower().replace(' ', '_')}",
                        use_container_width=True,
                        type=btn_type
                    ):
                        if current_page != entry["key"]:
                            st.session_state["current_page"] = entry["key"]
                            st.rerun()

            elif entry["type"] == "group":
                accessible_items = [
                    item for item in entry["items"]
                    if user_role == "Super Admin" or user_role in item["roles"]
                ]
                if not accessible_items:
                    continue

                st.markdown(
                    f'<div class="siom-nav-group-header">{html.escape(entry["title"])}</div>',
                    unsafe_allow_html=True
                )

                st.markdown('<div class="siom-sub-nav">', unsafe_allow_html=True)
                for item in accessible_items:
                    is_active = (current_page == item["key"])
                    btn_type = "primary" if is_active else "secondary"
                    item_label = f"   {item['label']}"
                    if st.button(
                        item_label,
                        key=f"nav_btn_{item['key'].lower().replace(' ', '_')}",
                        use_container_width=True,
                        type=btn_type
                    ):
                        if current_page != item["key"]:
                            st.session_state["current_page"] = item["key"]
                            st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("---")

        # Bottom User Session Profile Card
        full_name = st.session_state.get("full_name", "System Admin")
        user_initials = "".join([part[0].upper() for part in full_name.split()[:2]]) if full_name else "SA"
        safe_name = html.escape(str(full_name))
        safe_role = html.escape(str(user_role))

        st.markdown(
            f"""
            <div class="siom-user-card">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div style="background: linear-gradient(135deg, #2563eb, #1d4ed8); color: #ffffff; width: 34px; height: 34px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 12px; box-shadow: 0 2px 6px rgba(37,99,235,0.35); flex-shrink: 0;">
                        {user_initials}
                    </div>
                    <div style="flex: 1; overflow: hidden; min-width: 0;">
                        <div style="font-size: 13px; font-weight: 700; color: #ffffff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{safe_name}</div>
                        <div style="font-size: 11px; color: #38bdf8; display: flex; align-items: center; gap: 4px; margin-top: 1px;">
                            <span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #10b981;"></span> {safe_role}
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown('<div class="siom-signout-btn">', unsafe_allow_html=True)
        if st.button("🚪 Sign Out", use_container_width=True, key="signout_btn"):
            st.session_state["authenticated"] = False
            st.session_state.clear()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)


def main():
    # Session state initialization
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Dashboard"

    # Check authentication
    if not st.session_state["authenticated"]:
        render_login_or_setup()
        return

    # Render Clean Sidebar Navigation
    render_sidebar()

    # --------------------------------------------------------------------------
    # Dictionary Page Router with Permission Checks
    # --------------------------------------------------------------------------
    current_page = st.session_state.get("current_page", "Dashboard")
    if current_page in LEGACY_ROUTE_MAP:
        current_page = LEGACY_ROUTE_MAP[current_page]
        st.session_state["current_page"] = current_page

    user_role = st.session_state.get("role", "Super Admin")

    route_info = PAGE_ROUTES.get(current_page)
    if route_info:
        # Enforce security role check
        require_role(route_info["roles"])
        route_info["func"]()
    else:
        st.session_state["current_page"] = "Dashboard"
        render_dashboard_page()


if __name__ == "__main__":
    main()
