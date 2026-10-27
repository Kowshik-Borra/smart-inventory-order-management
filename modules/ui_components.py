"""
SIOM Enterprise UI Components & Design System Helper
Provides reusable UI helpers, custom dark ERP CSS styling, status badges, metric cards,
welcome banner, page headers, pagination, role access control, currency formatters,
and dark-themed Plotly chart styling utilities.
"""

import os
import html
from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# -----------------------------------------------------------------------------
# Global ERP Theme CSS Injection from assets/style.css
# -----------------------------------------------------------------------------

def apply_custom_styles():
    """Loads and injects centralized modern SaaS / ERP CSS from assets/style.css."""
    css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "style.css")
    if os.path.exists(css_path):
        try:
            with open(css_path, "r", encoding="utf-8") as f:
                css_content = f.read()
            st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
        except Exception:
            pass


# -----------------------------------------------------------------------------
# Currency Formatting Helpers (INR - Indian Rupee & Standard Format)
# -----------------------------------------------------------------------------

def format_currency(amount: Union[int, float, Decimal, str, None]) -> str:
    """Formats numeric amount into clean Indian Rupee notation e.g. ₹54,999.00."""
    if amount is None:
        return "₹0.00"
    try:
        val = float(amount)
        return f"₹{val:,.2f}"
    except (ValueError, TypeError):
        return str(amount)


def format_inr_compact(amount: Union[int, float, Decimal, str, None]) -> str:
    """Formats large amounts into readable compact notation e.g. ₹8.5L, ₹54.2K, ₹1.2Cr."""
    if amount is None:
        return "₹0"
    try:
        val = float(amount)
        if abs(val) >= 10000000:
            return f"₹{val / 10000000:.2f}Cr"
        elif abs(val) >= 100000:
            return f"₹{val / 100000:.2f}L"
        elif abs(val) >= 1000:
            return f"₹{val / 1000:.1f}K"
        else:
            return f"₹{val:,.0f}"
    except (ValueError, TypeError):
        return str(amount)


# -----------------------------------------------------------------------------
# Role-Based Access Control Helper (Security)
# -----------------------------------------------------------------------------

def require_role(allowed_roles: Union[str, List[str]]) -> bool:
    """
    Enforces role-based access control.
    Denies access by default if no valid role is found in session.
    Returns True if user role is in allowed_roles or is Super Admin, otherwise halts execution.
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    user_role = st.session_state.get("role")
    if not user_role or not st.session_state.get("authenticated", False):
        st.error("🚫 **Access Denied**: Authentication is required to access this resource.")
        st.stop()
        return False
    
    # Super Admin has unrestricted access to all modules
    if user_role == "Super Admin" or user_role in allowed_roles:
        return True

    st.error("🚫 **Access Restricted**: You do not have permission to view or modify this section.")
    st.info(f"Your current role is **{html.escape(str(user_role))}**. Required role(s): **{', '.join(html.escape(r) for r in allowed_roles)}**.")
    st.stop()
    return False


# -----------------------------------------------------------------------------
# Reusable UI Component Functions
# -----------------------------------------------------------------------------

def render_welcome_banner(title: str = "Welcome to SIOM", subtitle: str = "Smart Inventory & Order Management System"):
    """Renders high-impact dark hero banner for the dashboard."""
    safe_title = html.escape(str(title))
    safe_sub = html.escape(str(subtitle))
    st.markdown(
        f"""
        <div class="siom-welcome-banner">
            <div>
                <h1 class="siom-welcome-title">{safe_title}</h1>
                <div class="siom-welcome-sub">{safe_sub}</div>
            </div>
            <div style="font-size: 32px; background: rgba(37, 99, 235, 0.2); padding: 8px 16px; border-radius: 10px; border: 1px solid rgba(59, 130, 246, 0.3);">
                📦
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_page_header(title: str, subtitle: str, icon: str = "📦", badge_text: Optional[str] = None):
    """Renders a standard enterprise page header with HTML-escaped title, subtitle, and optional badge."""
    safe_title = html.escape(str(title))
    safe_subtitle = html.escape(str(subtitle))
    safe_icon = html.escape(str(icon))
    badge_html = f'<span class="siom-badge siom-badge-blue">{html.escape(str(badge_text))}</span>' if badge_text else ""
    
    st.markdown(
        f"""
        <div class="siom-page-header">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h1 class="siom-page-title">
                    <span>{safe_icon}</span> {safe_title} {badge_html}
                </h1>
            </div>
            <p class="siom-page-subtitle">{safe_subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_metric_card(
    title: str,
    value: Union[str, int, float, Decimal],
    subtext: Optional[str] = None,
    icon: Optional[str] = None,
    accent: str = "blue"
):
    """
    Renders an HTML-based ERP metric card with customizable top accent bar.
    accents: 'blue', 'green', 'amber', 'purple', 'red'
    """
    safe_title = html.escape(str(title))
    safe_val = html.escape(str(value))
    icon_html = f'<span class="siom-metric-icon">{html.escape(str(icon))}</span>' if icon else ""
    sub_html = f'<div class="siom-metric-sub">{html.escape(str(subtext))}</div>' if subtext else ""
    
    st.markdown(
        f"""
        <div class="siom-metric-card siom-metric-accent-{accent}">
            <div class="siom-metric-header">
                <span class="siom-metric-title">{safe_title}</span>
                {icon_html}
            </div>
            <div class="siom-metric-val">{safe_val}</div>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True
    )


def render_status_badge(status: str) -> str:
    """Returns styled HTML badge string for standard system statuses with escaped content."""
    safe_status = html.escape(str(status))
    status_lower = str(status).strip().lower()
    
    # Green variants
    if status_lower in ["active", "delivered", "completed", "received", "healthy", "ok", "paid", "success", "in stock"]:
        cls = "siom-badge-green"
        icon = "●"
    # Amber / Warning variants
    elif status_lower in ["low stock", "pending", "partially received", "processing", "in transit", "packed", "partial", "draft", "warning"]:
        cls = "siom-badge-amber"
        icon = "▲"
    # Red variants
    elif status_lower in ["out of stock", "inactive", "cancelled", "failed", "returned", "unpaid", "danger", "error"]:
        cls = "siom-badge-red"
        icon = "■"
    # Blue / Info variants
    elif status_lower in ["ordered", "confirmed", "shipped", "dispatched", "info"]:
        cls = "siom-badge-blue"
        icon = "✦"
    else:
        cls = "siom-badge-gray"
        icon = "•"
        
    return f'<span class="siom-badge {cls}">{icon} {safe_status}</span>'


def render_section_header(title: str, subtitle: Optional[str] = None, icon: Optional[str] = None):
    """Renders a section divider with title and optional helper subtitle."""
    icon_str = f"{html.escape(str(icon))} " if icon else ""
    safe_title = html.escape(str(title))
    st.markdown(f'<div class="siom-section-header">{icon_str}{safe_title}</div>', unsafe_allow_html=True)
    if subtitle:
        safe_sub = html.escape(str(subtitle))
        st.markdown(f'<div class="siom-section-sub">{safe_sub}</div>', unsafe_allow_html=True)


def render_empty_state(message: str, hint: Optional[str] = None, icon: str = "📦"):
    """Renders a clean empty-state placeholder when tables or queries return empty."""
    safe_msg = html.escape(str(message))
    safe_hint = html.escape(str(hint)) if hint else ""
    safe_icon = html.escape(str(icon))
    hint_html = f'<p class="siom-empty-hint">{safe_hint}</p>' if hint else ""
    st.markdown(
        f"""
        <div class="siom-empty-state">
            <div class="siom-empty-icon">{safe_icon}</div>
            <p class="siom-empty-text">{safe_msg}</p>
            {hint_html}
        </div>
        """,
        unsafe_allow_html=True
    )


# -----------------------------------------------------------------------------
# Table Pagination Helper (50 rows per page default)
# -----------------------------------------------------------------------------

def paginate_dataframe(
    df: pd.DataFrame,
    page_size: int = 50,
    key: str = "df_page",
    key_prefix: Optional[str] = None,
    **kwargs: Any
) -> pd.DataFrame:
    """
    Paginates a pandas DataFrame for Streamlit rendering with 50 rows per page.
    Returns the sliced DataFrame for the selected page.
    """
    if df is None or len(df) == 0:
        return df

    final_key = key_prefix if key_prefix is not None else key
    total_rows = len(df)
    if total_rows <= page_size:
        return df

    total_pages = (total_rows + page_size - 1) // page_size
    
    p_col1, p_col2, p_col3 = st.columns([1, 2, 1])
    with p_col2:
        current_page = st.number_input(
            f"Page (1 to {total_pages} — {total_rows} total records)",
            min_value=1,
            max_value=total_pages,
            value=1,
            step=1,
            key=f"{final_key}_num"
        )
    
    start_idx = (current_page - 1) * page_size
    end_idx = min(start_idx + page_size, total_rows)
    return df.iloc[start_idx:end_idx]


# -----------------------------------------------------------------------------
# Modern Dark Plotly Chart Theming Helpers
# -----------------------------------------------------------------------------

ERP_PLOT_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#06b6d4", "#ec4899", "#64748b"]

def get_erp_chart_layout(title: str = "", height: int = 340) -> Dict[str, Any]:
    """Returns standard high-contrast dark ERP Plotly layout configuration."""
    return dict(
        title=dict(
            text=f"<b>{html.escape(str(title))}</b>" if title else "",
            font=dict(family="Inter, sans-serif", size=14, color="#ffffff"),
            x=0.01,
            y=0.96
        ),
        paper_bgcolor="#151e2e",
        plot_bgcolor="#151e2e",
        font=dict(family="Inter, sans-serif", size=12, color="#94a3b8"),
        margin=dict(l=24, r=24, t=44 if title else 20, b=24),
        height=height,
        hoverlabel=dict(
            bgcolor="#0b1220",
            font_size=12,
            font_family="Inter, sans-serif",
            font_color="#ffffff",
            bordercolor="#334155"
        ),
        xaxis=dict(
            showgrid=True,
            gridcolor="#28374d",
            zeroline=False,
            linecolor="#28374d",
            tickfont=dict(size=11, color="#94a3b8")
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#28374d",
            zeroline=False,
            linecolor="#28374d",
            tickfont=dict(size=11, color="#94a3b8")
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11, color="#cbd5e1")
        )
    )


def style_plotly_figure(fig: go.Figure, title: str = "", height: int = 340) -> go.Figure:
    """Applies the dark ERP layout configuration to any Plotly figure."""
    fig.update_layout(**get_erp_chart_layout(title=title, height=height))
    return fig
