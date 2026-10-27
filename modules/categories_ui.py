"""
Category Management Module: Category master CRUD, assigned product counts,
category shortcut codes, and relational safe deletion / deactivation.
"""

import html
import logging
import streamlit as st
import pandas as pd
import database as db
from modules.ui_components import (
    render_page_header,
    render_section_header,
    render_empty_state,
    paginate_dataframe
)

logger = logging.getLogger("siom.categories")


def render_categories_page():
    render_page_header(
        title="Category Master Management",
        subtitle="Organize products into functional taxonomy, product groups, shortcut codes, and department structures.",
        icon="🏷️"
    )

    # --------------------------------------------------------------------------
    # 1. Add New Category Expander
    # --------------------------------------------------------------------------
    with st.expander("➕ Add New Category", expanded=False):
        with st.form("add_category_form", clear_on_submit=True):
            col_cn, col_cs = st.columns([2, 1])
            with col_cn:
                cat_name = st.text_input("Category Name *", placeholder="e.g. Gaming Accessories")
            with col_cs:
                cat_shortcut = st.text_input(
                    "Category Shortcut *",
                    placeholder="e.g. GAM",
                    help="2–5 uppercase letters/numbers for product IDs (e.g., GAM-001)"
                )

            cat_desc = st.text_area("Description", placeholder="Brief description of the product class or items grouped here...")
            cat_active = st.checkbox("Active Category", value=True)
            create_btn = st.form_submit_button("Create Category", type="primary", use_container_width=True)

            if create_btn:
                if not cat_name.strip():
                    st.error("Category Name is required.")
                else:
                    valid_short, short_err, clean_shortcut = db.validate_category_shortcut(cat_shortcut)
                    if not valid_short:
                        st.error(short_err)
                    else:
                        with st.spinner("Saving new category..."):
                            dup = db.execute_one("SELECT id FROM categories WHERE name = %s", (cat_name.strip(),))
                            if dup:
                                st.error("A category with this name already exists.")
                            else:
                                with db.get_db_transaction() as (cursor, conn):
                                    cursor.execute(
                                        "INSERT INTO categories (name, shortcut, description, is_active) VALUES (%s, %s, %s, %s)",
                                        (cat_name.strip(), clean_shortcut, cat_desc.strip(), 1 if cat_active else 0)
                                    )
                                    new_cat_id = cursor.lastrowid
                                    cursor.execute(
                                        "INSERT INTO document_sequences (seq_name, next_val) VALUES (%s, %s) ON DUPLICATE KEY UPDATE next_val = next_val",
                                        (f"PROD_CAT_{new_cat_id}", 0)
                                    )
                                st.toast(f"Category '{cat_name}' (Shortcut: {clean_shortcut}) created successfully!", icon="✅")
                                st.rerun()

    # --------------------------------------------------------------------------
    # 2. Search, Filter & Category Table
    # --------------------------------------------------------------------------
    st.markdown('<div class="siom-filter-panel">', unsafe_allow_html=True)
    col_search, col_filter = st.columns([3, 1])
    with col_search:
        search_query = st.text_input("Search Categories", placeholder="Search by name, shortcut, or description...")
    with col_filter:
        status_filter = st.selectbox("Status", ["All", "Active Only", "Inactive Only"], key="cat_stat_filt")
    st.markdown('</div>', unsafe_allow_html=True)

    query = """
        SELECT 
            c.id, 
            c.name, 
            c.shortcut,
            c.description, 
            c.is_active, 
            c.created_at,
            COUNT(p.id) AS product_count
        FROM categories c
        LEFT JOIN products p ON c.id = p.category_id
        WHERE 1=1
    """
    params = []

    if search_query:
        query += " AND (c.name LIKE %s OR c.shortcut LIKE %s OR c.description LIKE %s)"
        params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])

    if status_filter == "Active Only":
        query += " AND c.is_active = 1"
    elif status_filter == "Inactive Only":
        query += " AND c.is_active = 0"

    query += " GROUP BY c.id ORDER BY c.name ASC"
    categories = db.execute_query(query, params)

    if not categories:
        render_empty_state("No categories found matching the criteria.", "Try clearing filters or adding a new category.", "🏷️")
    else:
        df = pd.DataFrame(categories)
        df["Status"] = df["is_active"].apply(lambda x: "🟢 Active" if x == 1 else "🔴 Inactive")
        df_display = df[["id", "name", "shortcut", "description", "product_count", "Status", "created_at"]]
        df_display.columns = ["ID", "Category Name", "Shortcut", "Description", "Assigned Products", "Status", "Created At"]

        paginated_df = paginate_dataframe(df_display, page_size=50, key="cat_table")
        st.dataframe(paginated_df, use_container_width=True, hide_index=True)

        # ----------------------------------------------------------------------
        # 3. Category Actions (Edit / Deactivate / Delete)
        # ----------------------------------------------------------------------
        st.markdown("---")
        render_section_header("Manage Selected Category", "Update category attributes or manage lifecycle", "⚙️")
        cat_options = {f"{c['name']} [{c['shortcut']}] ({c['product_count']} Products)": c for c in categories}
        selected_cat_label = st.selectbox("Select Category to Modify", list(cat_options.keys()), key="cat_manage_sel")
        selected_cat = cat_options[selected_cat_label]

        col_edit, col_danger = st.columns([2, 1])

        with col_edit:
            with st.form("edit_category_form"):
                st.markdown(f"**Editing Category:** `{html.escape(selected_cat['name'])}` (Shortcut: `{html.escape(selected_cat.get('shortcut') or 'N/A')}`)")
                e_cn, e_cs = st.columns([2, 1])
                with e_cn:
                    new_name = st.text_input("Category Name *", value=selected_cat["name"])
                with e_cs:
                    new_shortcut = st.text_input(
                        "Category Shortcut *",
                        value=selected_cat.get("shortcut") or "",
                        help="2–5 uppercase alphanumeric characters (e.g., GAM, ELE)"
                    )

                new_desc = st.text_area("Description", value=selected_cat["description"] or "")
                new_active = st.checkbox("Active Status", value=bool(selected_cat["is_active"]))

                st.caption("ℹ️ Note: Changing a shortcut will only apply to future product codes. Existing product codes will remain unchanged to preserve order history.")

                update_btn = st.form_submit_button("Save Category Changes", type="primary", use_container_width=True)

                if update_btn:
                    if not new_name.strip():
                        st.error("Category name cannot be empty.")
                    else:
                        valid_short, short_err, clean_shortcut = db.validate_category_shortcut(
                            new_shortcut,
                            current_category_id=selected_cat["id"]
                        )
                        if not valid_short:
                            st.error(short_err)
                        else:
                            with st.spinner("Updating category..."):
                                dup = db.execute_one(
                                    "SELECT id FROM categories WHERE name = %s AND id != %s",
                                    (new_name.strip(), selected_cat["id"])
                                )
                                if dup:
                                    st.error("A category with this name already exists.")
                                else:
                                    db.execute_update(
                                        """
                                        UPDATE categories 
                                        SET name = %s, shortcut = %s, description = %s, is_active = %s 
                                        WHERE id = %s
                                        """,
                                        (new_name.strip(), clean_shortcut, new_desc.strip(), 1 if new_active else 0, selected_cat["id"])
                                    )
                                    st.toast(f"Category '{new_name}' (Shortcut: {clean_shortcut}) updated successfully!", icon="✅")
                                    st.rerun()

        with col_danger:
            st.markdown("**Data Integrity & Deletion**")
            prod_count = selected_cat["product_count"]
            if prod_count > 0:
                st.warning(
                    f"This category is linked to **{prod_count} product(s)**. "
                    "To protect relational foreign keys, it cannot be deleted. "
                    "Deactivate the category instead to hide it from new product forms."
                )
            else:
                st.info("This category has 0 linked products and can be safely deleted.")
                confirm_del = st.checkbox("I confirm I want to permanently delete this category", key="conf_del_cat")
                if st.button("Delete Category Permanently", type="primary", use_container_width=True, disabled=not confirm_del):
                    with st.spinner("Deleting category..."):
                        try:
                            with db.get_db_transaction() as (cursor, conn):
                                cursor.execute("DELETE FROM document_sequences WHERE seq_name = %s", (f"PROD_CAT_{selected_cat['id']}",))
                                cursor.execute("DELETE FROM categories WHERE id = %s", (selected_cat["id"],))
                            st.toast(f"Category '{selected_cat['name']}' deleted permanently.", icon="✅")
                            st.rerun()
                        except Exception as e:
                            logger.error(f"Cannot delete category: {e}", exc_info=True)
                            st.error("Cannot delete category. Ensure no linked products or foreign keys exist.")
