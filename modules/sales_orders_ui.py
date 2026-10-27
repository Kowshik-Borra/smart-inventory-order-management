"""
Sales Orders & Fulfillment Module:
Multi-item customer sales orders, real-time inventory validation,
transaction-safe fulfillment stock deduction, idempotent protections, and order lifecycles.
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

logger = logging.getLogger("siom.sales_orders")


def render_sales_orders_page():
    render_page_header(
        title="Sales Orders & Fulfillment Pipeline",
        subtitle="Manage customer orders, real-time stock allocation, dispatch fulfillment, and delivery lifecycles.",
        icon="🛍️"
    )

    tab1, tab2, tab3 = st.tabs(["📋 Sales Orders List", "➕ Create Sales Order", "⚙️ Order Details & Processing"])

    # --------------------------------------------------------------------------
    # Tab 1: Sales Orders Listing
    # --------------------------------------------------------------------------
    with tab1:
        st.markdown('<div class="siom-filter-panel">', unsafe_allow_html=True)
        col_s, col_stat, col_d = st.columns([2, 1, 1])
        with col_s:
            search_so = st.text_input("🔍 Search Order Number or Customer", placeholder="e.g. SO-2026 or Ananya", key="so_search_txt")
        with col_stat:
            status_so = st.selectbox(
                "Order Status Filter",
                ["All Statuses", "Draft", "Confirmed", "Processing", "Shipped", "Delivered", "Cancelled"],
                key="so_stat_f"
            )
        with col_d:
            date_filter = st.date_input(
                "Order Date Range",
                value=[date.today() - timedelta(days=365), date.today()],
                key="so_date_range"
            )
        st.markdown('</div>', unsafe_allow_html=True)

        if isinstance(date_filter, (list, tuple)) and len(date_filter) == 2:
            s_date, e_date = date_filter
        else:
            s_date, e_date = date.today() - timedelta(days=365), date.today()

        query = """
            SELECT 
                so.id,
                so.order_number,
                c.name AS customer_name,
                so.order_date,
                so.status,
                so.total_amount,
                so.stock_deducted,
                COALESCE(SUM(p.amount), 0) AS amount_paid,
                (so.total_amount - COALESCE(SUM(p.amount), 0)) AS balance_due,
                COUNT(soi.id) AS item_count
            FROM sales_orders so
            JOIN customers c ON so.customer_id = c.id
            LEFT JOIN sales_order_items soi ON so.id = soi.sales_order_id
            LEFT JOIN payments p ON so.id = p.sales_order_id AND p.status = 'Completed'
            WHERE so.order_date BETWEEN %s AND %s
        """
        params = [s_date, e_date]
        if search_so:
            query += " AND (so.order_number LIKE %s OR c.name LIKE %s)"
            params.extend([f"%{search_so}%", f"%{search_so}%"])

        if status_so != "All Statuses":
            query += " AND so.status = %s"
            params.append(status_so)

        query += " GROUP BY so.id ORDER BY so.order_date DESC, so.id DESC"
        so_list = db.execute_cached_query(query, tuple(params) if params else None)

        if so_list:
            total_sales_val = sum(Decimal(str(o["total_amount"])) for o in so_list if o["status"] != "Cancelled")
            total_collected_val = sum(Decimal(str(o["amount_paid"])) for o in so_list if o["status"] != "Cancelled")
            tot_so_cnt = len(so_list)
            deliv_cnt = sum(1 for o in so_list if o["status"] == "Delivered")

            k1, k2, k3, k4 = st.columns(4)
            with k1:
                render_metric_card("Total Sales Revenue", format_inr_compact(total_sales_val), f"Across {tot_so_cnt} Sales Orders", "💵", "blue")
            with k2:
                render_metric_card("Total Collected", format_inr_compact(total_collected_val), "Settled Payments", "💳", "green")
            with k3:
                render_metric_card("Delivered Orders", deliv_cnt, f"{tot_so_cnt - deliv_cnt} In Pipeline", "🚚", "purple")
            with k4:
                render_metric_card("Outstanding Balance", format_inr_compact(total_sales_val - total_collected_val), "Uncollected AR", "⏳", "amber" if (total_sales_val - total_collected_val) > 0 else "green")
            st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)

        if not so_list:
            render_empty_state("No sales orders found matching the filter.", "Create a new sales order or adjust filters.", "🛍️")
        else:
            df_so = pd.DataFrame(so_list)
            df_so["Payment Status"] = df_so.apply(
                lambda r: "Paid" if r["balance_due"] <= 0 
                else ("Partial" if r["amount_paid"] > 0 else "Unpaid"), axis=1
            )
            df_so["Stock Allocated"] = df_so["stock_deducted"].apply(lambda x: "Deducted" if x == 1 else "Pending")
            df_so["Total (₹)"] = df_so["total_amount"].apply(format_currency)
            df_so["Paid (₹)"] = df_so["amount_paid"].apply(format_currency)
            df_so["Balance Due (₹)"] = df_so["balance_due"].apply(format_currency)

            df_so_disp = df_so[[
                "id", "order_number", "customer_name", "order_date", "status", 
                "Total (₹)", "Paid (₹)", "Balance Due (₹)", "Payment Status", "Stock Allocated"
            ]]
            df_so_disp.columns = [
                "ID", "Order Number", "Customer", "Date", "Status", 
                "Total", "Paid", "Balance Due", "Payment", "Inventory"
            ]
            paginated_so = paginate_dataframe(df_so_disp, page_size=50, key="so_tbl")
            st.dataframe(paginated_so, use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # Tab 2: Create Sales Order (Dynamic Multi-Line Items)
    # --------------------------------------------------------------------------
    with tab2:
        render_section_header("Create New Customer Sales Order", "Draft or confirm an outbound order with real-time stock availability validation", "➕")
        customers = db.execute_cached_query("SELECT id, name FROM customers WHERE is_active = 1 ORDER BY name ASC")
        products = db.execute_cached_query(
            """
            SELECT p.id, p.sku, p.name, p.selling_price, p.cost_price, p.unit, COALESCE(i.quantity_on_hand, 0) as stock_qty
            FROM products p
            LEFT JOIN inventory i ON p.id = i.product_id
            WHERE p.is_active = 1
            ORDER BY p.name ASC
            """
        )

        if not customers or not products:
            st.warning("Please ensure active customers and products exist before creating a sales order.")
        else:
            if "so_line_items" not in st.session_state:
                st.session_state.so_line_items = []

            col_c1, col_c2 = st.columns(2)
            with col_c1:
                cust_choice = {c["name"]: c["id"] for c in customers}
                sel_cust = st.selectbox("Customer *", list(cust_choice.keys()), key="so_cust_sel")
                cust_id = cust_choice[sel_cust]
            with col_c2:
                so_date = st.date_input("Order Date", value=date.today(), key="so_order_date_in")

            so_notes = st.text_input("Order Notes / Delivery Instructions", placeholder="e.g. Expedited delivery requested, Gate 4 dock", key="so_notes_in")

            st.markdown("---")
            render_section_header("Add Products to Order", "Pick catalog items and specify quantities", "📦")

            prod_map = {f"{p['sku']} - {p['name']} (Stock: {p['stock_qty']} {p['unit']} | Price: {format_currency(p['selling_price'])})": p for p in products}
            i_col1, i_col2, i_col3, i_col4 = st.columns([3, 1, 1, 1])
            with i_col1:
                sel_p_key = st.selectbox("Select Product", list(prod_map.keys()), key="so_item_prod_pick")
                sel_p_obj = prod_map[sel_p_key]
            with i_col2:
                qty_avail = sel_p_obj["stock_qty"]
                so_item_qty = st.number_input("Quantity", min_value=1, value=1, step=1, key="so_item_qty_pick")
            with i_col3:
                so_unit_price = st.number_input(
                    "Unit Selling Price (₹)",
                    min_value=0.0,
                    value=float(sel_p_obj["selling_price"]),
                    step=50.0,
                    key="so_unit_price_pick"
                )
            with i_col4:
                st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
                if st.button("Add Item", key="so_add_item_btn", use_container_width=True):
                    if so_item_qty > qty_avail:
                        st.warning(f"Warning: Requested {so_item_qty} units, but only {qty_avail} are currently on hand.")
                    
                    exist = next((x for x in st.session_state.so_line_items if x["product_id"] == sel_p_obj["id"]), None)
                    if exist:
                        exist["quantity"] += so_item_qty
                        exist["unit_price"] = Decimal(str(so_unit_price))
                        exist["line_total"] = exist["quantity"] * exist["unit_price"]
                    else:
                        st.session_state.so_line_items.append({
                            "product_id": sel_p_obj["id"],
                            "sku": sel_p_obj["sku"],
                            "name": sel_p_obj["name"],
                            "stock_avail": qty_avail,
                            "quantity": so_item_qty,
                            "unit_price": Decimal(str(so_unit_price)),
                            "line_total": Decimal(str(so_item_qty)) * Decimal(str(so_unit_price))
                        })
                    st.rerun()

            if st.session_state.so_line_items:
                st.markdown("##### Current Order Lines")
                df_lines = pd.DataFrame([
                    {
                        "SKU": l["sku"],
                        "Product": l["name"],
                        "In Stock": l["stock_avail"],
                        "Order Qty": l["quantity"],
                        "Unit Price (₹)": format_currency(l["unit_price"]),
                        "Line Total (₹)": format_currency(l["line_total"])
                    }
                    for l in st.session_state.so_line_items
                ])
                st.dataframe(df_lines, use_container_width=True, hide_index=True)

                subtotal = sum(l["line_total"] for l in st.session_state.so_line_items)

                c_disc, c_tax, c_tot, c_clr = st.columns([1, 1, 2, 1])
                with c_disc:
                    discount_val = st.number_input("Discount (₹)", min_value=0.0, value=0.0, step=100.0, key="so_disc_val")
                with c_tax:
                    tax_pct = st.number_input("Sales Tax / GST (%)", min_value=0.0, max_value=100.0, value=18.0, step=0.5, key="so_tax_pct")
                with c_tot:
                    tax_val = (subtotal - Decimal(str(discount_val))) * (Decimal(str(tax_pct)) / Decimal("100"))
                    final_total = max(Decimal("0.00"), (subtotal - Decimal(str(discount_val))) + tax_val)
                    render_metric_card("Final Order Total", format_currency(final_total), f"Subtotal: {format_currency(subtotal)} | Disc: -{format_currency(discount_val)} | GST: +{format_currency(tax_val)}", "🛍️", "green")
                with c_clr:
                    st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
                    if st.button("Clear Items", key="so_clear_items_btn", use_container_width=True):
                        st.session_state.so_line_items = []
                        st.rerun()

                st.markdown("---")
                c_btn1, c_btn2 = st.columns(2)
                with c_btn1:
                    create_draft_so = st.button("Save as Draft (No Stock Deduction)", use_container_width=True)
                with c_btn2:
                    create_confirm_so = st.button("Confirm & Deduct Stock Now", type="primary", use_container_width=True)

                if create_draft_so or create_confirm_so:
                    should_deduct = bool(create_confirm_so)
                    init_status = "Confirmed" if should_deduct else "Draft"

                    with st.spinner("Processing sales order..."):
                        try:
                            admin_id = st.session_state.get("admin_id")
                            with db.get_db_transaction() as (cursor, conn):
                                # Generate race-safe SO Number
                                so_number = db.get_next_document_number(cursor, "SO")

                                cursor.execute(
                                    """
                                    INSERT INTO sales_orders 
                                    (order_number, customer_id, order_date, status, subtotal, discount_amount, tax_amount, total_amount, notes, stock_deducted)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                    """,
                                    (
                                        so_number, cust_id, so_date, init_status,
                                        subtotal, Decimal(str(discount_val)), tax_val, final_total,
                                        so_notes.strip(), 1 if should_deduct else 0
                                    )
                                )
                                new_so_id = cursor.lastrowid

                                for item in st.session_state.so_line_items:
                                    cursor.execute(
                                        """
                                        INSERT INTO sales_order_items (sales_order_id, product_id, quantity, unit_price, line_total)
                                        VALUES (%s, %s, %s, %s, %s)
                                        """,
                                        (new_so_id, item["product_id"], item["quantity"], item["unit_price"], item["line_total"])
                                    )

                                    if should_deduct:
                                        # Atomic stock deduction with overselling check
                                        cursor.execute(
                                            """
                                            UPDATE inventory 
                                             SET quantity_on_hand = quantity_on_hand - %s 
                                            WHERE product_id = %s AND quantity_on_hand >= %s
                                            """,
                                            (item["quantity"], item["product_id"], item["quantity"])
                                        )
                                        if cursor.rowcount == 0:
                                            raise ValueError(
                                                f"Insufficient inventory for product '{item['name']}' (Requested: {item['quantity']}). "
                                                f"Order creation aborted."
                                            )

                                        cursor.execute(
                                            "SELECT quantity_on_hand FROM inventory WHERE product_id = %s",
                                            (item["product_id"],)
                                        )
                                        inv_row = cursor.fetchone()
                                        new_b = inv_row["quantity_on_hand"] if inv_row else 0

                                        cursor.execute(
                                            """
                                            INSERT INTO stock_movements 
                                            (product_id, movement_type, quantity, balance_after, reference_type, reference_id, notes, created_by_admin_id)
                                            VALUES (%s, 'SO_FULFILLMENT', %s, %s, 'SALES_ORDER', %s, %s, %s)
                                            """,
                                            (item["product_id"], item["quantity"], new_b, new_so_id, f"Fulfillment for Order #{so_number}", admin_id)
                                        )

                            st.session_state.so_line_items = []
                            st.toast(f"Sales Order {so_number} created successfully ({init_status})!", icon="✅")
                            st.rerun()
                        except ValueError as val_err:
                            logger.warning(f"Validation error creating sales order: {val_err}")
                            st.error(str(val_err))
                        except Exception as ex:
                            logger.error(f"Error creating sales order: {ex}", exc_info=True)
                            st.error("An unexpected error occurred while creating the sales order. Please try again.")

    # --------------------------------------------------------------------------
    # Tab 3: Order Details, Stock Fulfillment & Status Transitions
    # --------------------------------------------------------------------------
    with tab3:
        render_section_header("Order Fulfillment & Lifecycle Manager", "Inspect customer lines, trigger warehouse allocations, or change dispatch statuses", "🔍")
        all_so = db.execute_query(
            """
            SELECT so.id, so.order_number, c.name as customer_name, so.status, so.stock_deducted, so.total_amount
            FROM sales_orders so
            JOIN customers c ON so.customer_id = c.id
            ORDER BY so.order_date DESC, so.id DESC
            """
        )

        if not all_so:
            render_empty_state("No sales orders recorded yet.", icon="🛍️")
        else:
            so_pick_map = {f"{o['order_number']} - {o['customer_name']} [{o['status']}]": o for o in all_so}
            sel_so_k = st.selectbox("Select Sales Order to Manage", list(so_pick_map.keys()), key="so_mgr_select")
            sel_order = so_pick_map[sel_so_k]
            order_id = sel_order["id"]

            so_detail = db.execute_one(
                """
                SELECT so.*, c.name as customer_name, c.email as customer_email, c.phone as customer_phone, c.address as customer_address
                FROM sales_orders so
                JOIN customers c ON so.customer_id = c.id
                WHERE so.id = %s
                """,
                (order_id,)
            )

            so_items = db.execute_query(
                """
                SELECT 
                    soi.id,
                    soi.product_id,
                    p.sku,
                    p.name as product_name,
                    soi.quantity,
                    soi.unit_price,
                    soi.line_total,
                    COALESCE(i.quantity_on_hand, 0) as current_stock
                FROM sales_order_items soi
                JOIN products p ON soi.product_id = p.id
                LEFT JOIN inventory i ON p.id = i.product_id
                WHERE soi.sales_order_id = %s
                """,
                (order_id,)
            )

            c_info1, c_info2 = st.columns([2, 1])
            with c_info1:
                st.markdown(f"### Order `{so_detail['order_number']}`")
                st.markdown(f"**Customer:** {so_detail['customer_name']} ({so_detail['customer_email'] or 'No email'})")
                st.markdown(f"**Address:** {so_detail['customer_address'] or 'N/A'}")
                st.markdown(f"**Order Date:** {so_detail['order_date']}")
                
                if so_items:
                    df_items_disp = pd.DataFrame(so_items)
                    df_items_disp["Unit Price (₹)"] = df_items_disp["unit_price"].apply(format_currency)
                    df_items_disp["Line Total (₹)"] = df_items_disp["line_total"].apply(format_currency)
                    df_items_disp = df_items_disp[["id", "sku", "product_name", "quantity", "Unit Price (₹)", "Line Total (₹)", "current_stock"]]
                    df_items_disp.columns = ["Item ID", "SKU", "Product Name", "Qty", "Price", "Line Total", "Current Stock"]
                    st.dataframe(df_items_disp, use_container_width=True, hide_index=True)

            with c_info2:
                render_section_header("Fulfillment & Status", None, "⚙️")
                render_metric_card("Order Total", format_currency(so_detail['total_amount']), f"Status: {so_detail['status']}", "💵", "blue")
                
                is_deducted = bool(so_detail["stock_deducted"])
                st.markdown(f"Inventory Stock Status: **{'Allocated & Deducted' if is_deducted else 'Pending Allocation'}**")

                admin_id = st.session_state.get("admin_id")
                current_status = so_detail["status"]

                # Action 1: Deduct Stock if Draft (Idempotent confirmation)
                if not is_deducted and current_status == "Draft":
                    if st.button("Confirm & Deduct Stock Now", type="primary", use_container_width=True):
                        with st.spinner("Deducting inventory and confirming order..."):
                            try:
                                with db.get_db_transaction() as (cursor, conn):
                                    cursor.execute(
                                        "UPDATE sales_orders SET status = 'Confirmed', stock_deducted = 1 WHERE id = %s AND stock_deducted = 0",
                                        (order_id,)
                                    )
                                    if cursor.rowcount == 0:
                                        raise ValueError("Order stock has already been deducted or order status has changed.")

                                    for item in so_items:
                                        cursor.execute(
                                            """
                                            UPDATE inventory 
                                            SET quantity_on_hand = quantity_on_hand - %s 
                                            WHERE product_id = %s AND quantity_on_hand >= %s
                                            """,
                                            (item["quantity"], item["product_id"], item["quantity"])
                                        )
                                        if cursor.rowcount == 0:
                                            raise ValueError(
                                                f"Insufficient stock for product '{item['product_name']}'. "
                                                f"Requested: {item['quantity']}, but available stock is insufficient."
                                            )

                                        cursor.execute(
                                            "SELECT quantity_on_hand FROM inventory WHERE product_id = %s",
                                            (item["product_id"],)
                                        )
                                        new_bal = cursor.fetchone()["quantity_on_hand"]

                                        cursor.execute(
                                            """
                                            INSERT INTO stock_movements 
                                            (product_id, movement_type, quantity, balance_after, reference_type, reference_id, notes, created_by_admin_id)
                                            VALUES (%s, 'SO_FULFILLMENT', %s, %s, 'SALES_ORDER', %s, %s, %s)
                                            """,
                                            (item["product_id"], item["quantity"], new_bal, order_id, f"Fulfillment for Order #{so_detail['order_number']}", admin_id)
                                        )

                                st.toast("Stock deducted and order confirmed successfully!", icon="✅")
                                st.rerun()
                            except ValueError as val_err:
                                logger.warning(f"Stock confirmation failed: {val_err}")
                                st.error(str(val_err))
                            except Exception as ex:
                                logger.error(f"Transaction error during order confirmation: {ex}", exc_info=True)
                                st.error("A transaction error occurred during confirmation. No changes were committed.")

                # Status Transition selector (Strict State Machine)
                st.markdown("<div style='height: 8px'></div>", unsafe_allow_html=True)
                allowed_next_states = db.SALES_ORDER_TRANSITIONS.get(current_status, [])

                if not allowed_next_states:
                    st.info(f"Order `{so_detail['order_number']}` is in terminal state **{current_status}**. No further status changes are permitted.")
                else:
                    status_choices = [current_status] + allowed_next_states
                    new_st = st.selectbox("Change Order Status", status_choices, index=0)

                    confirm_cancel = True
                    if new_st == "Cancelled":
                        st.warning("Cancelling a confirmed order will return all allocated items back to inventory stock.")
                        confirm_cancel = st.checkbox(f"Confirm cancellation of Order {so_detail['order_number']}", key="so_cancel_confirm_chk")

                    if st.button("Apply Status Change", use_container_width=True):
                        if new_st == current_status:
                            st.info("Selected status is the same as current status.")
                        elif not db.is_valid_sales_order_transition(current_status, new_st):
                            st.error(f"Invalid status transition from '{current_status}' to '{new_st}'.")
                        elif new_st == "Cancelled" and not confirm_cancel:
                            st.error("Please confirm the cancellation checkbox before applying.")
                        elif new_st == "Cancelled" and is_deducted:
                            with st.spinner("Restoring inventory and cancelling order..."):
                                try:
                                    with db.get_db_transaction() as (cursor, conn):
                                        cursor.execute(
                                            "UPDATE sales_orders SET status = 'Cancelled', stock_deducted = 0 WHERE id = %s AND stock_deducted = 1",
                                            (order_id,)
                                        )
                                        if cursor.rowcount == 0:
                                            raise ValueError("Order is already cancelled or stock has already been restored.")

                                        for item in so_items:
                                            cursor.execute(
                                                "UPDATE inventory SET quantity_on_hand = quantity_on_hand + %s WHERE product_id = %s",
                                                (item["quantity"], item["product_id"])
                                            )
                                            cursor.execute(
                                                "SELECT quantity_on_hand FROM inventory WHERE product_id = %s",
                                                (item["product_id"],)
                                            )
                                            new_bal = cursor.fetchone()["quantity_on_hand"]

                                            cursor.execute(
                                                """
                                                INSERT INTO stock_movements 
                                                (product_id, movement_type, quantity, balance_after, reference_type, reference_id, notes, created_by_admin_id)
                                                VALUES (%s, 'RETURN_IN', %s, %s, 'SALES_ORDER', %s, %s, %s)
                                                """,
                                                (item["product_id"], item["quantity"], new_bal, order_id, f"Order #{so_detail['order_number']} Cancelled - Returned to stock", admin_id)
                                            )

                                    st.toast("Order cancelled and inventory restored to warehouse!", icon="✅")
                                    st.rerun()
                                except ValueError as val_err:
                                    logger.warning(f"Cancellation failed: {val_err}")
                                    st.error(str(val_err))
                                except Exception as ex:
                                    logger.error(f"Error cancelling order: {ex}", exc_info=True)
                                    st.error("An error occurred while cancelling the order. Please try again.")
                        else:
                            with st.spinner(f"Updating order status to {new_st}..."):
                                try:
                                    with db.get_db_transaction() as (cursor, conn):
                                        cursor.execute(
                                            "UPDATE sales_orders SET status = %s WHERE id = %s AND status = %s",
                                            (new_st, order_id, current_status)
                                        )
                                        if cursor.rowcount == 0:
                                            raise ValueError(f"Order status could not be changed from '{current_status}'. Status may have already changed.")

                                    st.toast(f"Status updated to {new_st}!", icon="✅")
                                    st.rerun()
                                except ValueError as val_err:
                                    logger.warning(f"Status update rejected: {val_err}")
                                    st.error(str(val_err))
                                except Exception as ex:
                                    logger.error(f"Error updating order status: {ex}", exc_info=True)
                                    st.error("Failed to update status. Please try again.")
