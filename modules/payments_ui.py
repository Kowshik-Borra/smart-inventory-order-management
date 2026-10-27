"""
Payment Tracking Module: Record customer payments, track invoice balances,
support partial/advance payments, and generate transaction receipts.
"""

from datetime import date
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

logger = logging.getLogger("siom.payments")


def render_payments_page():
    render_page_header(
        title="Payment & Accounts Receivable",
        subtitle="Record payments against customer orders, track outstanding invoices, and audit payment receipts.",
        icon="💳"
    )

    tab1, tab2 = st.tabs(["💳 Payment Transactions Log", "➕ Record Order Payment"])

    # --------------------------------------------------------------------------
    # Tab 1: Payment Transactions Ledger
    # --------------------------------------------------------------------------
    with tab1:
        st.markdown('<div class="siom-filter-panel">', unsafe_allow_html=True)
        col_s, col_m, col_st = st.columns([2, 1, 1])
        with col_s:
            search_p = st.text_input("🔍 Search Payment #, Order, Customer, or Ref", key="pay_search_txt")
        with col_m:
            method_filter = st.selectbox(
                "Payment Method",
                ["All Methods", "Bank Transfer", "Credit Card", "Debit Card", "UPI", "Cash", "Cheque"],
                key="pay_meth_f"
            )
        with col_st:
            status_filter = st.selectbox(
                "Status",
                ["All Statuses", "Completed", "Pending", "Failed"],
                key="pay_status_f"
            )
        st.markdown('</div>', unsafe_allow_html=True)

        query = """
            SELECT 
                p.id,
                p.payment_number,
                so.order_number,
                c.name AS customer_name,
                p.payment_date,
                p.amount,
                p.payment_method,
                p.reference_number,
                p.status,
                p.notes,
                p.created_at
            FROM payments p
            JOIN sales_orders so ON p.sales_order_id = so.id
            JOIN customers c ON so.customer_id = c.id
            WHERE 1=1
        """
        params = []
        if search_p:
            query += " AND (p.payment_number LIKE %s OR so.order_number LIKE %s OR p.reference_number LIKE %s OR c.name LIKE %s)"
            params.extend([f"%{search_p}%", f"%{search_p}%", f"%{search_p}%", f"%{search_p}%"])

        if method_filter != "All Methods":
            query += " AND p.payment_method = %s"
            params.append(method_filter)

        if status_filter != "All Statuses":
            query += " AND p.status = %s"
            params.append(status_filter)

        query += " ORDER BY p.payment_date DESC, p.id DESC"
        payments = db.execute_cached_query(query, tuple(params) if params else None)

        # Summary KPIs
        total_collected = sum(Decimal(str(p["amount"])) for p in payments if p["status"] == "Completed")
        tot_cnt = len(payments)
        comp_cnt = sum(1 for p in payments if p["status"] == "Completed")
        pend_cnt = sum(1 for p in payments if p["status"] == "Pending")

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            render_metric_card("Total Collected Revenue", format_inr_compact(total_collected), f"Across {tot_cnt} Receipts", "💵", "green")
        with k2:
            render_metric_card("Settled Transactions", comp_cnt, "Completed Payments", "✅", "green")
        with k3:
            render_metric_card("Pending Clearance", pend_cnt, "In Clearance / Escrow", "⏳", "amber" if pend_cnt > 0 else "green")
        with k4:
            render_metric_card("Total Transaction Log", tot_cnt, "All Payment Records", "💳", "purple")

        st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)
        if not payments:
            render_empty_state("No payment transactions recorded yet.", "Record a payment against a pending sales order.", "💳")
        else:
            df_pay = pd.DataFrame(payments)
            df_pay["Amount (₹)"] = df_pay["amount"].apply(format_currency)
            df_pay_disp = df_pay[[
                "payment_number", "order_number", "customer_name", "payment_date", 
                "Amount (₹)", "payment_method", "reference_number", "status", "notes"
            ]]
            df_pay_disp.columns = [
                "Payment #", "Order #", "Customer", "Date", "Amount", 
                "Method", "Reference / Cheque #", "Status", "Notes"
            ]
            paginated_pay = paginate_dataframe(df_pay_disp, page_size=50, key="pay_tbl")
            st.dataframe(paginated_pay, use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # Tab 2: Record New Payment Against Sales Order
    # --------------------------------------------------------------------------
    with tab2:
        render_section_header("Record Customer Invoice Settlement", "Apply partial or full payments against unsettled outbound sales orders", "➕")

        pending_orders = db.execute_cached_query(
            """
            SELECT 
                so.id,
                so.order_number,
                c.name AS customer_name,
                so.total_amount,
                COALESCE(SUM(p.amount), 0) AS paid_amount,
                (so.total_amount - COALESCE(SUM(p.amount), 0)) AS balance_due
            FROM sales_orders so
            JOIN customers c ON so.customer_id = c.id
            LEFT JOIN payments p ON so.id = p.sales_order_id AND p.status = 'Completed'
            WHERE so.status != 'Cancelled'
            GROUP BY so.id
            HAVING balance_due > 0
            ORDER BY so.order_date DESC
            """
        )

        if not pending_orders:
            st.success("All sales orders are currently fully settled! No outstanding balances.")
        else:
            ord_map = {
                f"{o['order_number']} - {o['customer_name']} (Total: {format_currency(o['total_amount'])} | Due: {format_currency(o['balance_due'])})": o 
                for o in pending_orders
            }
            sel_ord_k = st.selectbox("Select Order with Outstanding Balance *", list(ord_map.keys()), key="pay_ord_sel")
            target_ord = ord_map[sel_ord_k]
            order_id = target_ord["id"]
            balance_due = Decimal(str(target_ord["balance_due"]))

            with st.form("record_payment_form"):
                col1, col2 = st.columns(2)
                with col1:
                    pay_amount = st.number_input(
                        "Payment Amount (₹) *",
                        min_value=1.0,
                        max_value=float(balance_due * Decimal("1.5")),
                        value=float(balance_due),
                        step=100.0
                    )
                    pay_date = st.date_input("Payment Date *", value=date.today())
                    pay_method = st.selectbox(
                        "Payment Method *",
                        ["Bank Transfer", "Credit Card", "Debit Card", "UPI", "Cash", "Cheque"]
                    )

                with col2:
                    ref_no = st.text_input("Transaction / Ref / Cheque No.", placeholder="e.g. TXN-892183921 / Cheque #0012")
                    pay_status = st.selectbox("Payment Status", ["Completed", "Pending", "Failed"])
                    pay_notes = st.text_area("Notes", placeholder="Advance deposit, milestone installment, final settlement...")

                submit_pay_btn = st.form_submit_button("Record Payment Transaction", type="primary", use_container_width=True)

                if submit_pay_btn:
                    pay_dec = Decimal(str(pay_amount))
                    if pay_dec > balance_due:
                        st.warning(f"Note: Recorded amount ({format_currency(pay_dec)}) exceeds remaining balance ({format_currency(balance_due)}).")

                    with st.spinner("Recording payment..."):
                        try:
                            with db.get_db_transaction() as (cursor, conn):
                                pay_number = db.get_next_document_number(cursor, "PAY")
                                cursor.execute(
                                    """
                                    INSERT INTO payments 
                                    (payment_number, sales_order_id, payment_date, amount, payment_method, reference_number, status, notes)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                    """,
                                    (
                                        pay_number, order_id, pay_date, pay_dec, 
                                        pay_method, ref_no.strip(), pay_status, pay_notes.strip()
                                    )
                                )

                            st.toast(f"Payment {pay_number} for {format_currency(pay_dec)} recorded successfully!", icon="✅")
                            st.rerun()
                        except Exception as ex:
                            logger.error(f"Error recording payment: {ex}", exc_info=True)
                            st.error("A database error occurred while recording the payment.")
