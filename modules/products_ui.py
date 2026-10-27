"""
Product Management Module: Master catalog CRUD, SKU validation, pricing rules,
inventory balance linking, multi-criteria filters, safe deletion/deactivation,
and purchase/sales/movement history inspection.
"""

import html
import logging
from decimal import Decimal
import streamlit as st
import pandas as pd
import database as db
from modules.ui_components import (
    render_page_header,
    render_metric_card,
    render_section_header,
    render_empty_state,
    paginate_dataframe,
    format_currency
)

logger = logging.getLogger("siom.products")


def render_products_page():
    render_page_header(
        title="Product Master Catalog",
        subtitle="Manage product master records, pricing in ₹, reorder thresholds, inventory balances, and linked transaction history.",
        icon="📦"
    )

    # --------------------------------------------------------------------------
    # 1. Add New Product Expander (Directly Accessible)
    # --------------------------------------------------------------------------
    categories_for_add = db.execute_query("SELECT id, name, shortcut FROM categories WHERE is_active = 1 ORDER BY name ASC")
    
    with st.expander("➕ Register New Product Master", expanded=False):
        if not categories_for_add:
            st.warning("Please create at least one active category before adding products.")
        else:
            cat_map_for_add = {c["id"]: c for c in categories_for_add}
            col_cat_sel, col_preview = st.columns([2, 1])
            with col_cat_sel:
                a_cat_id = st.selectbox(
                    "Category *",
                    options=[c["id"] for c in categories_for_add],
                    format_func=lambda x: f"{cat_map_for_add[x]['name']} [{cat_map_for_add[x].get('shortcut', 'N/A')}]",
                    key="add_product_category_select"
                )

            preview_code = db.peek_next_product_code(a_cat_id)
            with col_preview:
                st.text_input(
                    "Next Product Code Preview",
                    value=preview_code,
                    disabled=True,
                    help="Auto-generated using category shortcut and independent sequence"
                )

            with st.form("add_product_form", clear_on_submit=True):
                a_col1, a_col2 = st.columns(2)
                with a_col1:
                    st.text_input(
                        "Product Code (Auto-generated)",
                        value=preview_code,
                        disabled=True,
                        help="Auto-generated based on selected category shortcut and sequence"
                    )
                    a_name = st.text_input("Product Name *", placeholder="e.g. Mechanical Gaming Keyboard RGB")
                    a_unit = st.text_input("Unit of Measure *", value="pcs")

                with a_col2:
                    a_cost = st.number_input("Cost Price (₹) *", min_value=0.0, value=500.0, step=50.0)
                    a_sell = st.number_input("Selling Price (₹) *", min_value=0.0, value=899.0, step=50.0)
                    a_reorder = st.number_input("Reorder Level Threshold *", min_value=0, value=10, step=1)
                    a_init_qty = st.number_input("Initial Opening Stock Quantity", min_value=0, value=25, step=1)

                a_desc = st.text_area("Product Description / Technical Specifications", placeholder="Specs, dimensions, warranty, supplier notes...")
                a_active = st.checkbox("Active Product in Catalog", value=True)
                create_prod_btn = st.form_submit_button("Create Product & Initialize Stock", type="primary", use_container_width=True)

                if create_prod_btn:
                    if not a_name.strip():
                        st.error("Product Name is mandatory.")
                    else:
                        with st.spinner("Creating product record..."):
                            try:
                                with db.get_db_transaction() as (cursor, conn):
                                    # Atomically generate and reserve next product code
                                    final_prod_code = db.get_next_product_code(cursor, a_cat_id)

                                    cursor.execute(
                                        """
                                        INSERT INTO products 
                                        (sku, name, category_id, description, cost_price, selling_price, reorder_level, unit, is_active)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                        """,
                                        (
                                            final_prod_code, a_name.strip(), a_cat_id, a_desc.strip(),
                                            Decimal(str(a_cost)), Decimal(str(a_sell)), int(a_reorder),
                                            a_unit.strip(), 1 if a_active else 0
                                        )
                                    )
                                    new_prod_id = cursor.lastrowid

                                    cursor.execute(
                                        """
                                        INSERT INTO inventory (product_id, quantity_on_hand, reorder_point)
                                        VALUES (%s, %s, %s)
                                        """,
                                        (new_prod_id, int(a_init_qty), int(a_reorder))
                                    )

                                    if int(a_init_qty) > 0:
                                        admin_id = st.session_state.get("admin_id")
                                        cursor.execute(
                                            """
                                            INSERT INTO stock_movements 
                                            (product_id, movement_type, quantity, balance_after, reference_type, reference_id, notes, created_by_admin_id)
                                            VALUES (%s, 'INITIAL_STOCK', %s, %s, 'INITIAL_STOCK', NULL, 'Initial opening stock upon creation', %s)
                                            """,
                                            (new_prod_id, int(a_init_qty), int(a_init_qty), admin_id)
                                        )

                                st.toast(f"Product '{a_name}' created successfully with Code '{final_prod_code}'!", icon="✅")
                                st.rerun()
                            except Exception as ex:
                                logger.error(f"Error creating product: {ex}", exc_info=True)
                                st.error(f"A database error occurred while creating the product: {ex}")

    # --------------------------------------------------------------------------
    # 2. Multi-Dimensional Search & Filters
    # --------------------------------------------------------------------------
    st.markdown('<div class="siom-filter-panel">', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns([2, 1.5, 1.2, 1.2])
    with col1:
        search_query = st.text_input("🔍 Search Products", placeholder="Search by Product Code, Name, or Specs...")
    with col2:
        categories = db.execute_query("SELECT id, name FROM categories WHERE is_active = 1 ORDER BY name ASC")
        cat_options = {"All Categories": None}
        for c in categories:
            cat_options[c["name"]] = c["id"]
        selected_cat_filter = st.selectbox("Category", list(cat_options.keys()))
    with col3:
        stock_filter = st.selectbox("Stock Status", ["All Levels", "In Stock (>0)", "Low Stock (Alert)", "Out of Stock (0)"], key="prod_stock_filt")
    with col4:
        status_filter = st.selectbox("Status", ["All", "Active Only", "Inactive Only"], key="prod_status_filt")
    st.markdown('</div>', unsafe_allow_html=True)

    # Build SQL query
    query = """
        SELECT 
            p.id, 
            p.sku, 
            p.name, 
            c.name AS category_name, 
            p.category_id,
            p.description, 
            p.cost_price, 
            p.selling_price, 
            p.reorder_level, 
            p.unit, 
            p.is_active, 
            p.created_at,
            COALESCE(i.quantity_on_hand, 0) AS current_stock
        FROM products p
        JOIN categories c ON p.category_id = c.id
        LEFT JOIN inventory i ON p.id = i.product_id
        WHERE 1=1
    """
    params = []

    if search_query:
        query += " AND (p.sku LIKE %s OR p.name LIKE %s OR p.description LIKE %s)"
        params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])

    if cat_options[selected_cat_filter] is not None:
        query += " AND p.category_id = %s"
        params.append(cat_options[selected_cat_filter])

    if stock_filter == "In Stock (>0)":
        query += " AND COALESCE(i.quantity_on_hand, 0) > 0"
    elif stock_filter == "Low Stock (Alert)":
        query += " AND COALESCE(i.quantity_on_hand, 0) <= COALESCE(i.reorder_point, p.reorder_level)"
    elif stock_filter == "Out of Stock (0)":
        query += " AND COALESCE(i.quantity_on_hand, 0) = 0"

    if status_filter == "Active Only":
        query += " AND p.is_active = 1"
    elif status_filter == "Inactive Only":
        query += " AND p.is_active = 0"

    query += " ORDER BY p.name ASC"
    products = db.execute_query(query, params)

    if not products:
        render_empty_state("No products match the selected criteria.", "Try adjusting your search terms or filters.", "📦")
    else:
        df = pd.DataFrame(products)
        df["Status"] = df["is_active"].apply(lambda x: "🟢 Active" if x == 1 else "🔴 Inactive")
        df["Stock Alert"] = df.apply(
            lambda r: "🔴 OUT OF STOCK" if r["current_stock"] == 0 else ("⚠️ LOW STOCK" if r["current_stock"] <= r["reorder_level"] else "✅ HEALTHY"), axis=1
        )
        df["Cost (₹)"] = df["cost_price"].apply(format_currency)
        df["Selling (₹)"] = df["selling_price"].apply(format_currency)

        df_display = df[[
            "sku", "name", "category_name", "Cost (₹)", "Selling (₹)", 
            "unit", "current_stock", "reorder_level", "Stock Alert", "Status"
        ]]
        df_display.columns = [
            "Product Code", "Product Name", "Category", "Cost Price", "Selling Price",
            "Unit", "Stock On Hand", "Reorder Level", "Stock Alert", "Status"
        ]

        paginated_df = paginate_dataframe(df_display, page_size=50, key="prod_table")
        st.dataframe(paginated_df, use_container_width=True, hide_index=True)

        # ----------------------------------------------------------------------
        # 3. Selected Product Actions: Edit, Delete & Complete Transaction History
        # ----------------------------------------------------------------------
        st.markdown("---")
        render_section_header("Selected Product Master & Transaction Inspector", "Inspect detailed margins, inbound procurement, outbound sales, and stock movements", "⚙️")
        
        prod_lookup = {f"{p['sku']} - {p['name']} (Stock: {p['current_stock']} {p['unit']})": p for p in products}
        sel_key = st.selectbox("Select Product to Inspect or Modify", list(prod_lookup.keys()), key="edit_prod_select")
        sel_prod = prod_lookup[sel_key]

        sub_tab1, sub_tab2, sub_tab3 = st.tabs(["✏️ Edit & Manage Product", "🔍 Procurement & Sales History", "📜 Stock Movement Ledger"])

        # Tab 1: Edit & Delete
        with sub_tab1:
            col_edit, col_danger = st.columns([2, 1])
            with col_edit:
                with st.form("edit_product_form"):
                    st.markdown(f"**Editing Product:** `{html.escape(sel_prod['sku'])} - {html.escape(sel_prod['name'])}`")
                    e_col1, e_col2 = st.columns(2)
                    with e_col1:
                        st.text_input(
                            "Product Code",
                            value=sel_prod["sku"],
                            disabled=True,
                            help="Product codes cannot be modified to preserve historical order records and relational data integrity."
                        )
                        e_name = st.text_input("Product Name *", value=sel_prod["name"])
                        
                        cat_ids = [c["id"] for c in categories]
                        default_idx = cat_ids.index(sel_prod["category_id"]) if sel_prod["category_id"] in cat_ids else 0
                        e_cat_id = st.selectbox(
                            "Category *",
                            options=[c["id"] for c in categories],
                            format_func=lambda x: next((c["name"] for c in categories if c["id"] == x), ""),
                            index=default_idx
                        )
                        e_unit = st.text_input("Unit of Measure", value=sel_prod["unit"])

                    with e_col2:
                        e_cost = st.number_input("Cost Price (₹) *", value=float(sel_prod["cost_price"]), min_value=0.0, step=50.0)
                        e_sell = st.number_input("Selling Price (₹) *", value=float(sel_prod["selling_price"]), min_value=0.0, step=50.0)
                        e_reorder = st.number_input("Reorder Level Threshold *", value=int(sel_prod["reorder_level"]), min_value=0, step=1)
                        e_active = st.checkbox("Active Status", value=bool(sel_prod["is_active"]))

                    e_desc = st.text_area("Product Description", value=sel_prod["description"] or "")
                    update_p_btn = st.form_submit_button("Save Product Changes", type="primary", use_container_width=True)

                    if update_p_btn:
                        if not e_name.strip():
                            st.error("Product name is required.")
                        else:
                            with st.spinner("Updating product details..."):
                                db.execute_update(
                                    """
                                    UPDATE products 
                                    SET name = %s, category_id = %s, description = %s,
                                        cost_price = %s, selling_price = %s, reorder_level = %s,
                                        unit = %s, is_active = %s
                                    WHERE id = %s
                                    """,
                                    (
                                        e_name.strip(), e_cat_id, e_desc.strip(),
                                        Decimal(str(e_cost)), Decimal(str(e_sell)), int(e_reorder),
                                        e_unit.strip(), 1 if e_active else 0, sel_prod["id"]
                                    )
                                )
                                db.execute_update(
                                    "UPDATE inventory SET reorder_point = %s WHERE product_id = %s",
                                    (int(e_reorder), sel_prod["id"])
                                )
                                st.toast(f"Product '{e_name}' (Code: {sel_prod['sku']}) updated successfully!", icon="✅")
                                st.rerun()

            with col_danger:
                st.markdown("**Data Integrity & Deletion**")
                po_count = db.execute_one("SELECT COUNT(*) as count FROM purchase_order_items WHERE product_id = %s", (sel_prod["id"],))["count"]
                so_count = db.execute_one("SELECT COUNT(*) as count FROM sales_order_items WHERE product_id = %s", (sel_prod["id"],))["count"]
                has_history = (po_count > 0 or so_count > 0 or int(sel_prod["current_stock"]) > 0)

                if has_history:
                    st.warning(
                        f"This product is referenced in **{po_count} PO item(s)** and **{so_count} SO item(s)** (Current Stock: {sel_prod['current_stock']} {sel_prod['unit']}). "
                        "To protect relational foreign keys and financial auditability, it cannot be permanently deleted. "
                        "Deactivate the product above to hide it from new purchase and sales orders."
                    )
                else:
                    st.info("This product has zero order history and can be safely deleted permanently.")
                    confirm_del = st.checkbox("I confirm I want to permanently delete this product", key=f"conf_del_prod_{sel_prod['id']}")
                    if st.button("Delete Product Permanently", type="primary", use_container_width=True, disabled=not confirm_del):
                        with st.spinner("Deleting product master..."):
                            try:
                                with db.get_db_transaction() as (cursor, conn):
                                    cursor.execute("DELETE FROM inventory WHERE product_id = %s", (sel_prod["id"],))
                                    cursor.execute("DELETE FROM stock_movements WHERE product_id = %s", (sel_prod["id"],))
                                    cursor.execute("DELETE FROM products WHERE id = %s", (sel_prod["id"],))
                                st.toast(f"Product '{sel_prod['name']}' deleted permanently.", icon="✅")
                                st.rerun()
                            except Exception as e:
                                logger.error(f"Cannot delete product: {e}", exc_info=True)
                                st.error("Cannot delete product due to existing relational dependencies.")

        # Tab 2: Procurement & Sales History
        with sub_tab2:
            p_info = db.execute_one(
                """
                SELECT p.*, c.name as category_name, COALESCE(i.quantity_on_hand, 0) as stock_qty
                FROM products p
                JOIN categories c ON p.category_id = c.id
                LEFT JOIN inventory i ON p.id = i.product_id
                WHERE p.id = %s
                """,
                (sel_prod["id"],)
            )

            margin = ((p_info['selling_price'] - p_info['cost_price']) / p_info['selling_price'] * 100) if p_info['selling_price'] > 0 else 0
            unit_profit = p_info['selling_price'] - p_info['cost_price']
            
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                render_metric_card("Stock on Hand", f"{p_info['stock_qty']} {p_info['unit']}", f"Reorder Threshold: {p_info['reorder_level']}", "📦", "blue")
            with c2:
                render_metric_card("Unit Cost Price", format_currency(p_info['cost_price']), "Procurement basis", "💵", "purple")
            with c3:
                render_metric_card("Unit Selling Price", format_currency(p_info['selling_price']), "Standard catalogue rate", "🏷️", "green")
            with c4:
                render_metric_card("Gross Margin", f"{margin:.1f}%", f"+{format_currency(unit_profit)} per unit", "📊", "amber")

            st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)
            col_po, col_so = st.columns(2)
            with col_po:
                render_section_header("Inbound Purchase Orders", None, "📥")
                po_history = db.execute_query(
                    """
                    SELECT 
                        po.po_number, 
                        s.name as supplier_name, 
                        poi.quantity_ordered, 
                        poi.quantity_received, 
                        poi.unit_cost, 
                        po.order_date, 
                        po.status
                    FROM purchase_order_items poi
                    JOIN purchase_orders po ON poi.purchase_order_id = po.id
                    JOIN suppliers s ON po.supplier_id = s.id
                    WHERE poi.product_id = %s
                    ORDER BY po.order_date DESC
                    """,
                    (sel_prod["id"],)
                )
                if po_history:
                    df_po_h = pd.DataFrame(po_history)
                    df_po_h["Unit Cost"] = df_po_h["unit_cost"].apply(format_currency)
                    df_po_h_disp = df_po_h[["po_number", "supplier_name", "quantity_ordered", "quantity_received", "Unit Cost", "order_date", "status"]]
                    df_po_h_disp.columns = ["PO #", "Supplier", "Ordered", "Received", "Cost Price", "Date", "Status"]
                    paginated_po = paginate_dataframe(df_po_h_disp, page_size=50, key=f"prod_po_h_{sel_prod['id']}")
                    st.dataframe(paginated_po, use_container_width=True, hide_index=True)
                else:
                    render_empty_state("No purchase orders recorded for this product.", icon="📥")

            with col_so:
                render_section_header("Outbound Sales Orders", None, "📤")
                so_history = db.execute_query(
                    """
                    SELECT 
                        so.order_number, 
                        c.name as customer_name, 
                        soi.quantity, 
                        soi.unit_price, 
                        so.order_date, 
                        so.status
                    FROM sales_order_items soi
                    JOIN sales_orders so ON soi.sales_order_id = so.id
                    JOIN customers c ON so.customer_id = c.id
                    WHERE soi.product_id = %s
                    ORDER BY so.order_date DESC
                    """,
                    (sel_prod["id"],)
                )
                if so_history:
                    df_so_h = pd.DataFrame(so_history)
                    df_so_h["Unit Price"] = df_so_h["unit_price"].apply(format_currency)
                    df_so_h_disp = df_so_h[["order_number", "customer_name", "quantity", "Unit Price", "order_date", "status"]]
                    df_so_h_disp.columns = ["Order #", "Customer", "Qty", "Selling Price", "Date", "Status"]
                    paginated_so = paginate_dataframe(df_so_h_disp, page_size=50, key=f"prod_so_h_{sel_prod['id']}")
                    st.dataframe(paginated_so, use_container_width=True, hide_index=True)
                else:
                    render_empty_state("No sales orders recorded for this product.", icon="📤")

        # Tab 3: Stock Movement Ledger
        with sub_tab3:
            render_section_header("Audit Trail: Stock Movements for this SKU", None, "📜")
            p_movements = db.execute_query(
                """
                SELECT 
                    sm.created_at,
                    sm.movement_type,
                    sm.quantity,
                    sm.balance_after,
                    sm.reference_type,
                    sm.notes,
                    COALESCE(a.username, 'System') as admin_name
                FROM stock_movements sm
                LEFT JOIN admins a ON sm.created_by_admin_id = a.id
                WHERE sm.product_id = %s
                ORDER BY sm.created_at DESC
                """,
                (sel_prod["id"],)
            )
            if p_movements:
                df_pm = pd.DataFrame(p_movements)
                df_pm["Direction"] = df_pm["movement_type"].apply(
                    lambda t: "🟢 IN (+)" if t in ["PO_RECEIPT", "ADJUSTMENT_ADD", "INITIAL_STOCK", "RETURN_IN"] else "🔴 OUT (-)"
                )
                df_pm_disp = df_pm[["created_at", "Direction", "movement_type", "quantity", "balance_after", "reference_type", "notes", "admin_name"]]
                df_pm_disp.columns = ["Timestamp", "Flow", "Movement Type", "Qty", "Balance After", "Reference", "Notes", "Logged By"]
                paginated_pm = paginate_dataframe(df_pm_disp, page_size=50, key=f"prod_sm_h_{sel_prod['id']}")
                st.dataframe(paginated_pm, use_container_width=True, hide_index=True)
            else:
                render_empty_state("No stock movements recorded for this product.", icon="📜")
