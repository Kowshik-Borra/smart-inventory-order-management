-- ==============================================================================
-- SMART INVENTORY & ORDER MANAGEMENT SYSTEM (SIOM)
-- Complete Database Architecture Schema
-- ==============================================================================

CREATE DATABASE IF NOT EXISTS smart_inventory_db 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE smart_inventory_db;

-- ------------------------------------------------------------------------------
-- 1. Table: admins (User Authentication & Roles)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role ENUM('Super Admin', 'Inventory Manager', 'Sales Manager') NOT NULL DEFAULT 'Super Admin',
    status ENUM('Active', 'Inactive') NOT NULL DEFAULT 'Active',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_admin_username (username),
    INDEX idx_admin_email (email)
) ENGINE=InnoDB;

-- ------------------------------------------------------------------------------
-- 2. Table: categories (Product Grouping)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    shortcut VARCHAR(10) NOT NULL UNIQUE,
    description TEXT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_category_name (name),
    INDEX idx_category_shortcut (shortcut),
    INDEX idx_category_active (is_active)
) ENGINE=InnoDB;

-- ------------------------------------------------------------------------------
-- 3. Table: products (Item Catalog)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sku VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(150) NOT NULL,
    category_id INT NOT NULL,
    description TEXT NULL,
    cost_price DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    selling_price DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    reorder_level INT NOT NULL DEFAULT 10,
    unit VARCHAR(30) NOT NULL DEFAULT 'pcs',
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_products_category 
        FOREIGN KEY (category_id) REFERENCES categories(id) 
        ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX idx_product_sku (sku),
    INDEX idx_product_name (name),
    INDEX idx_product_category (category_id),
    INDEX idx_product_active (is_active)
) ENGINE=InnoDB;

-- ------------------------------------------------------------------------------
-- 4. Table: suppliers (Vendor Information)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS suppliers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL UNIQUE,
    contact_person VARCHAR(100) NULL,
    phone VARCHAR(30) NULL,
    email VARCHAR(100) NULL,
    address TEXT NULL,
    notes TEXT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_supplier_name (name),
    INDEX idx_supplier_active (is_active)
) ENGINE=InnoDB;

-- ------------------------------------------------------------------------------
-- 5. Table: customers (Buyer Information)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    contact_person VARCHAR(100) NULL,
    phone VARCHAR(30) NULL,
    email VARCHAR(100) NULL,
    address TEXT NULL,
    notes TEXT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_customer_name (name),
    INDEX idx_customer_email (email),
    INDEX idx_customer_active (is_active)
) ENGINE=InnoDB;

-- ------------------------------------------------------------------------------
-- 6. Table: inventory (Current Stock On Hand)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS inventory (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL UNIQUE,
    quantity_on_hand INT NOT NULL DEFAULT 0,
    reorder_point INT NOT NULL DEFAULT 10,
    last_updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_inventory_product 
        FOREIGN KEY (product_id) REFERENCES products(id) 
        ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX idx_inventory_product (product_id),
    INDEX idx_inventory_qty (quantity_on_hand)
) ENGINE=InnoDB;

-- ------------------------------------------------------------------------------
-- 7. Table: purchase_orders (Procurement Header)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS purchase_orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    po_number VARCHAR(50) NOT NULL UNIQUE,
    supplier_id INT NOT NULL,
    order_date DATE NOT NULL,
    expected_date DATE NULL,
    status ENUM('Draft', 'Ordered', 'Partially Received', 'Received', 'Cancelled') NOT NULL DEFAULT 'Draft',
    subtotal DECIMAL(14, 2) NOT NULL DEFAULT 0.00,
    tax_amount DECIMAL(14, 2) NOT NULL DEFAULT 0.00,
    total_amount DECIMAL(14, 2) NOT NULL DEFAULT 0.00,
    notes TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_po_supplier 
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id) 
        ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX idx_po_number (po_number),
    INDEX idx_po_supplier (supplier_id),
    INDEX idx_po_status (status),
    INDEX idx_po_date (order_date)
) ENGINE=InnoDB;

-- ------------------------------------------------------------------------------
-- 8. Table: purchase_order_items (Procurement Line Items)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS purchase_order_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    purchase_order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity_ordered INT NOT NULL,
    quantity_received INT NOT NULL DEFAULT 0,
    unit_cost DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    line_total DECIMAL(14, 2) NOT NULL DEFAULT 0.00,
    CONSTRAINT fk_poi_order 
        FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders(id) 
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_poi_product 
        FOREIGN KEY (product_id) REFERENCES products(id) 
        ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX idx_poi_order (purchase_order_id),
    INDEX idx_poi_product (product_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------------------------
-- 9. Table: sales_orders (Sales Order Header)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sales_orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_number VARCHAR(50) NOT NULL UNIQUE,
    customer_id INT NOT NULL,
    order_date DATE NOT NULL,
    status ENUM('Draft', 'Confirmed', 'Processing', 'Shipped', 'Delivered', 'Cancelled') NOT NULL DEFAULT 'Draft',
    subtotal DECIMAL(14, 2) NOT NULL DEFAULT 0.00,
    discount_amount DECIMAL(14, 2) NOT NULL DEFAULT 0.00,
    tax_amount DECIMAL(14, 2) NOT NULL DEFAULT 0.00,
    total_amount DECIMAL(14, 2) NOT NULL DEFAULT 0.00,
    notes TEXT NULL,
    stock_deducted TINYINT(1) NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_so_customer 
        FOREIGN KEY (customer_id) REFERENCES customers(id) 
        ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX idx_so_number (order_number),
    INDEX idx_so_customer (customer_id),
    INDEX idx_so_status (status),
    INDEX idx_so_date (order_date)
) ENGINE=InnoDB;

-- ------------------------------------------------------------------------------
-- 10. Table: sales_order_items (Sales Order Line Items)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sales_order_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sales_order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    line_total DECIMAL(14, 2) NOT NULL DEFAULT 0.00,
    CONSTRAINT fk_soi_order 
        FOREIGN KEY (sales_order_id) REFERENCES sales_orders(id) 
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_soi_product 
        FOREIGN KEY (product_id) REFERENCES products(id) 
        ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX idx_soi_order (sales_order_id),
    INDEX idx_soi_product (product_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------------------------
-- 11. Table: payments (Payment Tracking)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS payments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    payment_number VARCHAR(50) NOT NULL UNIQUE,
    sales_order_id INT NOT NULL,
    payment_date DATE NOT NULL,
    amount DECIMAL(14, 2) NOT NULL,
    payment_method ENUM('Cash', 'Bank Transfer', 'Credit Card', 'Debit Card', 'UPI', 'Cheque') NOT NULL DEFAULT 'Bank Transfer',
    reference_number VARCHAR(100) NULL,
    status ENUM('Completed', 'Pending', 'Failed', 'Refunded') NOT NULL DEFAULT 'Completed',
    notes TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_payments_order 
        FOREIGN KEY (sales_order_id) REFERENCES sales_orders(id) 
        ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX idx_payment_order (sales_order_id),
    INDEX idx_payment_date (payment_date),
    INDEX idx_payment_status (status)
) ENGINE=InnoDB;

-- ------------------------------------------------------------------------------
-- 12. Table: shipments (Fulfillment & Carrier Tracking)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS shipments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    shipment_number VARCHAR(50) NOT NULL UNIQUE,
    sales_order_id INT NOT NULL,
    carrier VARCHAR(100) NOT NULL,
    tracking_number VARCHAR(100) NOT NULL,
    dispatch_date DATE NULL,
    estimated_delivery DATE NULL,
    actual_delivery DATE NULL,
    status ENUM('Pending', 'Packed', 'Dispatched', 'In Transit', 'Delivered', 'Failed', 'Returned') NOT NULL DEFAULT 'Pending',
    notes TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_shipments_order 
        FOREIGN KEY (sales_order_id) REFERENCES sales_orders(id) 
        ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX idx_shipment_order (sales_order_id),
    INDEX idx_shipment_tracking (tracking_number),
    INDEX idx_shipment_status (status)
) ENGINE=InnoDB;

-- ------------------------------------------------------------------------------
-- ------------------------------------------------------------------------------
-- 13. Table: stock_movements (Audit Trail for All Inventory Adjustments)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_movements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    movement_type ENUM('PO_RECEIPT', 'SO_FULFILLMENT', 'ADJUSTMENT_ADD', 'ADJUSTMENT_SUB', 'RETURN_IN', 'RETURN_OUT', 'INITIAL_STOCK') NOT NULL,
    quantity INT NOT NULL, -- positive value; direction determined by movement_type
    balance_after INT NOT NULL,
    reference_type ENUM('PURCHASE_ORDER', 'SALES_ORDER', 'MANUAL_ADJUSTMENT', 'INITIAL_STOCK') NOT NULL,
    reference_id INT NULL,
    notes TEXT NULL,
    created_by_admin_id INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_sm_product 
        FOREIGN KEY (product_id) REFERENCES products(id) 
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_sm_admin 
        FOREIGN KEY (created_by_admin_id) REFERENCES admins(id) 
        ON UPDATE CASCADE ON DELETE SET NULL,
    INDEX idx_sm_product (product_id),
    INDEX idx_sm_type (movement_type),
    INDEX idx_sm_created (created_at),
    INDEX idx_sm_ref (reference_type, reference_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------------------------
-- 14. Table: document_sequences (Atomic Race-Safe Sequence Number Generator)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS document_sequences (
    seq_name VARCHAR(50) NOT NULL PRIMARY KEY,
    next_val INT NOT NULL DEFAULT 0,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

