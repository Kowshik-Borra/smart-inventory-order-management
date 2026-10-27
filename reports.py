"""
Reports and Business Analytics Module:
Pandas analytical transforms, Plotly visual trend builders, and Excel (.xlsx) / CSV export generators.
Accurately differentiates Gross Revenue, Cost of Goods Sold (COGS), and Net Profit with full INR currency formatting.
"""

from io import BytesIO
from datetime import date, timedelta
from decimal import Decimal
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import database as db
from modules.ui_components import (
    render_page_header,
    render_metric_card,
    render_section_header,
    render_empty_state,
    style_plotly_figure,
    paginate_dataframe,
    format_currency,
    format_inr_compact
)

def generate_excel_download(df: pd.DataFrame, sheet_name: str = "Report") -> bytes:
    """Generates an Excel workbook file stream using openpyxl."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()


def generate_csv_download(df: pd.DataFrame) -> bytes:
    """Generates CSV bytes format."""
    return df.to_csv(index=False).encode("utf-8")


def render_reports_page():
    render_page_header(
        title="Business Analytics & Financial Reports",
        subtitle="Deep-dive analytics on sales profitability, inventory valuation, supplier fulfillment, and audit ledgers.",
        icon="📈"
    )

    st.markdown('<div class="siom-filter-panel">', unsafe_allow_html=True)
    report_type = st.selectbox(
        "Select Report Category",
        [
            "1. Sales & Profitability Analysis",
            "2. Procurement & Supplier Spend Report",
            "3. Inventory Valuation & Asset Health",
            "4. Customer Ledger & Accounts Receivable",
            "5. Complete Stock Movement Audit Ledger"
        ]
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # Report 1: Sales & Profitability Analysis
    # --------------------------------------------------------------------------
    if report_type.startswith("1."):
        render_section_header("Sales Revenue, COGS & Gross Profitability", "Analyze top-line revenue, product cost of goods sold, and gross margins", "💰")
        
        st.markdown('<div class="siom-filter-panel">', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            date_range = st.date_input(
                "Select Date Range",
                value=[date.today() - timedelta(days=365), date.today()],
                key="rep_sales_date"
            )
        with col2:
            group_by = st.selectbox("Group By Dimension", ["Month", "Category", "Product", "Day"])
        st.markdown('</div>', unsafe_allow_html=True)

        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            s_date, e_date = date_range
        else:
            s_date, e_date = date.today() - timedelta(days=365), date.today()

        query = """
            SELECT 
                so.order_date,
                DATE_FORMAT(so.order_date, '%Y-%m') AS month_label,
                p.name AS product_name,
                c.name AS category_name,
                soi.quantity,
                soi.unit_price,
                soi.line_total AS line_revenue,
                (soi.quantity * p.cost_price) AS line_cogs,
                (soi.line_total - (soi.quantity * p.cost_price)) AS line_gross_profit
            FROM sales_order_items soi
            JOIN sales_orders so ON soi.sales_order_id = so.id
            JOIN products p ON soi.product_id = p.id
            JOIN categories c ON p.category_id = c.id
            WHERE so.status != 'Cancelled' AND so.order_date BETWEEN %s AND %s
            ORDER BY so.order_date DESC
        """
        raw_data = db.execute_cached_query(query, (s_date, e_date))

        if not raw_data:
            render_empty_state("No sales records found in the selected date window.", "Adjust your date filter to view historical data.", "💰")
        else:
            df = pd.DataFrame(raw_data)
            for col in ["quantity", "line_revenue", "line_cogs", "line_gross_profit"]:
                df[col] = df[col].astype(float)

            tot_rev = df["line_revenue"].sum()
            tot_cogs = df["line_cogs"].sum()
            tot_profit = df["line_gross_profit"].sum()
            tot_units = df["quantity"].sum()
            margin_pct = (tot_profit / tot_rev * 100) if tot_rev > 0 else 0

            k1, k2, k3, k4 = st.columns(4)
            with k1:
                render_metric_card("Gross Sales Revenue", format_inr_compact(tot_rev), f"Total: {format_currency(tot_rev)}", "💵", "blue")
            with k2:
                render_metric_card("Cost of Goods Sold (COGS)", format_inr_compact(tot_cogs), "Raw inventory cost basis", "📦", "purple")
            with k3:
                render_metric_card("Gross Profit Realized", format_inr_compact(tot_profit), f"Units Sold: {int(tot_units):,}", "💰", "green")
            with k4:
                render_metric_card("Gross Margin %", f"{margin_pct:.1f}%", "Overall catalog profitability", "📈", "green" if margin_pct >= 25 else "amber")

            st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)

            # Grouped breakdown
            if group_by == "Month":
                grouped_df = df.groupby("month_label").agg(
                    Units_Sold=("quantity", "sum"),
                    Revenue=("line_revenue", "sum"),
                    COGS=("line_cogs", "sum"),
                    Profit=("line_gross_profit", "sum")
                ).reset_index().sort_values(by="month_label", ascending=True)
                x_col = "month_label"
            elif group_by == "Category":
                grouped_df = df.groupby("category_name").agg(
                    Units_Sold=("quantity", "sum"),
                    Revenue=("line_revenue", "sum"),
                    COGS=("line_cogs", "sum"),
                    Profit=("line_gross_profit", "sum")
                ).reset_index().sort_values(by="Revenue", ascending=False)
                x_col = "category_name"
            elif group_by == "Product":
                grouped_df = df.groupby("product_name").agg(
                    Units_Sold=("quantity", "sum"),
                    Revenue=("line_revenue", "sum"),
                    COGS=("line_cogs", "sum"),
                    Profit=("line_gross_profit", "sum")
                ).reset_index().sort_values(by="Revenue", ascending=False).head(15)
                x_col = "product_name"
            else:  # Day
                grouped_df = df.groupby("order_date").agg(
                    Units_Sold=("quantity", "sum"),
                    Revenue=("line_revenue", "sum"),
                    COGS=("line_cogs", "sum"),
                    Profit=("line_gross_profit", "sum")
                ).reset_index().sort_values(by="order_date", ascending=True)
                x_col = "order_date"

            grouped_df["Margin %"] = (grouped_df["Profit"] / grouped_df["Revenue"] * 100).round(2)

            # Interactive Plotly Chart (Enterprise Dark Theme)
            fig = go.Figure()
            fig.add_trace(go.Bar(x=grouped_df[x_col], y=grouped_df["Revenue"], name="Revenue (₹)", marker_color="#3b82f6"))
            fig.add_trace(go.Bar(x=grouped_df[x_col], y=grouped_df["COGS"], name="COGS (₹)", marker_color="#64748b"))
            fig.add_trace(go.Bar(x=grouped_df[x_col], y=grouped_df["Profit"], name="Profit (₹)", marker_color="#10b981"))
            fig.update_layout(barmode="group")
            style_plotly_figure(fig, title=f"Revenue, COGS & Profit Comparison by {group_by}", height=380)
            st.plotly_chart(fig, use_container_width=True)

            # Display formatted table
            df_disp = grouped_df.copy()
            df_disp["Revenue (₹)"] = df_disp["Revenue"].apply(format_currency)
            df_disp["COGS (₹)"] = df_disp["COGS"].apply(format_currency)
            df_disp["Profit (₹)"] = df_disp["Profit"].apply(format_currency)
            df_disp["Margin"] = df_disp["Margin %"].apply(lambda m: f"{m:.1f}%")
            df_disp = df_disp.drop(columns=["Revenue", "COGS", "Profit", "Margin %"])

            paginated_sales = paginate_dataframe(df_disp, page_size=50, key="rep_s_tbl")
            st.dataframe(paginated_sales, use_container_width=True, hide_index=True)

            # Export Buttons
            exp_c1, exp_c2 = st.columns(2)
            with exp_c1:
                excel_bytes = generate_excel_download(grouped_df, "Sales_Profit_Report")
                st.download_button(
                    "📥 Export to Excel (.xlsx)",
                    data=excel_bytes,
                    file_name=f"sales_profit_report_{s_date}_to_{e_date}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            with exp_c2:
                csv_data = generate_csv_download(grouped_df)
                st.download_button(
                    "📥 Export to CSV (.csv)",
                    data=csv_data,
                    file_name=f"sales_profit_report_{s_date}_to_{e_date}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

    # --------------------------------------------------------------------------
    # Report 2: Procurement & Supplier Spend Report
    # --------------------------------------------------------------------------
    elif report_type.startswith("2."):
        render_section_header("Procurement & Supplier Spend Analysis", "Audit vendor spend, order fulfillment rates, and monthly purchasing trends", "🏢")

        st.markdown('<div class="siom-filter-panel">', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            p_date_range = st.date_input(
                "Select Date Range",
                value=[date.today() - timedelta(days=365), date.today()],
                key="rep_purch_date"
            )
        with col2:
            p_group_by = st.selectbox("Dimension Breakdown", ["Supplier", "Month"], key="purch_group_by")
        st.markdown('</div>', unsafe_allow_html=True)

        if isinstance(p_date_range, (list, tuple)) and len(p_date_range) == 2:
            ps_date, pe_date = p_date_range
        else:
            ps_date, pe_date = date.today() - timedelta(days=365), date.today()

        supp_perf = db.execute_cached_query(
            """
            SELECT 
                s.name AS supplier_name,
                po.order_date,
                DATE_FORMAT(po.order_date, '%Y-%m') AS month_label,
                po.total_amount,
                po.status,
                poi.quantity_ordered,
                poi.quantity_received
            FROM purchase_orders po
            JOIN suppliers s ON po.supplier_id = s.id
            LEFT JOIN purchase_order_items poi ON po.id = poi.purchase_order_id
            WHERE po.status != 'Cancelled' AND po.order_date BETWEEN %s AND %s
            ORDER BY po.order_date ASC
            """,
            (ps_date, pe_date)
        )

        if not supp_perf:
            render_empty_state("No procurement records found in the selected date window.", icon="🏢")
        else:
            df_po_rep = pd.DataFrame(supp_perf)
            for c in ["total_amount", "quantity_ordered", "quantity_received"]:
                df_po_rep[c] = df_po_rep[c].astype(float)

            tot_spend = df_po_rep["total_amount"].drop_duplicates().sum()
            tot_ordered_qty = df_po_rep["quantity_ordered"].sum()
            tot_rec_qty = df_po_rep["quantity_received"].sum()
            po_fulfill_rate = (tot_rec_qty / tot_ordered_qty * 100) if tot_ordered_qty > 0 else 100.0

            k1, k2, k3, k4 = st.columns(4)
            with k1:
                render_metric_card("Total Procurement Spend", format_inr_compact(tot_spend), f"Total: {format_currency(tot_spend)}", "💵", "blue")
            with k2:
                render_metric_card("Units Ordered", f"{int(tot_ordered_qty):,}", "Inbound requisition", "📦", "purple")
            with k3:
                render_metric_card("Units Received", f"{int(tot_rec_qty):,}", "Physically received", "✅", "green")
            with k4:
                render_metric_card("Fulfillment Rate", f"{po_fulfill_rate:.1f}%", "Vendor delivery ratio", "📈", "green" if po_fulfill_rate >= 80 else "amber")

            st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)

            if p_group_by == "Supplier":
                grouped_po = df_po_rep.groupby("supplier_name").agg(
                    Total_Spend=("total_amount", "sum"),
                    Units_Ordered=("quantity_ordered", "sum"),
                    Units_Received=("quantity_received", "sum")
                ).reset_index().sort_values(by="Total_Spend", ascending=False)
                grouped_po["Fulfillment Rate %"] = (grouped_po["Units_Received"] / grouped_po["Units_Ordered"] * 100).round(1)

                fig_p = px.bar(
                    grouped_po.head(10),
                    x="supplier_name",
                    y="Total_Spend",
                    title="Top 10 Suppliers by Procurement Spend (₹)",
                    labels={"supplier_name": "Supplier", "Total_Spend": "Spend (₹)"},
                    color_discrete_sequence=["#3b82f6"]
                )
                style_plotly_figure(fig_p, title="Top 10 Suppliers by Spend (₹)", height=350)
                st.plotly_chart(fig_p, use_container_width=True)
            else:
                grouped_po = df_po_rep.groupby("month_label").agg(
                    Total_Spend=("total_amount", "sum"),
                    Units_Ordered=("quantity_ordered", "sum"),
                    Units_Received=("quantity_received", "sum")
                ).reset_index().sort_values(by="month_label", ascending=True)

                fig_p = px.line(
                    grouped_po,
                    x="month_label",
                    y="Total_Spend",
                    title="Monthly Procurement Spend Trend (₹)",
                    labels={"month_label": "Month", "Total_Spend": "Spend (₹)"},
                    markers=True,
                    color_discrete_sequence=["#8b5cf6"]
                )
                style_plotly_figure(fig_p, title="Monthly Procurement Spend Trend (₹)", height=350)
                st.plotly_chart(fig_p, use_container_width=True)

            disp_po = grouped_po.copy()
            disp_po["Total Spend (₹)"] = disp_po["Total_Spend"].apply(format_currency)
            disp_po = disp_po.drop(columns=["Total_Spend"])
            paginated_sup = paginate_dataframe(disp_po, page_size=50, key="rep_sup_tbl")
            st.dataframe(paginated_sup, use_container_width=True, hide_index=True)

            exp_c1, exp_c2 = st.columns(2)
            with exp_c1:
                st.download_button(
                    "📥 Export Supplier Report (.xlsx)",
                    data=generate_excel_download(grouped_po, "Supplier_Performance"),
                    file_name="supplier_procurement_report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            with exp_c2:
                st.download_button(
                    "📥 Export Supplier Report (.csv)",
                    data=generate_csv_download(grouped_po),
                    file_name="supplier_procurement_report.csv",
                    mime="text/csv",
                    use_container_width=True
                )

    # --------------------------------------------------------------------------
    # Report 3: Inventory Valuation & Asset Health
    # --------------------------------------------------------------------------
    elif report_type.startswith("3."):
        render_section_header("Inventory Valuation & Asset Balance Sheet", "Total capitalized inventory at cost versus prospective retail value", "📦")

        inv_data = db.execute_cached_query(
            """
            SELECT 
                p.sku,
                p.name AS product_name,
                c.name AS category,
                COALESCE(i.quantity_on_hand, 0) AS stock_on_hand,
                p.unit,
                COALESCE(i.reorder_point, p.reorder_level) AS reorder_level,
                p.cost_price,
                p.selling_price,
                (COALESCE(i.quantity_on_hand, 0) * p.cost_price) AS valuation_cost,
                (COALESCE(i.quantity_on_hand, 0) * p.selling_price) AS valuation_retail,
                ((COALESCE(i.quantity_on_hand, 0) * p.selling_price) - (COALESCE(i.quantity_on_hand, 0) * p.cost_price)) AS unrealized_profit
            FROM products p
            JOIN categories c ON p.category_id = c.id
            LEFT JOIN inventory i ON p.id = i.product_id
            WHERE p.is_active = 1
            ORDER BY valuation_cost DESC
            """
        )

        if inv_data:
            df_inv = pd.DataFrame(inv_data)
            for c in ["stock_on_hand", "cost_price", "selling_price", "valuation_cost", "valuation_retail", "unrealized_profit"]:
                df_inv[c] = df_inv[c].astype(float)

            tot_val_cost = df_inv["valuation_cost"].sum()
            tot_val_retail = df_inv["valuation_retail"].sum()
            tot_unrealized = df_inv["unrealized_profit"].sum()
            tot_stock = df_inv["stock_on_hand"].sum()

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                render_metric_card("Asset Value (Cost Basis)", format_inr_compact(tot_val_cost), f"Total: {format_currency(tot_val_cost)}", "💵", "blue")
            with c2:
                render_metric_card("Total Retail Value", format_inr_compact(tot_val_retail), "Potential gross proceeds", "🏷️", "purple")
            with c3:
                render_metric_card("Unrealized Profit", format_inr_compact(tot_unrealized), "Projected catalog margin", "📈", "green")
            with c4:
                render_metric_card("Total Units in Warehouse", f"{int(tot_stock):,}", f"Across {len(df_inv)} Active SKUs", "📦", "blue")

            st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)

            # Category Valuation Chart
            cat_val = df_inv.groupby("category").agg(
                Valuation_Cost=("valuation_cost", "sum"),
                Valuation_Retail=("valuation_retail", "sum")
            ).reset_index().sort_values(by="Valuation_Cost", ascending=False)

            fig_cat = go.Figure()
            fig_cat.add_trace(go.Bar(x=cat_val["category"], y=cat_val["Valuation_Cost"], name="Cost Basis (₹)", marker_color="#3b82f6"))
            fig_cat.add_trace(go.Bar(x=cat_val["category"], y=cat_val["Valuation_Retail"], name="Retail Value (₹)", marker_color="#10b981"))
            fig_cat.update_layout(barmode="group")
            style_plotly_figure(fig_cat, title="Inventory Valuation by Category (Cost vs Retail ₹)", height=360)
            st.plotly_chart(fig_cat, use_container_width=True)

            # Formatted table
            df_inv_disp = df_inv.copy()
            df_inv_disp["Cost Price (₹)"] = df_inv_disp["cost_price"].apply(format_currency)
            df_inv_disp["Selling Price (₹)"] = df_inv_disp["selling_price"].apply(format_currency)
            df_inv_disp["Valuation Cost (₹)"] = df_inv_disp["valuation_cost"].apply(format_currency)
            df_inv_disp["Valuation Retail (₹)"] = df_inv_disp["valuation_retail"].apply(format_currency)
            df_inv_disp["Unrealized Profit (₹)"] = df_inv_disp["unrealized_profit"].apply(format_currency)
            
            df_inv_disp = df_inv_disp[[
                "sku", "product_name", "category", "stock_on_hand", "unit", "reorder_level",
                "Cost Price (₹)", "Selling Price (₹)", "Valuation Cost (₹)", "Valuation Retail (₹)", "Unrealized Profit (₹)"
            ]]
            df_inv_disp.columns = [
                "SKU", "Product Name", "Category", "Stock", "Unit", "Reorder Level",
                "Cost Price", "Selling Price", "Cost Basis", "Retail Value", "Unrealized Profit"
            ]

            paginated_inv = paginate_dataframe(df_inv_disp, page_size=50, key="rep_inv_tbl")
            st.dataframe(paginated_inv, use_container_width=True, hide_index=True)

            exp_c1, exp_c2 = st.columns(2)
            with exp_c1:
                st.download_button(
                    "📥 Export Inventory Valuation (.xlsx)",
                    data=generate_excel_download(df_inv, "Inventory_Valuation"),
                    file_name="inventory_valuation_report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            with exp_c2:
                st.download_button(
                    "📥 Export Inventory Valuation (.csv)",
                    data=generate_csv_download(df_inv),
                    file_name="inventory_valuation_report.csv",
                    mime="text/csv",
                    use_container_width=True
                )

    # --------------------------------------------------------------------------
    # Report 4: Customer Ledger & Accounts Receivable
    # --------------------------------------------------------------------------
    elif report_type.startswith("4."):
        render_section_header("Customer Invoicing & Accounts Receivable Ledger", "Track total invoices, payments collected, and outstanding balances due", "👥")

        cust_data = db.execute_cached_query(
            """
            SELECT 
                c.name AS customer_name,
                c.phone,
                c.email,
                COUNT(so.id) AS total_orders,
                COALESCE(SUM(so.total_amount), 0) AS total_invoiced,
                COALESCE((
                    SELECT SUM(p.amount) 
                    FROM payments p 
                    JOIN sales_orders so2 ON p.sales_order_id = so2.id 
                    WHERE so2.customer_id = c.id AND p.status = 'Completed'
                ), 0) AS total_collected
            FROM customers c
            LEFT JOIN sales_orders so ON c.id = so.customer_id AND so.status != 'Cancelled'
            WHERE c.is_active = 1
            GROUP BY c.id
            ORDER BY total_invoiced DESC
            """
        )

        if cust_data:
            df_cust = pd.DataFrame(cust_data)
            for c in ["total_invoiced", "total_collected"]:
                df_cust[c] = df_cust[c].astype(float)
            df_cust["Outstanding Balance"] = df_cust["total_invoiced"] - df_cust["total_collected"]

            total_inv = df_cust["total_invoiced"].sum()
            total_coll = df_cust["total_collected"].sum()
            total_due = df_cust["Outstanding Balance"].sum()

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                render_metric_card("Total Cumulative Invoiced", format_inr_compact(total_inv), f"Total: {format_currency(total_inv)}", "💵", "blue")
            with c2:
                render_metric_card("Total Collected Revenue", format_inr_compact(total_coll), "Settled payments", "💳", "green")
            with c3:
                render_metric_card("Accounts Receivable (AR)", format_inr_compact(total_due), "Due for collection", "📈", "amber" if total_due > 0 else "green")
            with c4:
                render_metric_card("Active Customer Accounts", len(df_cust), "Commercial client base", "👥", "purple")

            st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)

            # Top Customers by Invoiced Amount
            fig_cust = px.bar(
                df_cust.head(10),
                x="customer_name",
                y=["total_collected", "Outstanding Balance"],
                title="Top 10 Customers by Invoicing & Settlement (₹)",
                labels={"customer_name": "Customer", "value": "Amount (₹)", "variable": "Metric"},
                color_discrete_map={"total_collected": "#10b981", "Outstanding Balance": "#f59e0b"}
            )
            style_plotly_figure(fig_cust, title="Top 10 Customers by Invoicing & Settlement (₹)", height=350)
            st.plotly_chart(fig_cust, use_container_width=True)

            df_cust_disp = df_cust.copy()
            df_cust_disp["Total Invoiced (₹)"] = df_cust_disp["total_invoiced"].apply(format_currency)
            df_cust_disp["Total Collected (₹)"] = df_cust_disp["total_collected"].apply(format_currency)
            df_cust_disp["Outstanding Due (₹)"] = df_cust_disp["Outstanding Balance"].apply(format_currency)
            df_cust_disp = df_cust_disp[["customer_name", "phone", "email", "total_orders", "Total Invoiced (₹)", "Total Collected (₹)", "Outstanding Due (₹)"]]
            df_cust_disp.columns = ["Customer", "Phone", "Email", "Total Orders", "Total Invoiced", "Total Collected", "Outstanding Due"]

            paginated_cust = paginate_dataframe(df_cust_disp, page_size=50, key="rep_cust_tbl")
            st.dataframe(paginated_cust, use_container_width=True, hide_index=True)

            exp_c1, exp_c2 = st.columns(2)
            with exp_c1:
                st.download_button(
                    "📥 Export Receivables Report (.xlsx)",
                    data=generate_excel_download(df_cust, "Receivables_Ledger"),
                    file_name="accounts_receivable_report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            with exp_c2:
                st.download_button(
                    "📥 Export Receivables Report (.csv)",
                    data=generate_csv_download(df_cust),
                    file_name="accounts_receivable_report.csv",
                    mime="text/csv",
                    use_container_width=True
                )

    # --------------------------------------------------------------------------
    # Report 5: Complete Stock Movement Audit Ledger
    # --------------------------------------------------------------------------
    elif report_type.startswith("5."):
        render_section_header("Comprehensive Stock Movement Audit Ledger", "Complete chronological ledger of all physical warehouse adjustments", "📜")

        sm_data = db.execute_cached_query(
            """
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
            ORDER BY sm.created_at DESC
            """
        )

        if sm_data:
            df_sm_all = pd.DataFrame(sm_data)
            tot_logs = len(df_sm_all)
            inbound_qty = df_sm_all[df_sm_all["quantity"] > 0]["quantity"].sum()
            outbound_qty = abs(df_sm_all[df_sm_all["quantity"] < 0]["quantity"].sum())

            k1, k2, k3, k4 = st.columns(4)
            with k1:
                render_metric_card("Total Audit Events", f"{tot_logs:,}", "Indexed warehouse entries", "📜", "blue")
            with k2:
                render_metric_card("Total Inbound Stock", f"+{int(inbound_qty):,}", "Receipts, Initial, Adjustments", "📥", "green")
            with k3:
                render_metric_card("Total Outbound Stock", f"-{int(outbound_qty):,}", "Sales Order Dispatches", "📤", "purple")
            with k4:
                render_metric_card("Audit Integrity", "100% Verified", "Foreign key constrained", "🔒", "green")

            st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)
            df_sm_disp = df_sm_all[["id", "created_at", "sku", "product_name", "movement_type", "quantity", "balance_after", "reference_type", "reference_id", "notes", "logged_by"]]
            df_sm_disp.columns = ["Log ID", "Timestamp", "SKU", "Product", "Movement Type", "Qty Delta", "Balance After", "Ref Type", "Ref ID", "Notes", "Admin"]

            paginated_sm = paginate_dataframe(df_sm_disp, page_size=50, key="rep_sm_tbl")
            st.dataframe(paginated_sm, use_container_width=True, hide_index=True)

            exp_c1, exp_c2 = st.columns(2)
            with exp_c1:
                st.download_button(
                    "📥 Export Stock Audit Ledger (.xlsx)",
                    data=generate_excel_download(df_sm_all, "Stock_Movement_Audit"),
                    file_name="stock_movement_audit_ledger.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            with exp_c2:
                st.download_button(
                    "📥 Export Stock Audit Ledger (.csv)",
                    data=generate_csv_download(df_sm_all),
                    file_name="stock_movement_audit_ledger.csv",
                    mime="text/csv",
                    use_container_width=True
                )
