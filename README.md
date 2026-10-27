# 📦 Smart Inventory & Order Management System (SIOM)

A complete, enterprise-grade, full-stack **Smart Inventory & Order Management System** built with **Python**, **MySQL**, **Streamlit**, **Pandas**, **Plotly**, and **Excel/CSV Export Utilities**.

---

## 🌟 Key Features & Architecture

1. **🔐 Multi-Role Access Control & Security**
   - **Role Enforcement (`require_role`)**:
     - **Super Admin**: Complete unrestricted system access across all 10 ERP modules and user administration.
     - **Inventory Manager**: Direct authority over Products, Categories, Stock/Inventory adjustments, Suppliers, and Inbound Purchase Orders.
     - **Sales Manager**: Outbound Customer relationships, Sales Orders, Invoicing/Payments, and Carrier Dispatch Tracking.
   - **Login Rate Limiting**: Automatic 5-minute security lockout after 5 consecutive failed login attempts.
   - **Password Complexity Policy**: Minimum 10 characters requiring at least one letter and one number.
   - **HTML Sanitization**: All user-rendered strings are safely escaped using `html.escape`.
   - **Secure PBKDF2/bcrypt Hashing**: Salted cryptographic credentials storage.

2. **🎨 Polished Light Theme & Modern UI**
   - **Theme Engine (`.streamlit/config.toml` & `assets/style.css`)**:
     - `base="light"`, `primaryColor="#dc2626"`, `backgroundColor="#f8fafc"`, `textColor="#0f172a"`.
     - Consistent light backgrounds, dark typography, and light gray borders for all input fields, select boxes, and data tables.
     - Red-accented navigation tabs with active underline indicator and 14px high-contrast typography.
     - Widened table columns with text-wrapping and row height optimization.
     - Maximum 1400px layout width on wide screens.
     - Clean, non-disappearing feedback notifications using `st.toast` and `st.spinner` feedback indicators.

3. **⚡ High-Performance Caching & Pagination**
   - Read-only queries cached via `@st.cache_data` with automatic cache-invalidation on database mutations.
   - Built-in table pagination (50 items per page) for responsive performance across large catalogs and ledgers.

4. **🛒 Purchase Orders & Inbound Goods Receipt**
   - Multi-item PO builder with tax calculation.
   - **Transaction-safe goods receiving**: Increases warehouse inventory **only** upon physical receipt and logs audit entries in `stock_movements`.

5. **🛍️ Sales Orders & Fulfillment**
   - Real-time stock availability verification prior to confirmation.
   - **Idempotent stock deduction**: Confirmed sales orders deduct stock once only with transaction guards (`stock_deducted`).
   - **Order cancellation safety**: Cancelling a confirmed order restores inventory back to the warehouse with `RETURN_IN` audit logging.

6. **📜 Immutable Stock Movement Audit Trail**
   - **Mandatory Reason Enforcement**: Manual stock adjustments without a valid, non-empty business justification are strictly rejected.

7. **📈 Financial Reports & Analytical Exports**
   - Sales & profitability reports separating **Gross Revenue**, **COGS**, and **Gross Margin**.
   - One-click downloads for **Excel (.xlsx)** and **CSV**.

---

## 🏗️ Project Structure

```
siom/
├── .streamlit/
│   └── config.toml            # Streamlit light theme configuration
├── assets/
│   └── style.css              # Global custom CSS design tokens
├── tests/
│   ├── __init__.py
│   └── test_stock_logic.py    # Pytest automated test suite for stock logic
├── modules/
│   ├── __init__.py
│   ├── auth_ui.py             # Login, Rate Limiting, Role Profile
│   ├── dashboard_ui.py        # Executive KPI dashboard & Plotly charts
│   ├── categories_ui.py       # Product category management
│   ├── products_ui.py         # Product catalog management
│   ├── suppliers_ui.py        # Supplier CRM & procurement analytics
│   ├── customers_ui.py        # Customer CRM & balance ledger
│   ├── inventory_ui.py        # Stock on hand, reorder alerts, adjustments
│   ├── purchase_orders_ui.py  # Inbound purchase orders & receipt
│   ├── sales_orders_ui.py     # Outbound sales orders & fulfillment
│   ├── payments_ui.py         # Accounts receivable & payment records
│   ├── shipments_ui.py        # Carrier tracking & delivery milestones
│   └── ui_components.py       # Reusable UI components & role helpers
├── .env.example               # Template for environment variables
├── .env                       # Local database credentials (ignored by git)
├── .gitignore                  # Git ignore rules
├── requirements.txt           # Python dependencies
├── schema.sql                 # Complete MySQL DDL schema (13 tables)
├── database.py                # Connection pool, transactions, logging & auth
├── seed_data.py               # Database seeder with secure role accounts
├── app.py                     # Streamlit application entrypoint & dictionary router
└── reports.py                 # Analytics, Plotly figures & Excel/CSV exporters
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+
- MySQL Server 8.0+

### 2. Environment Setup
Create and configure your local `.env` file:
```bash
cp .env.example .env
```
Edit `.env` with your MySQL credentials:
```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=smart_inventory_db
APP_NAME=Smart Inventory & Order Management System
APP_SECRET_KEY=secure_random_key
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Initialize Database & Seed Demo Data
```bash
python seed_data.py
```

### 5. Run the Streamlit Application
```bash
streamlit run app.py
```

---

## 🧪 Running Automated Tests

Run the full pytest suite to verify core business logic:
```bash
pytest -v tests/
```

Test coverage includes:
- ✅ Purchase order receipt increases warehouse stock.
- ✅ Sales order confirmation deducts stock once only (idempotent).
- ✅ Cancelling a confirmed order restores deducted inventory.
- ✅ Manual stock adjustments without a reason are strictly rejected.
- ✅ Password complexity and strength verification.

---

## 👥 Role Permissions Matrix

| Module / Feature | Super Admin | Inventory Manager | Sales Manager |
| :--- | :---: | :---: | :---: |
| Executive Dashboard | ✅ | ✅ | ✅ |
| Product Catalog | ✅ | ✅ | ❌ |
| Category Management | ✅ | ✅ | ❌ |
| Inventory & Stock | ✅ | ✅ | ❌ |
| Supplier Directory | ✅ | ✅ | ❌ |
| Customer Directory | ✅ | ❌ | ✅ |
| Purchase Orders (Inbound) | ✅ | ✅ | ❌ |
| Sales Orders (Outbound) | ✅ | ❌ | ✅ |
| Payments & Invoicing | ✅ | ❌ | ✅ |
| Shipment Tracking | ✅ | ❌ | ✅ |
| Analytics & Reports | ✅ | ✅ | ✅ |
| Admin Profile & Password Change | ✅ | ✅ | ✅ |
