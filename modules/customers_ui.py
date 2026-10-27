"""
Customer Management Module: Client CRM, contact info, sales order history,
and live outstanding balance calculation based on invoice vs payments.
"""

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
    format_currency,
    format_inr_compact
)

def render_customers_page():
    render_page_header(
        title="Customer Directory & CRM",
        subtitle="Maintain customer accounts, order histories, credit limits, and outstanding accounts receivable balances.",
        icon="👥"
    )

    tab1, tab2, tab3 = st.tabs(["👥 Customer Directory", "➕ Add New Customer", "📑 Customer History & Balance"])

    # --------------------------------------------------------------------------
    # Tab 1: Customer Directory & Edit
    # --------------------------------------------------------------------------
    with tab1:
        st.markdown('<div class="siom-filter-panel">', unsafe_allow_html=True)
        col_s, col_f = st.columns([3, 1])
        with col_s:
            search_txt = st.text_input("🔍 Search Customers", placeholder="Search by name, contact person, email, city, or phone...", key="cust_search_txt")
        with col_f:
            status_f = st.selectbox("Status", ["All", "Active Only", "Inactive Only"], key="cust_status_filter")
        st.markdown('</div>', unsafe_allow_html=True)

        query = """
            SELECT 
                c.id, 
                c.name, 
                c.contact_person, 
                c.phone, 
                c.email, 
                c.address, 
                c.is_active,
                COUNT(so.id) AS total_orders,
                COALESCE(SUM(so.total_amount), 0) AS total_ordered,
                COALESCE((
                    SELECT SUM(p.amount) 
                    FROM payments p 
                    JOIN sales_orders so2 ON p.sales_order_id = so2.id 
                    WHERE so2.customer_id = c.id AND p.status = 'Completed'
                ), 0) AS total_paid
            FROM customers c
            LEFT JOIN sales_orders so ON c.id = so.customer_id AND so.status != 'Cancelled'
            WHERE 1=1
        """
        params = []
        if search_txt:
            query += " AND (c.name LIKE %s OR c.contact_person LIKE %s OR c.email LIKE %s OR c.phone LIKE %s OR c.address LIKE %s)"
            params.extend([f"%{search_txt}%", f"%{search_txt}%", f"%{search_txt}%", f"%{search_txt}%", f"%{search_txt}%"])

        if status_f == "Active Only":
            query += " AND c.is_active = 1"
        elif status_f == "Inactive Only":
            query += " AND c.is_active = 0"

        query += " GROUP BY c.id ORDER BY c.name ASC"
        customers = db.execute_query(query, params)

        if not customers:
            render_empty_state("No customers found matching the criteria.", "Register a new customer account or clear search filter.", "👥")
        else:
            df = pd.DataFrame(customers)
            df["Status"] = df["is_active"].apply(lambda x: "🟢 Active" if x == 1 else "🔴 Inactive")
            df["Outstanding Balance"] = df["total_ordered"] - df["total_paid"]
            df["Total Ordered (₹)"] = df["total_ordered"].apply(format_currency)
            df["Total Paid (₹)"] = df["total_paid"].apply(format_currency)
            df["Outstanding Due (₹)"] = df["Outstanding Balance"].apply(format_currency)
            
            display_df = df[["id", "name", "contact_person", "phone", "email", "address", "total_orders", "Total Ordered (₹)", "Total Paid (₹)", "Outstanding Due (₹)", "Status"]]
            display_df.columns = ["ID", "Customer / Client", "Contact Person", "Phone", "Email", "Billing / Shipping Address", "Total Orders", "Total Ordered", "Total Paid", "Outstanding Due", "Status"]
            
            paginated_cust = paginate_dataframe(display_df, page_size=50, key="cust_table")
            st.dataframe(
                paginated_cust,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Billing / Shipping Address": st.column_config.TextColumn(
                        "Billing / Shipping Address",
                        width="large"
                    )
                }
            )

            # Edit Section
            st.markdown("---")
            render_section_header("Edit Customer Profile", "Update client contact information or CRM status", "✏️")
            cust_dict = {f"{c['name']} (ID: {c['id']})": c for c in customers}
            sel_c_key = st.selectbox("Select Customer to Edit", list(cust_dict.keys()), key="cust_edit_sel")
            sel_c = cust_dict[sel_c_key]

            with st.form("edit_customer_form"):
                e1, e2 = st.columns(2)
                with e1:
                    e_name = st.text_input("Customer / Company Name *", value=sel_c["name"])
                    e_contact = st.text_input("Contact Person", value=sel_c["contact_person"] or "")
                    e_phone = st.text_input("Phone Number", value=sel_c["phone"] or "")
                with e2:
                    e_email = st.text_input("Email Address", value=sel_c["email"] or "")
                    e_active = st.checkbox("Active Customer Account", value=bool(sel_c["is_active"]))
                    e_address = st.text_input("Billing / Shipping Address", value=sel_c["address"] or "")

                update_cust_btn = st.form_submit_button("Save Customer Changes", type="primary", use_container_width=True)

                if update_cust_btn:
                    if not e_name.strip():
                        st.error("Customer Name is required.")
                    else:
                        with st.spinner("Saving customer changes..."):
                            dup = db.execute_one(
                                "SELECT id FROM customers WHERE name = %s AND id != %s",
                                (e_name.strip(), sel_c["id"])
                            )
                            if dup:
                                st.error(f"Customer with name '{e_name}' already exists.")
                            else:
                                db.execute_update(
                                    """
                                    UPDATE customers 
                                    SET name = %s, contact_person = %s, email = %s, phone = %s, address = %s, is_active = %s
                                    WHERE id = %s
                                    """,
                                    (
                                        e_name.strip(), e_contact.strip(), e_email.strip(), e_phone.strip(),
                                        e_address.strip(), 1 if e_active else 0, sel_c["id"]
                                    )
                                )
                                st.toast(f"Customer '{e_name}' updated successfully!", icon="✅")
                                st.rerun()

    # --------------------------------------------------------------------------
    # Tab 2: Add New Customer
    # --------------------------------------------------------------------------
    with tab2:
        render_section_header("Register New Customer Account", "Add a new client account for sales orders, invoicing, and receivable tracking", "➕")
        with st.form("add_customer_form", clear_on_submit=True):
            a1, a2 = st.columns(2)
            with a1:
                n_name = st.text_input("Customer / Corporate Client Name *", placeholder="e.g. Suresh Technologies Pvt Ltd")
                n_contact = st.text_input("Primary Contact Person", placeholder="e.g. Suresh Varma (Managing Director)")
                n_phone = st.text_input("Phone Number", placeholder="e.g. +91 98480 23456")
            with a2:
                n_email = st.text_input("Email Address", placeholder="e.g. procurement@suresh-tech.in")
                n_address = st.text_input("Primary Billing / Shipping Address", placeholder="e.g. Plot 42, Cyber Pearl, HITEC City, Hyderabad, Telangana")
                n_active = st.checkbox("Active Customer Account", value=True)

            create_cust_btn = st.form_submit_button("Create Customer Account", type="primary", use_container_width=True)

            if create_cust_btn:
                if not n_name.strip():
                    st.error("Customer Name is required.")
                else:
                    with st.spinner("Registering customer account..."):
                        dup = db.execute_one("SELECT id FROM customers WHERE name = %s", (n_name.strip(),))
                        if dup:
                            st.error(f"Customer with name '{n_name}' already exists.")
                        else:
                            db.execute_insert(
                                """
                                INSERT INTO customers (name, contact_person, email, phone, address, is_active)
                                VALUES (%s, %s, %s, %s, %s, %s)
                                """,
                                (
                                    n_name.strip(), n_contact.strip(), n_email.strip(), n_phone.strip(),
                                    n_address.strip(), 1 if n_active else 0
                                )
                            )
                            st.toast(f"Customer '{n_name}' created successfully!", icon="✅")
                            st.rerun()

    # --------------------------------------------------------------------------
    # Tab 3: Customer History & Ledger
    # --------------------------------------------------------------------------
    with tab3:
        render_section_header("Customer Account Balance & Order Ledger", "Trace historical orders, invoice totals, and accounts receivable balance", "📑")
        all_c = db.execute_query("SELECT id, name FROM customers ORDER BY name ASC")
        if not all_c:
            render_empty_state("No customers registered yet.", icon="👥")
            return

        c_pick_map = {c["name"]: c["id"] for c in all_c}
        sel_c_label = st.selectbox("Select Customer to Review", list(c_pick_map.keys()), key="cust_hist_pick")
        customer_id = c_pick_map[sel_c_label]

        cust_totals = db.execute_one(
            """
            SELECT 
                COUNT(so.id) AS total_orders,
                COALESCE(SUM(so.total_amount), 0) AS total_invoiced,
                COALESCE((
                    SELECT SUM(p.amount) 
                    FROM payments p 
                    JOIN sales_orders so2 ON p.sales_order_id = so2.id 
                    WHERE so2.customer_id = %s AND p.status = 'Completed'
                ), 0) AS total_paid
            FROM sales_orders so
            WHERE so.customer_id = %s AND so.status != 'Cancelled'
            """,
            (customer_id, customer_id)
        )

        invoiced = Decimal(str(cust_totals["total_invoiced"]))
        paid = Decimal(str(cust_totals["total_paid"]))
        outstanding = invoiced - paid
        order_count = cust_totals["total_orders"]

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            render_metric_card("Total Invoiced", format_inr_compact(invoiced), "Cumulative gross orders", "💵", "blue")
        with c2:
            render_metric_card("Total Collected", format_inr_compact(paid), "Settled payments", "💳", "green")
        with c3:
            render_metric_card(
                "Outstanding Balance", 
                format_inr_compact(outstanding), 
                "Due for collection" if outstanding > 0 else "Fully settled", 
                "📈", 
                "amber" if outstanding > 0 else "green"
            )
        with c4:
            render_metric_card("Orders Placed", order_count, "All-time order count", "🛍️", "purple")

        st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)
        st.markdown("##### Historical Customer Orders")
        so_hist = db.execute_query(
            """
            SELECT 
                so.order_number, 
                so.order_date, 
                so.status, 
                so.total_amount,
                COALESCE(SUM(p.amount), 0) AS paid_amount,
                (so.total_amount - COALESCE(SUM(p.amount), 0)) AS balance_due
            FROM sales_orders so
            LEFT JOIN payments p ON so.id = p.sales_order_id AND p.status = 'Completed'
            WHERE so.customer_id = %s
            GROUP BY so.id
            ORDER BY so.order_date DESC
            """,
            (customer_id,)
        )

        if so_hist:
            df_so_hist = pd.DataFrame(so_hist)
            df_so_hist["Total Amount (₹)"] = df_so_hist["total_amount"].apply(format_currency)
            df_so_hist["Paid (₹)"] = df_so_hist["paid_amount"].apply(format_currency)
            df_so_hist["Balance Due (₹)"] = df_so_hist["balance_due"].apply(format_currency)
            df_so_hist_disp = df_so_hist[["order_number", "order_date", "status", "Total Amount (₹)", "Paid (₹)", "Balance Due (₹)"]]
            df_so_hist_disp.columns = ["Order #", "Order Date", "Status", "Total Amount", "Paid", "Balance Due"]
            paginated_so_hist = paginate_dataframe(df_so_hist_disp, page_size=50, key="cust_so_hist")
            st.dataframe(paginated_so_hist, use_container_width=True, hide_index=True)
        else:
            render_empty_state(f"No sales orders found for {sel_c_label}.", icon="🛍️")
