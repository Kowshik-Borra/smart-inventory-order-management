"""
Executive Dashboard Module:
Real-time KPIs, interactive Plotly visualizations, low-stock warnings,
monthly procurement vs sales trends, and live unified activity feed.
"""

from datetime import date, timedelta
from decimal import Decimal
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import database as db
from modules.ui_components import (
    render_welcome_banner,
    render_metric_card,
    render_section_header,
    render_empty_state,
    style_plotly_figure,
    format_currency,
    format_inr_compact,
    ERP_PLOT_COLORS
)

def render_dashboard_page():
    # --------------------------------------------------------------------------
    # 1. Top Hero Welcome Banner
    # --------------------------------------------------------------------------
    render_welcome_banner(
        title="Welcome to SIOM",
        subtitle="Smart Inventory & Order Management System — Real-time Operations & Valuation Center"
    )

    # --------------------------------------------------------------------------
    # 2. Filter Bar
    # --------------------------------------------------------------------------
    with st.container():
        st.markdown('<div class="siom-filter-panel">', unsafe_allow_html=True)
        f_col1, f_col2, f_col3 = st.columns([2, 2, 1])
        with f_col1:
            date_range = st.date_input(
                "📅 Reporting Date Range",
                value=[date.today() - timedelta(days=365), date.today()],
                key="dash_date_range"
            )
        with f_col2:
            cats = db.execute_query("SELECT id, name FROM categories WHERE is_active = 1 ORDER BY name ASC")
            cat_map = {"All Categories": None}
            for c in cats:
                cat_map[c["name"]] = c["id"]
            selected_cat = st.selectbox("🏷️ Filter Category", list(cat_map.keys()), key="dash_cat_sel")
        with f_col3:
            st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
            if st.button("🔄 Refresh Data", key="dash_refresh", use_container_width=True):
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # Parse date range
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = date.today() - timedelta(days=365), date.today()

    cat_id = cat_map[selected_cat]

    # --------------------------------------------------------------------------
    # 3. Real-Time Aggregate KPIs
    # --------------------------------------------------------------------------
    # Core Counts
    prod_count = db.execute_one(
        "SELECT COUNT(*) as count FROM products WHERE is_active = 1 " + ("AND category_id = %s" if cat_id else ""),
        (cat_id,) if cat_id else ()
    )["count"]

    cat_count = db.execute_one("SELECT COUNT(*) as count FROM categories WHERE is_active = 1")["count"]
    supp_count = db.execute_one("SELECT COUNT(*) as count FROM suppliers WHERE is_active = 1")["count"]
    cust_count = db.execute_one("SELECT COUNT(*) as count FROM customers WHERE is_active = 1")["count"]

    # Inventory Valuation & Stock Distribution
    inv_stats_query = """
        SELECT 
            COALESCE(SUM(i.quantity_on_hand * p.cost_price), 0) AS total_val,
            COALESCE(SUM(i.quantity_on_hand), 0) AS total_units,
            COUNT(CASE WHEN i.quantity_on_hand <= COALESCE(i.reorder_point, p.reorder_level) AND i.quantity_on_hand > 0 THEN 1 END) AS low_stock_count,
            COUNT(CASE WHEN i.quantity_on_hand = 0 THEN 1 END) AS out_of_stock_count,
            COUNT(CASE WHEN i.quantity_on_hand > COALESCE(i.reorder_point, p.reorder_level) THEN 1 END) AS in_stock_count
        FROM products p
        LEFT JOIN inventory i ON p.id = i.product_id
        WHERE p.is_active = 1
    """
    if cat_id:
        inv_stats_query += " AND p.category_id = %s"
        inv_stats = db.execute_one(inv_stats_query, (cat_id,))
    else:
        inv_stats = db.execute_one(inv_stats_query)

    inv_value = Decimal(str(inv_stats["total_val"]))
    total_stock_units = inv_stats["total_units"]
    low_stock_num = inv_stats["low_stock_count"]
    out_of_stock_num = inv_stats["out_of_stock_count"]
    in_stock_num = inv_stats["in_stock_count"]

    # Pending Orders
    pending_po = db.execute_one("SELECT COUNT(*) as count FROM purchase_orders WHERE status IN ('Ordered', 'Partially Received', 'Draft')")["count"]
    pending_so = db.execute_one("SELECT COUNT(*) as count FROM sales_orders WHERE status IN ('Draft', 'Confirmed', 'Processing', 'Shipped')")["count"]

    # Period Sales & Purchases
    sales_kpi = db.execute_one(
        """
        SELECT 
            COALESCE(SUM(so.total_amount), 0) AS total_revenue,
            COUNT(so.id) AS orders_count
        FROM sales_orders so
        WHERE so.order_date BETWEEN %s AND %s AND so.status != 'Cancelled'
        """,
        (start_date, end_date)
    )
    period_revenue = Decimal(str(sales_kpi["total_revenue"]))
    period_sales_orders = sales_kpi["orders_count"]

    purchases_kpi = db.execute_one(
        """
        SELECT 
            COALESCE(SUM(po.total_amount), 0) AS total_purchases,
            COUNT(po.id) AS po_count
        FROM purchase_orders po
        WHERE po.order_date BETWEEN %s AND %s AND po.status != 'Cancelled'
        """,
        (start_date, end_date)
    )
    period_purchases = Decimal(str(purchases_kpi["total_purchases"]))
    period_po_count = purchases_kpi["po_count"]

    # --------------------------------------------------------------------------
    # 4. KPI Cards Row 1 & Row 2
    # --------------------------------------------------------------------------
    render_section_header("Executive KPI Command Center", "High-level summary of products, stock, customers, suppliers, sales, and purchases", "📊")
    
    # Row 1: Master Entity Counts
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        render_metric_card(
            title="Products Master",
            value=f"{prod_count:,}",
            subtext=f"📦 {cat_count} Active Categories",
            icon="📦",
            accent="blue"
        )
    with k2:
        render_metric_card(
            title="Warehouse Stock",
            value=f"{total_stock_units:,}",
            subtext=f"💵 Valuation: {format_inr_compact(inv_value)}",
            icon="🔢",
            accent="purple"
        )
    with k3:
        render_metric_card(
            title="Customers",
            value=f"{cust_count:,}",
            subtext="👥 Registered Accounts",
            icon="👥",
            accent="green"
        )
    with k4:
        render_metric_card(
            title="Suppliers",
            value=f"{supp_count:,}",
            subtext="🏢 Active B2B Vendors",
            icon="🏢",
            accent="blue"
        )

    # Row 2: Financial & Operational Metrics
    st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True)
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        render_metric_card(
            title="Sales Revenue",
            value=format_inr_compact(period_revenue),
            subtext=f"🛍️ {period_sales_orders} Orders ({format_currency(period_revenue)})",
            icon="💰",
            accent="green"
        )
    with f2:
        render_metric_card(
            title="Purchases Spend",
            value=format_inr_compact(period_purchases),
            subtext=f"📥 {period_po_count} Inbound POs ({format_currency(period_purchases)})",
            icon="🛒",
            accent="purple"
        )
    with f3:
        crit_stock_total = low_stock_num + out_of_stock_num
        render_metric_card(
            title="Low Stock Items",
            value=crit_stock_total,
            subtext=f"⚠️ {low_stock_num} Low | {out_of_stock_num} Out of Stock" if crit_stock_total > 0 else "✅ All Stock Healthy",
            icon="⚠️",
            accent="amber" if crit_stock_total > 0 else "green"
        )
    with f4:
        pending_total = pending_po + pending_so
        render_metric_card(
            title="Pending Orders",
            value=pending_total,
            subtext=f"🛒 {pending_so} Sales | 📥 {pending_po} Inbound POs",
            icon="⏳",
            accent="blue" if pending_total > 0 else "green"
        )

    st.markdown("---")

    # --------------------------------------------------------------------------
    # 5. Interactive Charts (Sales Trend, Purchases vs Sales, Inventory Status, Top Sellers)
    # --------------------------------------------------------------------------
    render_section_header("Business Intelligence & Visual Analytics", "Monthly revenue trajectories, procurement vs sales comparison, and stock distribution", "📈")
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        # Purchase vs Sales Comparison by Month
        monthly_comparison = db.execute_query(
            """
            SELECT 
                DATE_FORMAT(order_date, '%Y-%m') AS month_label,
                SUM(total_amount) AS sales_amount
            FROM sales_orders
            WHERE status != 'Cancelled' AND order_date BETWEEN %s AND %s
            GROUP BY DATE_FORMAT(order_date, '%Y-%m')
            ORDER BY month_label ASC
            """,
            (start_date, end_date)
        )
        monthly_po = db.execute_query(
            """
            SELECT 
                DATE_FORMAT(order_date, '%Y-%m') AS month_label,
                SUM(total_amount) AS purchase_amount
            FROM purchase_orders
            WHERE status != 'Cancelled' AND order_date BETWEEN %s AND %s
            GROUP BY DATE_FORMAT(order_date, '%Y-%m')
            ORDER BY month_label ASC
            """,
            (start_date, end_date)
        )

        sales_df = pd.DataFrame(monthly_comparison) if monthly_comparison else pd.DataFrame(columns=["month_label", "sales_amount"])
        po_df = pd.DataFrame(monthly_po) if monthly_po else pd.DataFrame(columns=["month_label", "purchase_amount"])
        
        merged_df = pd.merge(sales_df, po_df, on="month_label", how="outer").fillna(0).sort_values("month_label")

        if not merged_df.empty:
            merged_df["sales_amount"] = merged_df["sales_amount"].astype(float)
            merged_df["purchase_amount"] = merged_df["purchase_amount"].astype(float)

            fig_comp = go.Figure()
            fig_comp.add_trace(go.Bar(
                x=merged_df["month_label"],
                y=merged_df["sales_amount"],
                name="Sales (₹)",
                marker_color="#10b981"
            ))
            fig_comp.add_trace(go.Bar(
                x=merged_df["month_label"],
                y=merged_df["purchase_amount"],
                name="Purchases (₹)",
                marker_color="#8b5cf6"
            ))
            fig_comp.update_layout(barmode="group")
            style_plotly_figure(fig_comp, title="Monthly Purchases vs Sales (₹)", height=320)
            st.plotly_chart(fig_comp, use_container_width=True)
        else:
            render_empty_state("No sales or purchase order data recorded in selected range.", icon="📅")

    with chart_col2:
        # Inventory Stock Status Breakdown Donut Chart
        status_data = [
            {"Status": "In Stock (Healthy)", "Count": in_stock_num, "Color": "#10b981"},
            {"Status": "Low Stock (Reorder)", "Count": low_stock_num, "Color": "#f59e0b"},
            {"Status": "Out of Stock (0 Units)", "Count": out_of_stock_num, "Color": "#ef4444"}
        ]
        status_df = pd.DataFrame([d for d in status_data if d["Count"] > 0])
        
        if not status_df.empty:
            fig_donut = px.pie(
                status_df,
                names="Status",
                values="Count",
                hole=0.55,
                color="Status",
                color_discrete_map={
                    "In Stock (Healthy)": "#10b981",
                    "Low Stock (Reorder)": "#f59e0b",
                    "Out of Stock (0 Units)": "#ef4444"
                }
            )
            fig_donut.update_traces(
                textposition="inside",
                textinfo="percent+label",
                marker=dict(line=dict(color="#1e293b", width=2))
            )
            style_plotly_figure(fig_donut, title="Inventory Stock Status Health", height=320)
            st.plotly_chart(fig_donut, use_container_width=True)
        else:
            render_empty_state("No inventory records found.", icon="📦")

    # --------------------------------------------------------------------------
    # 6. Top Selling Products & Category Valuation
    # --------------------------------------------------------------------------
    st.markdown("<div style='height: 8px'></div>", unsafe_allow_html=True)
    t_col1, t_col2 = st.columns(2)

    with t_col1:
        top_prods = db.execute_query(
            """
            SELECT 
                p.name AS product_name,
                SUM(soi.quantity) AS units_sold,
                SUM(soi.line_total) AS total_revenue
            FROM sales_order_items soi
            JOIN products p ON soi.product_id = p.id
            JOIN sales_orders so ON soi.sales_order_id = so.id
            WHERE so.status != 'Cancelled'
            GROUP BY p.id
            ORDER BY total_revenue DESC
            LIMIT 5
            """
        )
        if top_prods:
            df_top = pd.DataFrame(top_prods)
            df_top["total_revenue"] = df_top["total_revenue"].astype(float)
            fig_top = px.bar(
                df_top,
                x="total_revenue",
                y="product_name",
                orientation="h",
                labels={"total_revenue": "Revenue (₹)", "product_name": "Product"},
                color_discrete_sequence=["#3b82f6"]
            )
            fig_top.update_traces(
                texttemplate="₹%{x:,.0f}",
                textposition="outside",
                marker=dict(line=dict(width=0), opacity=0.9)
            )
            style_plotly_figure(fig_top, title="Top 5 Products by Sales Revenue (₹)", height=300)
            st.plotly_chart(fig_top, use_container_width=True)
        else:
            render_empty_state("No sales transactions to compute top products.", icon="📦")

    with t_col2:
        cat_dist = db.execute_query(
            """
            SELECT 
                c.name AS category_name,
                COALESCE(SUM(i.quantity_on_hand * p.cost_price), 0) AS category_val
            FROM categories c
            LEFT JOIN products p ON c.id = p.category_id AND p.is_active = 1
            LEFT JOIN inventory i ON p.id = i.product_id
            WHERE c.is_active = 1
            GROUP BY c.id
            HAVING category_val > 0
            ORDER BY category_val DESC
            LIMIT 6
            """
        )
        if cat_dist:
            df_cat = pd.DataFrame(cat_dist)
            df_cat["category_val"] = df_cat["category_val"].astype(float)
            fig_cat = px.bar(
                df_cat,
                x="category_val",
                y="category_name",
                orientation="h",
                labels={"category_val": "Stock Valuation (₹)", "category_name": "Category"},
                color_discrete_sequence=["#06b6d4"]
            )
            fig_cat.update_traces(
                texttemplate="₹%{x:,.0f}",
                textposition="outside",
                marker=dict(line=dict(width=0), opacity=0.9)
            )
            style_plotly_figure(fig_cat, title="Inventory Valuation by Category (₹)", height=300)
            st.plotly_chart(fig_cat, use_container_width=True)
        else:
            render_empty_state("No category valuation data found.", icon="🏷️")

    st.markdown("---")

    # --------------------------------------------------------------------------
    # 7. Low Stock Alert Section
    # --------------------------------------------------------------------------
    render_section_header("⚠️ Low Stock & Restock Alerts", "Critical warehouse items at or below designated reorder threshold", "⚠️")
    low_stock_records = db.execute_query(
        """
        SELECT 
            p.sku,
            p.name,
            c.name AS category,
            COALESCE(i.quantity_on_hand, 0) AS on_hand,
            COALESCE(i.reorder_point, p.reorder_level) AS reorder_level,
            p.unit,
            p.cost_price
        FROM products p
        JOIN categories c ON p.category_id = c.id
        LEFT JOIN inventory i ON p.id = i.product_id
        WHERE p.is_active = 1 AND COALESCE(i.quantity_on_hand, 0) <= COALESCE(i.reorder_point, p.reorder_level)
        ORDER BY COALESCE(i.quantity_on_hand, 0) ASC
        """
    )
    if low_stock_records:
        st.warning(f"🚨 **{len(low_stock_records)} item(s)** require procurement replenishment:")
        df_ls = pd.DataFrame(low_stock_records)
        df_ls["Cost Price (₹)"] = df_ls["cost_price"].apply(format_currency)
        df_ls["Status"] = df_ls["on_hand"].apply(lambda q: "🔴 OUT OF STOCK" if q == 0 else "⚠️ LOW STOCK")
        df_ls_disp = df_ls[["sku", "name", "category", "on_hand", "reorder_level", "unit", "Cost Price (₹)", "Status"]]
        df_ls_disp.columns = ["SKU", "Product Name", "Category", "Stock on Hand", "Reorder Level", "Unit", "Unit Cost", "Alert Level"]
        st.dataframe(df_ls_disp, use_container_width=True, hide_index=True)
    else:
        st.success("✅ All products have sufficient stock. Warehouse inventory is operating at optimal levels.")

    st.markdown("---")

    # --------------------------------------------------------------------------
    # 8. Unified Recent Activity Feed
    # --------------------------------------------------------------------------
    render_section_header("🕒 Recent Activity & Pipeline Feed", "Real-time transactions across sales orders, goods receipts, and warehouse adjustments", "🕒")
    r_col1, r_col2 = st.columns(2)

    with r_col1:
        st.markdown("**🛒 Latest Customer Sales Orders**")
        recent_so = db.execute_query(
            """
            SELECT 
                so.order_number,
                c.name AS customer,
                so.order_date,
                so.status,
                so.total_amount
            FROM sales_orders so
            JOIN customers c ON so.customer_id = c.id
            ORDER BY so.created_at DESC
            LIMIT 6
            """
        )
        if recent_so:
            df_r_so = pd.DataFrame(recent_so)
            df_r_so["Total Amount"] = df_r_so["total_amount"].apply(format_currency)
            df_r_so_disp = df_r_so[["order_number", "customer", "order_date", "status", "Total Amount"]]
            df_r_so_disp.columns = ["Order #", "Customer", "Date", "Status", "Amount"]
            st.dataframe(df_r_so_disp, use_container_width=True, hide_index=True)
        else:
            render_empty_state("No recent sales orders.", icon="🛍️")

    with r_col2:
        st.markdown("**📥 Latest Inbound Purchase Receipts**")
        recent_po = db.execute_query(
            """
            SELECT 
                po.po_number,
                s.name AS supplier,
                po.order_date,
                po.status,
                po.total_amount
            FROM purchase_orders po
            JOIN suppliers s ON po.supplier_id = s.id
            ORDER BY po.created_at DESC
            LIMIT 6
            """
        )
        if recent_po:
            df_r_po = pd.DataFrame(recent_po)
            df_r_po["Total Amount"] = df_r_po["total_amount"].apply(format_currency)
            df_r_po_disp = df_r_po[["po_number", "supplier", "order_date", "status", "Total Amount"]]
            df_r_po_disp.columns = ["PO #", "Supplier", "Date", "Status", "Amount"]
            st.dataframe(df_r_po_disp, use_container_width=True, hide_index=True)
        else:
            render_empty_state("No recent purchase orders.", icon="📥")
