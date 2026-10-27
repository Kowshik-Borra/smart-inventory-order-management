"""
Supplier Management Module: Vendor Directory, Contact Validation, Procurement History,
and Performance Metrics.
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

def render_suppliers_page():
    render_page_header(
        title="Supplier Directory & Vendor Management",
        subtitle="Manage procurement partners, contact channels, lead times, and vendor fulfillment metrics.",
        icon="🏢"
    )

    tab1, tab2, tab3 = st.tabs(["🏢 Supplier Directory", "➕ Add New Supplier", "📊 Supplier Analytics & History"])

    # --------------------------------------------------------------------------
    # Tab 1: Directory & Quick Edit
    # --------------------------------------------------------------------------
    with tab1:
        st.markdown('<div class="siom-filter-panel">', unsafe_allow_html=True)
        col_s, col_f = st.columns([3, 1])
        with col_s:
            search_txt = st.text_input("🔍 Search Suppliers", placeholder="Search by company name, contact person, email, city, or phone...")
        with col_f:
            status_f = st.selectbox("Status", ["All", "Active Only", "Inactive Only"], key="supp_status_filter")
        st.markdown('</div>', unsafe_allow_html=True)

        query = """
            SELECT 
                s.id,
                s.name,
                s.contact_person,
                s.phone,
                s.email,
                s.address,
                s.notes,
                s.is_active,
                COUNT(po.id) AS total_orders,
                COALESCE(SUM(po.total_amount), 0) AS total_purchases
            FROM suppliers s
            LEFT JOIN purchase_orders po ON s.id = po.supplier_id AND po.status != 'Cancelled'
            WHERE 1=1
        """
        params = []
        if search_txt:
            query += " AND (s.name LIKE %s OR s.contact_person LIKE %s OR s.email LIKE %s OR s.phone LIKE %s OR s.address LIKE %s)"
            params.extend([f"%{search_txt}%", f"%{search_txt}%", f"%{search_txt}%", f"%{search_txt}%", f"%{search_txt}%"])

        if status_f == "Active Only":
            query += " AND s.is_active = 1"
        elif status_f == "Inactive Only":
            query += " AND s.is_active = 0"

        query += " GROUP BY s.id ORDER BY s.name ASC"
        suppliers = db.execute_query(query, params)

        if not suppliers:
            render_empty_state("No suppliers found matching the filter.", "Register a new vendor or clear your search query.", "🏢")
        else:
            df = pd.DataFrame(suppliers)
            df["Status"] = df["is_active"].apply(lambda x: "🟢 Active" if x == 1 else "🔴 Inactive")
            df["Total Purchases (₹)"] = df["total_purchases"].apply(format_currency)
            
            display_df = df[["id", "name", "contact_person", "phone", "email", "address", "total_orders", "Total Purchases (₹)", "Status"]]
            display_df.columns = ["ID", "Supplier / Company", "Contact Person", "Phone", "Email", "Address", "Total POs", "Total Purchases", "Status"]
            paginated_supp = paginate_dataframe(display_df, page_size=50, key="supp_table")
            st.dataframe(paginated_supp, use_container_width=True, hide_index=True)

            # Edit Section
            st.markdown("---")
            render_section_header("Edit Supplier Profile", "Update vendor contact details and partnership status", "✏️")
            supp_dict = {f"{s['name']} (ID: {s['id']})": s for s in suppliers}
            sel_s_key = st.selectbox("Select Supplier", list(supp_dict.keys()), key="supp_edit_sel")
            sel_s = supp_dict[sel_s_key]

            with st.form("edit_supplier_form"):
                e1, e2 = st.columns(2)
                with e1:
                    e_name = st.text_input("Supplier Name *", value=sel_s["name"])
                    e_contact = st.text_input("Contact Person", value=sel_s["contact_person"] or "")
                    e_phone = st.text_input("Phone Number", value=sel_s["phone"] or "")
                with e2:
                    e_email = st.text_input("Email Address", value=sel_s["email"] or "")
                    e_active = st.checkbox("Active Partner", value=bool(sel_s["is_active"]))
                    e_notes = st.text_input("Notes / Terms", value=sel_s["notes"] or "")

                e_address = st.text_area("Address", value=sel_s["address"] or "")
                update_supp_btn = st.form_submit_button("Save Supplier Changes", type="primary", use_container_width=True)

                if update_supp_btn:
                    if not e_name.strip():
                        st.error("Supplier Name is required.")
                    else:
                        with st.spinner("Saving supplier changes..."):
                            dup = db.execute_one(
                                "SELECT id FROM suppliers WHERE name = %s AND id != %s",
                                (e_name.strip(), sel_s["id"])
                            )
                            if dup:
                                st.error(f"Supplier with name '{e_name}' already exists.")
                            else:
                                db.execute_update(
                                    """
                                    UPDATE suppliers 
                                    SET name = %s, contact_person = %s, email = %s, phone = %s, address = %s, notes = %s, is_active = %s
                                    WHERE id = %s
                                    """,
                                    (
                                        e_name.strip(), e_contact.strip(), e_email.strip(), e_phone.strip(),
                                        e_address.strip(), e_notes.strip(), 1 if e_active else 0, sel_s["id"]
                                    )
                                )
                                st.toast(f"Supplier '{e_name}' updated successfully!", icon="✅")
                                st.rerun()

    # --------------------------------------------------------------------------
    # Tab 2: Add New Supplier
    # --------------------------------------------------------------------------
    with tab2:
        render_section_header("Register New Procurement Partner", "Add a qualified vendor to the system for future purchase orders", "➕")
        with st.form("add_supplier_form", clear_on_submit=True):
            a1, a2 = st.columns(2)
            with a1:
                n_name = st.text_input("Supplier / Vendor Company Name *", placeholder="e.g. Apex Industrial Electronics Ltd.")
                n_contact = st.text_input("Key Contact Person", placeholder="e.g. Robert Smith (Account Mgr)")
                n_phone = st.text_input("Phone Number", placeholder="e.g. +91 98450 12345")
            with a2:
                n_email = st.text_input("Email Address", placeholder="e.g. sales@apex-electronics.com")
                n_notes = st.text_input("Payment Terms / Notes", placeholder="e.g. Net 30 days, FOB Warehouse")
                n_active = st.checkbox("Active Supplier", value=True)

            n_address = st.text_area("Physical / Billing Address", placeholder="Street, Industrial Area, City, State, PIN Code")
            create_supp_btn = st.form_submit_button("Create Supplier Record", type="primary", use_container_width=True)

            if create_supp_btn:
                if not n_name.strip():
                    st.error("Supplier Company Name is required.")
                else:
                    with st.spinner("Registering supplier..."):
                        dup = db.execute_one("SELECT id FROM suppliers WHERE name = %s", (n_name.strip(),))
                        if dup:
                            st.error(f"A supplier with name '{n_name}' already exists.")
                        else:
                            db.execute_insert(
                                """
                                INSERT INTO suppliers (name, contact_person, email, phone, address, notes, is_active)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """,
                                (
                                    n_name.strip(), n_contact.strip(), n_email.strip(), n_phone.strip(),
                                    n_address.strip(), n_notes.strip(), 1 if n_active else 0
                                )
                            )
                            st.toast(f"Supplier '{n_name}' registered successfully!", icon="✅")
                            st.rerun()

    # --------------------------------------------------------------------------
    # Tab 3: Supplier Analytics & History
    # --------------------------------------------------------------------------
    with tab3:
        render_section_header("Vendor Performance & Procurement Audit", "Review order fulfillment rates, historical spend, and purchase history", "📊")
        all_s = db.execute_query("SELECT id, name FROM suppliers ORDER BY name ASC")
        if not all_s:
            render_empty_state("No suppliers found in directory.", icon="🏢")
            return

        s_pick_map = {s["name"]: s["id"] for s in all_s}
        sel_s_label = st.selectbox("Select Supplier to Analyze", list(s_pick_map.keys()), key="supp_perf_pick")
        supp_id = s_pick_map[sel_s_label]

        # Supplier metrics
        po_agg = db.execute_one(
            """
            SELECT 
                COUNT(id) AS total_orders,
                COALESCE(SUM(total_amount), 0) AS total_spent,
                COUNT(CASE WHEN status = 'Received' THEN 1 END) AS completed_orders,
                COUNT(CASE WHEN status IN ('Ordered', 'Partially Received') THEN 1 END) AS open_orders
            FROM purchase_orders
            WHERE supplier_id = %s
            """,
            (supp_id,)
        )

        spent_val = Decimal(str(po_agg["total_spent"]))
        tot_orders = po_agg["total_orders"]
        comp_orders = po_agg["completed_orders"]
        open_orders = po_agg["open_orders"]
        fulfill_rate = (comp_orders / tot_orders * 100) if tot_orders > 0 else 100.0

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            render_metric_card("Total PO Spend", format_inr_compact(spent_val), "All historical requisitions", "💵", "blue")
        with c2:
            render_metric_card("Total Orders Placed", tot_orders, f"{open_orders} Currently Open", "🛒", "purple")
        with c3:
            render_metric_card("Completed Orders", comp_orders, f"{open_orders} in pipeline", "📦", "green")
        with c4:
            render_metric_card("Fulfillment Rate", f"{fulfill_rate:.1f}%", "Order completion ratio", "📈", "green" if fulfill_rate >= 80 else "amber")

        st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)
        st.markdown("##### Historical Purchase Orders")
        po_hist = db.execute_query(
            """
            SELECT 
                po_number, order_date, expected_date, status, subtotal, tax_amount, total_amount, notes
            FROM purchase_orders
            WHERE supplier_id = %s
            ORDER BY order_date DESC
            """,
            (supp_id,)
        )

        if po_hist:
            df_po_hist = pd.DataFrame(po_hist)
            df_po_hist["Subtotal (₹)"] = df_po_hist["subtotal"].apply(format_currency)
            df_po_hist["Tax (₹)"] = df_po_hist["tax_amount"].apply(format_currency)
            df_po_hist["Total Amount (₹)"] = df_po_hist["total_amount"].apply(format_currency)
            df_po_hist_disp = df_po_hist[["po_number", "order_date", "expected_date", "status", "Subtotal (₹)", "Tax (₹)", "Total Amount (₹)", "notes"]]
            df_po_hist_disp.columns = ["PO #", "Order Date", "Expected Date", "Status", "Subtotal", "Tax", "Total Amount", "Notes"]
            paginated_po_hist = paginate_dataframe(df_po_hist_disp, page_size=50, key="supp_po_hist")
            st.dataframe(paginated_po_hist, use_container_width=True, hide_index=True)
        else:
            render_empty_state(f"No historical purchase orders recorded with {sel_s_label}.", icon="🛒")
