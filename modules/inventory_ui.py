"""
Inventory Management Module: Real-Time Stock Tracking, Low Stock Alerts,
Mandatory-Reason Stock Adjustments, and Complete Audit Trail Movements.
"""

from decimal import Decimal
import logging
import streamlit as st
import pandas as pd
import database as db
from modules.ui_components import (
    render_page_header,
    render_metric_card,
    render_section_header,
    render_empty_state,
    paginate_dataframe,
    format_currency,
    format_inr_compact
)

logger = logging.getLogger("siom.inventory")


def render_inventory_page():
    render_page_header(
        title="Stock & Warehouse Inventory",
        subtitle="Monitor real-time warehouse stock levels, low/out-of-stock alerts, adjustments, and movement audit logs.",
        icon="📦"
    )

    tab1, tab2, tab3, tab4 = st.tabs([
        "Current Stock", 
        "Low & Out of Stock", 
        "Stock Adjustment", 
        "Stock Movements"
    ])

    # --------------------------------------------------------------------------
    # Tab 1: Current Stock on Hand
    # --------------------------------------------------------------------------
    with tab1:
        st.markdown('<div class="siom-filter-panel">', unsafe_allow_html=True)
        col_s, col_c, col_stat = st.columns([2, 1, 1])
        with col_s:
            search_inv = st.text_input("🔍 Search Stock", placeholder="Search SKU or Product Name...")
        with col_c:
            cats = db.execute_query("SELECT id, name FROM categories WHERE is_active = 1 ORDER BY name ASC")
            cat_filter_map = {"All Categories": None}
            for c in cats:
                cat_filter_map[c["name"]] = c["id"]
            sel_cat_filter = st.selectbox("Category", list(cat_filter_map.keys()), key="inv_cat_filter")
        with col_stat:
            stock_filter = st.selectbox("Stock Level", ["All Levels", "In Stock (>0)", "Low Stock Only", "Out of Stock (0)"])
        st.markdown('</div>', unsafe_allow_html=True)

        query = """
            SELECT 
                p.id AS product_id,
                p.sku,
                p.name,
                c.name AS category_name,
                p.cost_price,
                p.selling_price,
                p.unit,
                COALESCE(i.quantity_on_hand, 0) AS quantity_on_hand,
                COALESCE(i.reorder_point, p.reorder_level) AS reorder_point,
                (COALESCE(i.quantity_on_hand, 0) * p.cost_price) AS inventory_valuation,
                i.last_updated_at
            FROM products p
            JOIN categories c ON p.category_id = c.id
            LEFT JOIN inventory i ON p.id = i.product_id
            WHERE p.is_active = 1
        """
        params = []

        if search_inv:
            query += " AND (p.sku LIKE %s OR p.name LIKE %s)"
            params.extend([f"%{search_inv}%", f"%{search_inv}%"])

        if cat_filter_map[sel_cat_filter] is not None:
            query += " AND p.category_id = %s"
            params.append(cat_filter_map[sel_cat_filter])

        if stock_filter == "In Stock (>0)":
            query += " AND COALESCE(i.quantity_on_hand, 0) > 0"
        elif stock_filter == "Low Stock Only":
            query += " AND COALESCE(i.quantity_on_hand, 0) <= COALESCE(i.reorder_point, p.reorder_level) AND COALESCE(i.quantity_on_hand, 0) > 0"
        elif stock_filter == "Out of Stock (0)":
            query += " AND COALESCE(i.quantity_on_hand, 0) = 0"

        query += " ORDER BY p.name ASC"
        inventory_items = db.execute_query(query, params)

        total_items = len(inventory_items)
        total_units = sum(item["quantity_on_hand"] for item in inventory_items)
        total_val = sum(Decimal(str(item["inventory_valuation"])) for item in inventory_items)
        low_stock_count = sum(1 for item in inventory_items if item["quantity_on_hand"] <= item["reorder_point"])

        render_section_header("Stock Valuation Summary", "Aggregated physical quantities and asset balances", "📊")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            render_metric_card("Catalog SKUs", total_items, "Active items in scope", "📦", "blue")
        with c2:
            render_metric_card("Total Physical Units", f"{total_units:,}", "Across warehouse locations", "🔢", "purple")
        with c3:
            render_metric_card("Inventory Valuation", format_inr_compact(total_val), f"Exact: {format_currency(total_val)}", "💵", "green")
        with c4:
            render_metric_card("Low Stock Items", low_stock_count, "Require restocking", "⚠️", "red" if low_stock_count > 0 else "blue")

        st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)
        if not inventory_items:
            render_empty_state("No inventory records found matching the criteria.", "Try clearing filters.", "📦")
        else:
            df_inv = pd.DataFrame(inventory_items)
            df_inv["Health"] = df_inv.apply(
                lambda r: "🔴 OUT OF STOCK" if r["quantity_on_hand"] == 0 else ("⚠️ LOW STOCK" if r["quantity_on_hand"] <= r["reorder_point"] else "✅ HEALTHY"), axis=1
            )
            df_inv["Cost (₹)"] = df_inv["cost_price"].apply(format_currency)
            df_inv["Valuation (₹)"] = df_inv["inventory_valuation"].apply(format_currency)

            df_inv_disp = df_inv[[
                "sku", "name", "category_name", "quantity_on_hand", 
                "reorder_point", "unit", "Cost (₹)", "Valuation (₹)", "Health"
            ]]
            df_inv_disp.columns = [
                "SKU", "Product Name", "Category", "Stock on Hand",
                "Reorder Threshold", "Unit", "Cost Price", "Stock Valuation", "Status"
            ]
            paginated_inv = paginate_dataframe(df_inv_disp, page_size=50, key="inv_table")
            st.dataframe(paginated_inv, use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # Tab 2: Low Stock Alerts
    # --------------------------------------------------------------------------
    with tab2:
        render_section_header("Critical Inventory Reorder Alerts", "Products whose stock on hand is at or below defined minimum threshold", "⚠️")

        low_stock_query = """
            SELECT 
                p.id,
                p.sku,
                p.name,
                c.name AS category_name,
                COALESCE(i.quantity_on_hand, 0) AS current_stock,
                COALESCE(i.reorder_point, p.reorder_level) AS reorder_level,
                GREATEST(10, (COALESCE(i.reorder_point, p.reorder_level) * 2 - COALESCE(i.quantity_on_hand, 0))) AS suggested_reorder_qty,
                p.cost_price,
                p.unit
            FROM products p
            JOIN categories c ON p.category_id = c.id
            LEFT JOIN inventory i ON p.id = i.product_id
            WHERE p.is_active = 1 AND COALESCE(i.quantity_on_hand, 0) <= COALESCE(i.reorder_point, p.reorder_level)
            ORDER BY COALESCE(i.quantity_on_hand, 0) ASC
        """
        low_items = db.execute_query(low_stock_query)

        if not low_items:
            st.success("✅ All inventory stock levels are healthy. No items are currently below reorder thresholds.")
        else:
            st.warning(f"🚨 Found **{len(low_items)}** product(s) requiring procurement replenishment.")
            df_low = pd.DataFrame(low_items)
            df_low["Restock Cost"] = (df_low["suggested_reorder_qty"] * df_low["cost_price"]).apply(format_currency)
            df_low["Cost Price"] = df_low["cost_price"].apply(format_currency)
            df_low["Status"] = df_low["current_stock"].apply(lambda q: "🔴 OUT OF STOCK" if q == 0 else "⚠️ LOW STOCK")

            df_low_disp = df_low[["sku", "name", "category_name", "current_stock", "reorder_level", "suggested_reorder_qty", "unit", "Cost Price", "Restock Cost", "Status"]]
            df_low_disp.columns = ["SKU", "Product Name", "Category", "Current Stock", "Reorder Threshold", "Suggested Order Qty", "Unit", "Unit Cost", "Est. Restock Cost", "Alert Level"]
            paginated_low = paginate_dataframe(df_low_disp, page_size=50, key="low_stock_table")
            st.dataframe(paginated_low, use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # Tab 3: Manual Stock Adjustment (Transaction-Safe)
    # --------------------------------------------------------------------------
    with tab3:
        render_section_header("Manual Warehouse Stock Adjustment", "Every manual adjustment requires a mandatory reason and records an audit log entry", "⚡")

        all_active_prods = db.execute_query(
            """
            SELECT p.id, p.sku, p.name, p.unit, COALESCE(i.quantity_on_hand, 0) as stock_qty
            FROM products p
            LEFT JOIN inventory i ON p.id = i.product_id
            WHERE p.is_active = 1
            ORDER BY p.name ASC
            """
        )

        if not all_active_prods:
            render_empty_state("No active products found to adjust.", icon="📦")
        else:
            prod_choice = {f"{p['sku']} - {p['name']} (Current Stock: {p['stock_qty']} {p['unit']})": p for p in all_active_prods}
            sel_p_choice = st.selectbox("Select Product to Adjust", list(prod_choice.keys()), key="adjust_prod_sel")
            selected_item = prod_choice[sel_p_choice]
            current_qty = selected_item["stock_qty"]
            prod_id = selected_item["id"]

            with st.form("manual_adjustment_form"):
                col_a1, col_a2 = st.columns(2)
                with col_a1:
                    adj_type = st.radio(
                        "Adjustment Action *",
                        ["Increase Stock (Add Inventory)", "Decrease Stock (Damage / Loss / Correction)"]
                    )
                    adj_qty = st.number_input("Adjustment Quantity *", min_value=1, value=1, step=1)

                with col_a2:
                    reason_category = st.selectbox(
                        "Reason Category *",
                        [
                            "Physical Inventory Count Discrepancy",
                            "Damaged Goods Write-off",
                            "Customer Return to Stock",
                            "Supplier Return / Defect",
                            "Internal Usage / Demonstration",
                            "Warehouse Relocation Re-count",
                            "Other Specific Reason"
                        ]
                    )
                    detailed_notes = st.text_area("Detailed Reason Notes *", placeholder="Explain the exact operational justification for this stock adjustment...")

                confirm_adj = st.checkbox("I confirm that this stock adjustment is accurate and authorized", key="conf_manual_adj")
                submit_adj_btn = st.form_submit_button("Apply Stock Adjustment", type="primary", use_container_width=True)

                if submit_adj_btn:
                    if not detailed_notes or not detailed_notes.strip():
                        st.error("A detailed reason note is mandatory for all manual adjustments.")
                    elif not confirm_adj:
                        st.error("Please confirm the adjustment authorization checkbox before proceeding.")
                    else:
                        is_addition = "Increase" in adj_type
                        with st.spinner("Applying stock adjustment..."):
                            try:
                                admin_id = st.session_state.get("admin_id")
                                m_type = "ADJUSTMENT_ADD" if is_addition else "ADJUSTMENT_SUB"
                                full_reason = f"[{reason_category}] {detailed_notes.strip()}"

                                with db.get_db_transaction() as (cursor, conn):
                                    if is_addition:
                                        cursor.execute(
                                            """
                                            INSERT INTO inventory (product_id, quantity_on_hand, reorder_point)
                                            VALUES (%s, %s, 10)
                                            ON DUPLICATE KEY UPDATE quantity_on_hand = quantity_on_hand + VALUES(quantity_on_hand)
                                            """,
                                            (prod_id, adj_qty)
                                        )
                                    else:
                                        cursor.execute(
                                            """
                                            UPDATE inventory 
                                            SET quantity_on_hand = quantity_on_hand - %s 
                                            WHERE product_id = %s AND quantity_on_hand >= %s
                                            """,
                                            (adj_qty, prod_id, adj_qty)
                                        )
                                        if cursor.rowcount == 0:
                                            raise ValueError(
                                                f"Cannot reduce stock by {adj_qty}. Current stock on hand is insufficient."
                                            )

                                    cursor.execute(
                                        "SELECT quantity_on_hand FROM inventory WHERE product_id = %s",
                                        (prod_id,)
                                    )
                                    new_balance = cursor.fetchone()["quantity_on_hand"]

                                    cursor.execute(
                                        """
                                        INSERT INTO stock_movements 
                                        (product_id, movement_type, quantity, balance_after, reference_type, reference_id, notes, created_by_admin_id)
                                        VALUES (%s, %s, %s, %s, 'MANUAL_ADJUSTMENT', NULL, %s, %s)
                                        """,
                                        (prod_id, m_type, adj_qty, new_balance, full_reason, admin_id)
                                    )

                                st.toast(f"Stock successfully adjusted! New balance: {new_balance} {selected_item['unit']}.", icon="✅")
                                st.rerun()
                            except ValueError as val_err:
                                logger.warning(f"Stock adjustment validation error: {val_err}")
                                st.error(str(val_err))
                            except Exception as ex:
                                logger.error(f"Failed to adjust stock: {ex}", exc_info=True)
                                st.error("A database error occurred while applying the stock adjustment.")

    # --------------------------------------------------------------------------
    # Tab 4: Stock Movement Audit History
    # --------------------------------------------------------------------------
    with tab4:
        render_section_header("Stock Movements Audit Log", "Immutable ledger of all receipts, fulfillments, adjustments, and returns", "📜")

        st.markdown('<div class="siom-filter-panel">', unsafe_allow_html=True)
        col_m1, col_m2 = st.columns([2, 1])
        with col_m1:
            m_search = st.text_input("Filter by Product SKU/Name or Reference", key="sm_search")
        with col_m2:
            m_type_filter = st.selectbox(
                "Movement Type Filter",
                ["All Types", "PO_RECEIPT", "SO_FULFILLMENT", "ADJUSTMENT_ADD", "ADJUSTMENT_SUB", "INITIAL_STOCK", "RETURN_IN", "RETURN_OUT"]
            )
        st.markdown('</div>', unsafe_allow_html=True)

        sm_query = """
            SELECT 
                sm.id,
                sm.created_at,
                p.sku,
                p.name AS product_name,
                sm.movement_type,
                sm.quantity,
                sm.balance_after,
                sm.reference_type,
                sm.reference_id,
                sm.notes,
                COALESCE(a.username, 'System') AS logged_by
            FROM stock_movements sm
            JOIN products p ON sm.product_id = p.id
            LEFT JOIN admins a ON sm.created_by_admin_id = a.id
            WHERE 1=1
        """
        sm_params = []

        if m_search:
            sm_query += " AND (p.sku LIKE %s OR p.name LIKE %s OR sm.notes LIKE %s)"
            sm_params.extend([f"%{m_search}%", f"%{m_search}%", f"%{m_search}%"])

        if m_type_filter != "All Types":
            sm_query += " AND sm.movement_type = %s"
            sm_params.append(m_type_filter)

        sm_query += " ORDER BY sm.created_at DESC LIMIT 250"
        movements = db.execute_query(sm_query, sm_params)

        if not movements:
            render_empty_state("No stock movements recorded matching the criteria.", icon="📜")
        else:
            df_sm = pd.DataFrame(movements)
            df_sm["Direction"] = df_sm["movement_type"].apply(
                lambda t: "🟢 IN (+)" if t in ["PO_RECEIPT", "ADJUSTMENT_ADD", "INITIAL_STOCK", "RETURN_IN"] else "🔴 OUT (-)"
            )
            df_sm_disp = df_sm[[
                "created_at", "sku", "product_name", "Direction", "movement_type", 
                "quantity", "balance_after", "reference_type", "notes", "logged_by"
            ]]
            df_sm_disp.columns = [
                "Timestamp", "SKU", "Product Name", "Flow", "Type", 
                "Qty", "Balance After", "Reference Source", "Notes / Justification", "Admin User"
            ]
            paginated_movements = paginate_dataframe(df_sm_disp, page_size=50, key="sm_table")
            st.dataframe(paginated_movements, use_container_width=True, hide_index=True)
