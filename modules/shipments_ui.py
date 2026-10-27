"""
Shipment Tracking Module: Carrier Dispatch, Tracking Numbers, Status Progression, and Delivery Verification.
"""

from datetime import date, timedelta
import logging
import streamlit as st
import pandas as pd
import database as db
from modules.ui_components import (
    render_page_header,
    render_metric_card,
    render_section_header,
    render_empty_state,
    paginate_dataframe
)

logger = logging.getLogger("siom.shipments")


def render_shipments_page():
    render_page_header(
        title="Shipment & Logistics Tracking",
        subtitle="Manage carrier dispatch, package tracking numbers, delivery timelines, and logistics lifecycles.",
        icon="🚚"
    )

    tab1, tab2, tab3 = st.tabs(["🚚 Shipments Directory", "➕ Create Shipment Dispatch", "⏱️ Shipment Timeline & Status Update"])

    # --------------------------------------------------------------------------
    # Tab 1: Shipments Directory
    # --------------------------------------------------------------------------
    with tab1:
        st.markdown('<div class="siom-filter-panel">', unsafe_allow_html=True)
        col_s, col_c, col_stat = st.columns([2, 1, 1])
        with col_s:
            search_shp = st.text_input("🔍 Search Shipment #, Tracking #, or Customer", key="shp_search")
        with col_c:
            carrier_f = st.selectbox(
                "Carrier Filter",
                ["All Carriers", "BlueDart Express", "Delhivery", "DTDC", "FedEx", "DHL Express", "Local Courier / Own Fleet"],
                key="shp_carrier_f"
            )
        with col_stat:
            status_f = st.selectbox(
                "Shipment Status",
                ["All Statuses", "Pending", "Packed", "Dispatched", "In Transit", "Delivered", "Failed", "Returned"],
                key="shp_stat_f"
            )
        st.markdown('</div>', unsafe_allow_html=True)

        query = """
            SELECT 
                s.id,
                s.shipment_number,
                so.order_number,
                c.name AS customer_name,
                s.carrier,
                s.tracking_number,
                s.dispatch_date,
                s.estimated_delivery,
                s.actual_delivery,
                s.status,
                s.notes
            FROM shipments s
            JOIN sales_orders so ON s.sales_order_id = so.id
            JOIN customers c ON so.customer_id = c.id
            WHERE 1=1
        """
        params = []
        if search_shp:
            query += " AND (s.shipment_number LIKE %s OR s.tracking_number LIKE %s OR so.order_number LIKE %s OR c.name LIKE %s)"
            params.extend([f"%{search_shp}%", f"%{search_shp}%", f"%{search_shp}%", f"%{search_shp}%"])

        if carrier_f != "All Carriers":
            query += " AND s.carrier = %s"
            params.append(carrier_f)

        if status_f != "All Statuses":
            query += " AND s.status = %s"
            params.append(status_f)

        query += " ORDER BY s.created_at DESC"
        shipments = db.execute_cached_query(query, tuple(params) if params else None)

        if shipments:
            tot_shp = len(shipments)
            deliv_shp = sum(1 for s in shipments if s["status"] == "Delivered")
            transit_shp = sum(1 for s in shipments if s["status"] in ("In Transit", "Dispatched"))
            pack_shp = sum(1 for s in shipments if s["status"] in ("Packed", "Pending"))

            k1, k2, k3, k4 = st.columns(4)
            with k1:
                render_metric_card("Total Dispatches", tot_shp, "All carrier shipments", "🚚", "blue")
            with k2:
                render_metric_card("Delivered & Verified", deliv_shp, "POD confirmed", "✅", "green")
            with k3:
                render_metric_card("In Transit", transit_shp, "En route to customers", "📦", "purple")
            with k4:
                render_metric_card("Pending Dispatch", pack_shp, "In warehouse staging", "⏳", "amber" if pack_shp > 0 else "green")
            st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)

        if not shipments:
            render_empty_state("No shipment dispatches found matching the filter.", "Create a dispatch record for a confirmed order.", "🚚")
        else:
            df = pd.DataFrame(shipments)
            df_disp = df[[
                "shipment_number", "order_number", "customer_name", "carrier", 
                "tracking_number", "dispatch_date", "estimated_delivery", "actual_delivery", "status"
            ]]
            df_disp.columns = [
                "Shipment #", "Order #", "Customer", "Carrier", 
                "Tracking #", "Dispatch Date", "Est. Delivery", "Actual Delivery", "Status"
            ]
            paginated_shp = paginate_dataframe(df_disp, page_size=50, key="shp_tbl")
            st.dataframe(paginated_shp, use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # Tab 2: Create Shipment Record
    # --------------------------------------------------------------------------
    with tab2:
        render_section_header("Create Logistics Dispatch for Confirmed Order", "Assign third-party carrier details, tracking codes, and dispatch schedule", "➕")

        eligible_orders = db.execute_cached_query(
            """
            SELECT so.id, so.order_number, c.name as customer_name, so.order_date, so.status
            FROM sales_orders so
            JOIN customers c ON so.customer_id = c.id
            WHERE so.status IN ('Confirmed', 'Processing', 'Shipped')
            ORDER BY so.order_date DESC
            """
        )

        if not eligible_orders:
            render_empty_state("No confirmed orders currently awaiting shipment dispatch.", icon="📦")
        else:
            so_map = {f"{o['order_number']} - {o['customer_name']} ({o['status']})": o for o in eligible_orders}
            sel_so_k = st.selectbox("Select Sales Order *", list(so_map.keys()), key="shp_so_sel")
            target_so = so_map[sel_so_k]
            order_id = target_so["id"]

            with st.form("create_shipment_form"):
                col1, col2 = st.columns(2)
                with col1:
                    carrier = st.selectbox(
                        "Logistics Carrier *",
                        ["BlueDart Express", "Delhivery", "DTDC", "FedEx", "DHL Express", "UPS", "Local Courier / Own Fleet"]
                    )
                    tracking_number = st.text_input("Tracking / Waybill Number *", placeholder="e.g. BD-8921734912")
                    dispatch_date = st.date_input("Dispatch Date", value=date.today())

                with col2:
                    est_delivery = st.date_input("Estimated Delivery Date", value=date.today() + timedelta(days=3))
                    init_status = st.selectbox("Initial Shipment Status", ["Packed", "Dispatched", "In Transit", "Pending"])
                    notes = st.text_area("Logistics Notes / Special Instructions", placeholder="Fragile handling, gate pass reference, package count...")

                create_shp_btn = st.form_submit_button("Create Shipment Record", type="primary", use_container_width=True)

                if create_shp_btn:
                    if not tracking_number.strip():
                        st.error("Tracking / Waybill Number is required.")
                    else:
                        with st.spinner("Creating shipment..."):
                            try:
                                with db.get_db_transaction() as (cursor, conn):
                                    shp_number = db.get_next_document_number(cursor, "SHP")
                                    cursor.execute(
                                        """
                                        INSERT INTO shipments 
                                        (shipment_number, sales_order_id, carrier, tracking_number, dispatch_date, estimated_delivery, status, notes)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                        """,
                                        (
                                            shp_number, order_id, carrier, tracking_number.strip(),
                                             dispatch_date, est_delivery, init_status, notes.strip()
                                        )
                                    )
                                    if init_status in ["Dispatched", "In Transit"]:
                                        cursor.execute("UPDATE sales_orders SET status = 'Shipped' WHERE id = %s", (order_id,))

                                st.toast(f"Shipment {shp_number} created successfully!", icon="✅")
                                st.rerun()
                            except Exception as ex:
                                logger.error(f"Error creating shipment: {ex}", exc_info=True)
                                st.error("A database error occurred while creating the shipment record.")

    # --------------------------------------------------------------------------
    # Tab 3: Shipment Status & Timeline Update
    # --------------------------------------------------------------------------
    with tab3:
        render_section_header("Logistics Status Progression & POD Update", "Advance shipment statuses through delivery or record carrier exceptions", "⏱️")
        all_shp = db.execute_query(
            """
            SELECT s.id, s.shipment_number, s.carrier, s.tracking_number, s.status, so.order_number, s.sales_order_id
            FROM shipments s
            JOIN sales_orders so ON s.sales_order_id = so.id
            ORDER BY s.created_at DESC
            """
        )

        if not all_shp:
            render_empty_state("No shipments recorded to update.", icon="🚚")
        else:
            shp_map = {f"{s['shipment_number']} ({s['carrier']} - {s['tracking_number']}) [{s['status']}]": s for s in all_shp}
            sel_s_k = st.selectbox("Select Shipment to Update", list(shp_map.keys()), key="shp_upd_sel")
            curr_shp = shp_map[sel_s_k]
            shp_id = curr_shp["id"]
            so_id = curr_shp["sales_order_id"]

            with st.form("update_shipment_form"):
                st.markdown(f"**Shipment:** `{curr_shp['shipment_number']}` | **Order:** `{curr_shp['order_number']}`")
                
                statuses = ["Pending", "Packed", "Dispatched", "In Transit", "Delivered", "Failed", "Returned"]
                curr_idx = statuses.index(curr_shp["status"]) if curr_shp["status"] in statuses else 0
                new_status = st.selectbox("Update Status", statuses, index=curr_idx)

                actual_del_date = st.date_input("Actual Delivery Date (if Delivered)", value=date.today())
                update_notes = st.text_input("Delivery Remarks / POD Reference", placeholder="Signed by recipient, Gate security receipt, etc.")

                update_btn = st.form_submit_button("Update Logistics Status", type="primary", use_container_width=True)

                if update_btn:
                    with st.spinner("Updating shipment status..."):
                        try:
                            with db.get_db_transaction() as (cursor, conn):
                                if new_status == "Delivered":
                                    cursor.execute(
                                        """
                                        UPDATE shipments 
                                        SET status = %s, actual_delivery = %s, notes = CONCAT(COALESCE(notes, ''), ' | ', %s)
                                        WHERE id = %s
                                        """,
                                        (new_status, actual_del_date, f"Delivered: {update_notes.strip()}", shp_id)
                                    )
                                    cursor.execute("UPDATE sales_orders SET status = 'Delivered' WHERE id = %s", (so_id,))
                                else:
                                    cursor.execute(
                                        """
                                        UPDATE shipments 
                                        SET status = %s, notes = CONCAT(COALESCE(notes, ''), ' | ', %s)
                                        WHERE id = %s
                                        """,
                                        (new_status, update_notes.strip(), shp_id)
                                    )
                                    if new_status in ["Dispatched", "In Transit"]:
                                        cursor.execute("UPDATE sales_orders SET status = 'Shipped' WHERE id = %s", (so_id,))

                            st.toast(f"Shipment status updated to {new_status}!", icon="✅")
                            st.rerun()
                        except Exception as ex:
                            logger.error(f"Error updating shipment: {ex}", exc_info=True)
                            st.error("A database error occurred while updating shipment status.")
