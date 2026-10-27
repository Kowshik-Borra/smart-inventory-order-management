"""
Purchase Orders & Goods Receipt Module:
Multi-item PO creation, status workflows, transaction-safe receiving, and audit updates.
"""

from datetime import date, timedelta
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

logger = logging.getLogger("siom.purchase_orders")


def render_purchase_orders_page():
    render_page_header(
        title="Purchase Orders & Inbound Receiving",
        subtitle="Manage procurement lifecycles from draft requisition to physical warehouse goods receipt.",
        icon="🛒"
    )

    tab1, tab2, tab3 = st.tabs(["📋 Purchase Orders List", "➕ Create Purchase Order", "📥 Receive Goods (Inbound)"])

    # --------------------------------------------------------------------------
    # Tab 1: Purchase Orders Listing & Details
    # --------------------------------------------------------------------------
    with tab1:
        st.markdown('<div class="siom-filter-panel">', unsafe_allow_html=True)
        col_s, col_stat, col_d = st.columns([2, 1, 1])
        with col_s:
            search_po = st.text_input("🔍 Search PO Number or Supplier", placeholder="e.g. PO-2026 or TechWorld", key="po_search")
        with col_stat:
            status_po = st.selectbox(
                "Status Filter",
                ["All Statuses", "Draft", "Ordered", "Partially Received", "Received", "Cancelled"],
                key="po_stat_f"
            )
        with col_d:
            date_filter = st.date_input(
                "Date Range",
                value=[date.today() - timedelta(days=365), date.today()],
                key="po_date_range"
            )
        st.markdown('</div>', unsafe_allow_html=True)

        if isinstance(date_filter, (list, tuple)) and len(date_filter) == 2:
            s_date, e_date = date_filter
        else:
            s_date, e_date = date.today() - timedelta(days=365), date.today()

        query = """
            SELECT 
                po.id,
                po.po_number,
                s.name AS supplier_name,
                po.order_date,
                po.expected_date,
                po.status,
                po.subtotal,
                po.tax_amount,
                po.total_amount,
                po.notes,
                COUNT(poi.id) AS item_count
            FROM purchase_orders po
            JOIN suppliers s ON po.supplier_id = s.id
            LEFT JOIN purchase_order_items poi ON po.id = poi.purchase_order_id
            WHERE po.order_date BETWEEN %s AND %s
        """
        params = [s_date, e_date]
        if search_po:
            query += " AND (po.po_number LIKE %s OR s.name LIKE %s)"
            params.extend([f"%{search_po}%", f"%{search_po}%"])

        if status_po != "All Statuses":
            query += " AND po.status = %s"
            params.append(status_po)

        query += " GROUP BY po.id ORDER BY po.order_date DESC, po.id DESC"
        po_list = db.execute_query(query, params)

        # Quick summary stats
        if po_list:
            total_po_val = sum(Decimal(str(p["total_amount"])) for p in po_list if p["status"] != "Cancelled")
            tot_po_cnt = len(po_list)
            rec_cnt = sum(1 for p in po_list if p["status"] == "Received")
            pend_cnt = sum(1 for p in po_list if p["status"] in ("Ordered", "Partially Received"))

            k1, k2, k3, k4 = st.columns(4)
            with k1:
                render_metric_card("Total Procurement Spend", format_inr_compact(total_po_val), f"Across {tot_po_cnt} Requisitions", "💵", "blue")
            with k2:
                render_metric_card("Active PO Count", tot_po_cnt, "Filtered Requisitions", "🛒", "purple")
            with k3:
                render_metric_card("Completed / Received", rec_cnt, "Fulfilled Orders", "✅", "green")
            with k4:
                render_metric_card("Pending Inbound Delivery", pend_cnt, "Awaiting Goods Receipt", "⏳", "amber" if pend_cnt > 0 else "green")
            st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)

        if not po_list:
            render_empty_state("No purchase orders found matching the criteria.", "Create a new purchase order or adjust filters.", "🛒")
        else:
            df_po = pd.DataFrame(po_list)
            df_po["Subtotal (₹)"] = df_po["subtotal"].apply(format_currency)
            df_po["Tax (₹)"] = df_po["tax_amount"].apply(format_currency)
            df_po["Total Amount (₹)"] = df_po["total_amount"].apply(format_currency)
            
            df_po_disp = df_po[[
                "id", "po_number", "supplier_name", "order_date", "expected_date", 
                "status", "item_count", "Subtotal (₹)", "Tax (₹)", "Total Amount (₹)"
            ]]
            df_po_disp.columns = [
                "ID", "PO Number", "Supplier", "Order Date", "Expected Date", 
                "Status", "Items", "Subtotal", "Tax", "Total Amount"
            ]
            paginated_po = paginate_dataframe(df_po_disp, page_size=50, key="po_list_table")
            st.dataframe(paginated_po, use_container_width=True, hide_index=True)

            st.markdown("---")
            render_section_header("Purchase Order Inspector & Workflow", "View line items and transition order lifecycles", "🔎")
            po_dict = {f"{p['po_number']} - {p['supplier_name']} ({p['status']})": p for p in po_list}
            sel_po_k = st.selectbox("Select Purchase Order to Inspect", list(po_dict.keys()), key="po_inspect_sel")
            selected_po = po_dict[sel_po_k]

            po_id = selected_po["id"]
            items = db.execute_query(
                """
                SELECT 
                    poi.id,
                    p.sku,
                    p.name AS product_name,
                    poi.quantity_ordered,
                    poi.quantity_received,
                    poi.unit_cost,
                    poi.line_total
                FROM purchase_order_items poi
                JOIN products p ON poi.product_id = p.id
                WHERE poi.purchase_order_id = %s
                """,
                (po_id,)
            )

            c_po1, c_po2, c_po3 = st.columns(3)
            with c_po1:
                st.info(f"**PO Number:** `{selected_po['po_number']}`\n\n**Supplier:** {selected_po['supplier_name']}")
            with c_po2:
                st.info(f"**Order Date:** {selected_po['order_date']}\n\n**Expected Delivery:** {selected_po['expected_date'] or 'N/A'}")
            with c_po3:
                st.info(f"**Current Status:** `{selected_po['status']}`\n\n**Total Gross Value:** {format_currency(selected_po['total_amount'])}")

            if items:
                st.markdown("##### Line Items Requisitioned")
                df_it = pd.DataFrame(items)
                df_it["Unit Cost (₹)"] = df_it["unit_cost"].apply(format_currency)
                df_it["Line Total (₹)"] = df_it["line_total"].apply(format_currency)
                df_it_disp = df_it[["id", "sku", "product_name", "quantity_ordered", "quantity_received", "Unit Cost (₹)", "Line Total (₹)"]]
                df_it_disp.columns = ["Item ID", "SKU", "Product Name", "Ordered Qty", "Received Qty", "Unit Cost", "Line Total"]
                st.dataframe(df_it_disp, use_container_width=True, hide_index=True)

            # Workflow state transitions (Strict State Machine)
            current_status = selected_po["status"]
            allowed_next = db.PURCHASE_ORDER_TRANSITIONS.get(current_status, [])

            if not allowed_next:
                st.info(f"Purchase Order `{selected_po['po_number']}` is in terminal status **{current_status}**. No further state changes are permitted.")
            elif current_status == "Draft":
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("Mark Ordered & Transmit to Vendor", type="primary", use_container_width=True):
                        with st.spinner("Updating PO status..."):
                            try:
                                rows = db.execute_update("UPDATE purchase_orders SET status = 'Ordered' WHERE id = %s AND status = 'Draft'", (po_id,))
                                if rows == 0:
                                    st.error("PO status could not be changed. It may have already been updated.")
                                else:
                                    st.toast("PO marked as Ordered and transmitted.", icon="✅")
                                    st.rerun()
                            except Exception as ex:
                                logger.error(f"Error updating PO status: {ex}", exc_info=True)
                                st.error("Failed to update purchase order status.")
                with col_btn2:
                    confirm_cancel_draft = st.checkbox("Confirm cancellation", key=f"conf_po_draft_{po_id}")
                    if st.button("Cancel Draft PO", use_container_width=True, disabled=not confirm_cancel_draft):
                        with st.spinner("Cancelling PO..."):
                            try:
                                rows = db.execute_update("UPDATE purchase_orders SET status = 'Cancelled' WHERE id = %s AND status = 'Draft'", (po_id,))
                                if rows == 0:
                                    st.error("PO could not be cancelled. It may have already been updated.")
                                else:
                                    st.toast("Draft PO Cancelled.", icon="ℹ️")
                                    st.rerun()
                            except Exception as ex:
                                logger.error(f"Error cancelling PO: {ex}", exc_info=True)
                                st.error("Failed to cancel purchase order.")

            elif current_status == "Ordered":
                confirm_cancel_ord = st.checkbox("Confirm cancellation of active PO", key=f"conf_po_ord_{po_id}")
                if st.button("Cancel Purchase Order", use_container_width=True, disabled=not confirm_cancel_ord):
                    with st.spinner("Cancelling PO..."):
                        try:
                            rows = db.execute_update("UPDATE purchase_orders SET status = 'Cancelled' WHERE id = %s AND status = 'Ordered'", (po_id,))
                            if rows == 0:
                                st.error("PO could not be cancelled. It may have already been received or updated.")
                            else:
                                st.toast("Purchase Order Cancelled.", icon="ℹ️")
                                st.rerun()
                        except Exception as ex:
                            logger.error(f"Error cancelling PO: {ex}", exc_info=True)
                            st.error("Failed to cancel purchase order.")

    # --------------------------------------------------------------------------
    # Tab 2: Create Purchase Order (Multi-Item Requisition)
    # --------------------------------------------------------------------------
    with tab2:
        render_section_header("Create New Purchase Requisition", "Build multi-item purchase orders with automatic tax & subtotal calculations", "➕")
        suppliers = db.execute_query("SELECT id, name FROM suppliers WHERE is_active = 1 ORDER BY name ASC")
        products = db.execute_query("SELECT id, sku, name, cost_price FROM products WHERE is_active = 1 ORDER BY name ASC")

        if not suppliers:
            st.warning("Please register at least one active supplier before drafting purchase orders.")
            return
        if not products:
            st.warning("Please create products in the catalog before creating purchase orders.")
            return

        # Session state for line items
        if "po_line_items" not in st.session_state:
            st.session_state.po_line_items = []

        po_col1, po_col2, po_col3 = st.columns(3)
        with po_col1:
            supp_map = {s["name"]: s["id"] for s in suppliers}
            sel_supp_label = st.selectbox("Select Supplier *", list(supp_map.keys()), key="po_supp_sel")
            supp_id = supp_map[sel_supp_label]
        with po_col2:
            po_order_date = st.date_input("Order Date", value=date.today(), key="po_order_date")
        with po_col3:
            po_exp_date = st.date_input("Expected Delivery Date", value=date.today() + timedelta(days=7), key="po_exp_date")

        po_notes = st.text_input("PO Notes / Reference", placeholder="e.g. Q3 Restock, Expedited Air Cargo", key="po_notes_input")

        # Line Item Builder
        st.markdown("---")
        st.markdown("##### Add Products to Order")
        li_c1, li_c2, li_c3, li_c4 = st.columns([3, 1, 1, 1])
        with li_c1:
            prod_map = {f"{p['sku']} - {p['name']} (Cost: {format_currency(p['cost_price'])})": p for p in products}
            sel_prod_label = st.selectbox("Product SKU", list(prod_map.keys()), key="po_add_prod_sel")
            sel_prod_obj = prod_map[sel_prod_label]
        with li_c2:
            item_qty = st.number_input("Quantity *", min_value=1, value=10, step=1, key="po_item_qty")
        with li_c3:
            item_cost = st.number_input("Unit Cost (₹) *", min_value=0.0, value=float(sel_prod_obj["cost_price"]), step=50.0, key="po_item_cost")
        with li_c4:
            st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
            if st.button("Add Line Item", key="po_add_item_btn", use_container_width=True):
                existing_item = next((i for i in st.session_state.po_line_items if i["product_id"] == sel_prod_obj["id"]), None)
                if existing_item:
                    existing_item["quantity"] += item_qty
                    existing_item["unit_cost"] = Decimal(str(item_cost))
                    existing_item["line_total"] = Decimal(str(existing_item["quantity"])) * Decimal(str(item_cost))
                else:
                    st.session_state.po_line_items.append({
                        "product_id": sel_prod_obj["id"],
                        "sku": sel_prod_obj["sku"],
                        "name": sel_prod_obj["name"],
                        "quantity": item_qty,
                        "unit_cost": Decimal(str(item_cost)),
                        "line_total": Decimal(str(item_qty)) * Decimal(str(item_cost))
                    })
                st.rerun()

        # Render Line Items Table
        if st.session_state.po_line_items:
            st.markdown("##### Current Order Items")
            lines_df = pd.DataFrame([
                {
                    "SKU": i["sku"],
                    "Product": i["name"],
                    "Quantity": i["quantity"],
                    "Unit Cost (₹)": format_currency(i["unit_cost"]),
                    "Line Total (₹)": format_currency(i["line_total"])
                }
                for i in st.session_state.po_line_items
            ])
            st.dataframe(lines_df, use_container_width=True, hide_index=True)

            subtotal = sum(i["line_total"] for i in st.session_state.po_line_items)
            col_tax, col_tot, col_clr = st.columns([1, 2, 1])
            with col_tax:
                tax_pct = st.number_input("Tax Rate / GST (%)", min_value=0.0, max_value=100.0, value=18.0, step=0.5, key="po_tax_pct")
                tax_amount = subtotal * (Decimal(str(tax_pct)) / Decimal("100"))
            with col_tot:
                total_amount = subtotal + tax_amount
                render_metric_card("Total PO Value", format_currency(total_amount), f"Subtotal: {format_currency(subtotal)} | GST ({tax_pct}%): {format_currency(tax_amount)}", "💵", "blue")
            with col_clr:
                st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
                if st.button("Clear Items", key="po_clear_items", use_container_width=True):
                    st.session_state.po_line_items = []
                    st.rerun()

            # Action Buttons
            st.markdown("---")
            c_save1, c_save2 = st.columns(2)
            with c_save1:
                save_draft = st.button("Save as Draft PO", use_container_width=True)
            with c_save2:
                save_order = st.button("Save & Mark Ordered", type="primary", use_container_width=True)

            if save_draft or save_order:
                status = "Ordered" if save_order else "Draft"

                with st.spinner("Saving purchase order..."):
                    try:
                        with db.get_db_transaction() as (cursor, conn):
                            # Generate race-safe PO Number
                            po_number = db.get_next_document_number(cursor, "PO")

                            cursor.execute(
                                """
                                INSERT INTO purchase_orders 
                                (po_number, supplier_id, order_date, expected_date, status, subtotal, tax_amount, total_amount, notes)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """,
                                (
                                    po_number, supp_id, po_order_date, po_exp_date, status,
                                    subtotal, tax_amount, total_amount, po_notes.strip()
                                )
                            )
                            new_po_id = cursor.lastrowid

                            for item in st.session_state.po_line_items:
                                cursor.execute(
                                    """
                                    INSERT INTO purchase_order_items 
                                    (purchase_order_id, product_id, quantity_ordered, quantity_received, unit_cost, line_total)
                                    VALUES (%s, %s, %s, 0, %s, %s)
                                    """,
                                    (new_po_id, item["product_id"], item["quantity"], item["unit_cost"], item["line_total"])
                                )

                        st.session_state.po_line_items = []
                        st.toast(f"Purchase Order {po_number} created successfully with status {status}!", icon="✅")
                        st.rerun()
                    except Exception as ex:
                        logger.error(f"Error creating PO: {ex}", exc_info=True)
                        st.error("Failed to create purchase order. Please verify input data and try again.")

    # --------------------------------------------------------------------------
    # Tab 3: Receive Goods (Inbound Receipt & Inventory Transaction)
    # --------------------------------------------------------------------------
    with tab3:
        render_section_header("Physical Goods Receipt Processing", "Inspect and receive incoming shipments into warehouse stock safely via transactions", "📥")

        receivable_pos = db.execute_query(
            """
            SELECT po.id, po.po_number, s.name AS supplier_name, po.status, po.order_date
            FROM purchase_orders po
            JOIN suppliers s ON po.supplier_id = s.id
            WHERE po.status IN ('Ordered', 'Partially Received')
            ORDER BY po.order_date ASC
            """
        )

        if not receivable_pos:
            render_empty_state("No purchase orders currently awaiting physical goods receipt.", "All ordered POs have been received.", "📥")
        else:
            rec_map = {f"{r['po_number']} - {r['supplier_name']} ({r['status']})": r for r in receivable_pos}
            sel_rec_k = st.selectbox("Select PO to Receive", list(rec_map.keys()), key="po_receive_sel")
            rec_po = rec_map[sel_rec_k]
            rec_po_id = rec_po["id"]

            po_items = db.execute_query(
                """
                SELECT 
                    poi.id AS item_id,
                    poi.product_id,
                    p.sku,
                    p.name AS product_name,
                    poi.quantity_ordered,
                    poi.quantity_received,
                    (poi.quantity_ordered - poi.quantity_received) AS outstanding_qty,
                    poi.unit_cost,
                    COALESCE(i.quantity_on_hand, 0) AS current_stock
                FROM purchase_order_items poi
                JOIN products p ON poi.product_id = p.id
                LEFT JOIN inventory i ON p.id = i.product_id
                WHERE poi.purchase_order_id = %s
                """,
                (rec_po_id,)
            )

            st.markdown("##### Line Items to Receive")
            with st.form("receive_goods_form"):
                receipt_inputs = {}
                for it in po_items:
                    r_c1, r_c2, r_c3, r_c4 = st.columns([3, 1, 1, 1])
                    with r_c1:
                        st.markdown(f"**{it['sku']}** - {it['product_name']}")
                        st.caption(f"Current Stock: {it['current_stock']} | Unit Cost: {format_currency(it['unit_cost'])}")
                    with r_c2:
                        st.metric("Ordered", it["quantity_ordered"])
                    with r_c3:
                        st.metric("Received", it["quantity_received"])
                    with r_c4:
                        max_rec = it["outstanding_qty"]
                        if max_rec > 0:
                            qty_to_rec = st.number_input(
                                f"Receive Qty (Max {max_rec})",
                                min_value=0,
                                max_value=max_rec,
                                value=max_rec,
                                step=1,
                                key=f"rec_in_{it['item_id']}"
                            )
                            receipt_inputs[it["item_id"]] = (it, qty_to_rec)
                        else:
                            st.success("Fully Received")

                receipt_notes = st.text_input("Receipt / Delivery Note Reference", placeholder="e.g. Courier Docket #884129, Supplier Invoice #991", key="rec_notes")
                confirm_receipt_btn = st.form_submit_button("Confirm Physical Receipt & Update Warehouse Stock", type="primary", use_container_width=True)

                if confirm_receipt_btn:
                    total_receiving_now = sum(qty for _, qty in receipt_inputs.values())
                    if total_receiving_now == 0:
                        st.warning("No quantities specified to receive.")
                    else:
                        admin_id = st.session_state.get("admin_id")
                        with st.spinner("Processing goods receipt transaction..."):
                            try:
                                with db.get_db_transaction() as (cursor, conn):
                                    # Lock and verify PO status to reject receiving on Cancelled / Completed POs
                                    cursor.execute(
                                        "SELECT status FROM purchase_orders WHERE id = %s FOR UPDATE",
                                        (rec_po_id,)
                                    )
                                    po_status_row = cursor.fetchone()
                                    if not po_status_row or po_status_row["status"] not in ("Ordered", "Partially Received"):
                                        current_stat = po_status_row["status"] if po_status_row else "Unknown"
                                        raise ValueError(f"Cannot receive goods: Purchase Order is in '{current_stat}' status.")

                                    for item_id, (it, qty_now) in receipt_inputs.items():
                                        if qty_now > 0:
                                            # Atomic guard against over-receiving
                                            cursor.execute(
                                                """
                                                UPDATE purchase_order_items 
                                                SET quantity_received = quantity_received + %s 
                                                WHERE id = %s AND (quantity_received + %s) <= quantity_ordered
                                                """,
                                                (qty_now, item_id, qty_now)
                                            )
                                            if cursor.rowcount == 0:
                                                raise ValueError(
                                                    f"Receiving {qty_now} units for '{it['product_name']}' would exceed the ordered quantity."
                                                )

                                            # Atomic inventory update / upsert
                                            cursor.execute(
                                                """
                                                INSERT INTO inventory (product_id, quantity_on_hand, reorder_point)
                                                VALUES (%s, %s, 10)
                                                ON DUPLICATE KEY UPDATE quantity_on_hand = quantity_on_hand + VALUES(quantity_on_hand)
                                                """,
                                                (it["product_id"], qty_now)
                                            )

                                            cursor.execute(
                                                "SELECT quantity_on_hand FROM inventory WHERE product_id = %s",
                                                (it["product_id"],)
                                            )
                                            new_balance = cursor.fetchone()["quantity_on_hand"]

                                            ref_note = f"PO #{rec_po['po_number']} receipt. Notes: {receipt_notes.strip()}"
                                            cursor.execute(
                                                """
                                                INSERT INTO stock_movements 
                                                (product_id, movement_type, quantity, balance_after, reference_type, reference_id, notes, created_by_admin_id)
                                                VALUES (%s, 'PO_RECEIPT', %s, %s, 'PURCHASE_ORDER', %s, %s, %s)
                                                """,
                                                (it["product_id"], qty_now, new_balance, rec_po_id, ref_note, admin_id)
                                            )

                                    cursor.execute(
                                        """
                                        SELECT COUNT(*) as count FROM purchase_order_items 
                                        WHERE purchase_order_id = %s AND quantity_received < quantity_ordered
                                        """,
                                        (rec_po_id,)
                                    )
                                    pending_count = cursor.fetchone()["count"]

                                    new_po_status = "Received" if pending_count == 0 else "Partially Received"
                                    cursor.execute(
                                        "UPDATE purchase_orders SET status = %s WHERE id = %s AND status IN ('Ordered', 'Partially Received')",
                                        (new_po_status, rec_po_id)
                                    )

                                st.toast(f"Successfully received {total_receiving_now} unit(s)! PO status: {new_po_status}.", icon="✅")
                                st.rerun()
                            except ValueError as val_err:
                                logger.warning(f"Goods receipt validation failed: {val_err}")
                                st.error(str(val_err))
                            except Exception as ex:
                                logger.error(f"Error during receipt transaction: {ex}", exc_info=True)
                                st.error("A database transaction error occurred during receipt processing.")
