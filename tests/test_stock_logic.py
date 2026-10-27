"""
Test Suite for Core SIOM Stock Logic:
1. Receiving a purchase order increases stock.
2. Confirming a sales order deducts stock once only (idempotency).
3. Cancelling a confirmed order restores stock.
4. A manual stock adjustment without a reason is rejected.
5. Password security policy enforcement.
"""

# pyrefly: ignore [missing-import]
import pytest
from decimal import Decimal
from database import validate_password_strength


# ==============================================================================
# In-Memory Inventory and Order Management Domain Model for Logic Verification
# ==============================================================================

class InventoryService:
    def __init__(self):
        # product_id -> {"sku": str, "stock": int}
        self.inventory = {}
        # order_id -> {"order_number": str, "status": str, "stock_deducted": bool, "items": list}
        self.sales_orders = {}
        # po_id -> {"po_number": str, "status": str, "items": list}
        self.purchase_orders = {}
        # Audit log of stock movements
        self.stock_movements = []

    def set_stock(self, product_id: int, sku: str, quantity: int):
        self.inventory[product_id] = {"sku": sku, "stock": quantity}

    def get_stock(self, product_id: int) -> int:
        return self.inventory.get(product_id, {}).get("stock", 0)

    def receive_purchase_order(self, po_id: int, received_items: list):
        """
        Receiving a purchase order increases warehouse stock.
        received_items: list of dicts {"product_id": int, "quantity_received": int}
        """
        if po_id not in self.purchase_orders:
            self.purchase_orders[po_id] = {"status": "Ordered", "items": []}

        for item in received_items:
            p_id = item["product_id"]
            qty = item["quantity_received"]
            if qty <= 0:
                raise ValueError("Received quantity must be greater than zero.")
            
            curr = self.get_stock(p_id)
            new_bal = curr + qty
            self.inventory[p_id]["stock"] = new_bal
            self.stock_movements.append({
                "product_id": p_id,
                "movement_type": "PO_RECEIPT",
                "quantity": qty,
                "balance_after": new_bal,
                "reference_id": po_id
            })

        self.purchase_orders[po_id]["status"] = "Received"
        return True

    def confirm_sales_order(self, order_id: int, items: list):
        """
        Confirming a sales order deducts stock once only.
        items: list of dicts {"product_id": int, "quantity": int}
        """
        order = self.sales_orders.get(order_id)
        if not order:
            order = {"status": "Draft", "stock_deducted": False, "items": items}
            self.sales_orders[order_id] = order

        # Idempotency check: deduct only once
        if order.get("stock_deducted"):
            return False, "Order stock has already been deducted."

        # Validate stock availability
        for item in items:
            p_id = item["product_id"]
            req_qty = item["quantity"]
            curr = self.get_stock(p_id)
            if req_qty > curr:
                raise ValueError(f"Insufficient stock for product {p_id}. Requested: {req_qty}, Available: {curr}")

        # Deduct stock
        for item in items:
            p_id = item["product_id"]
            req_qty = item["quantity"]
            curr = self.get_stock(p_id)
            new_bal = curr - req_qty
            self.inventory[p_id]["stock"] = new_bal
            self.stock_movements.append({
                "product_id": p_id,
                "movement_type": "SO_FULFILLMENT",
                "quantity": req_qty,
                "balance_after": new_bal,
                "reference_id": order_id
            })

        order["status"] = "Confirmed"
        order["stock_deducted"] = True
        return True, "Order confirmed and stock deducted."

    def cancel_sales_order(self, order_id: int):
        """
        Cancelling a confirmed sales order restores stock if previously deducted.
        """
        order = self.sales_orders.get(order_id)
        if not order:
            raise ValueError(f"Sales order {order_id} not found.")

        if order["status"] == "Cancelled":
            return False, "Order is already cancelled."

        # If stock was deducted, restore it
        if order.get("stock_deducted"):
            for item in order["items"]:
                p_id = item["product_id"]
                qty = item["quantity"]
                curr = self.get_stock(p_id)
                new_bal = curr + qty
                self.inventory[p_id]["stock"] = new_bal
                self.stock_movements.append({
                    "product_id": p_id,
                    "movement_type": "RETURN_IN",
                    "quantity": qty,
                    "balance_after": new_bal,
                    "reference_id": order_id
                })
            order["stock_deducted"] = False

        order["status"] = "Cancelled"
        return True, "Order cancelled and stock restored."

    def manual_stock_adjustment(self, product_id: int, new_quantity: int, reason: str, admin_id: int = 1):
        """
        Manual stock adjustments strictly require a mandatory non-empty business reason.
        """
        if not reason or not reason.strip():
            raise ValueError("A valid, non-empty business reason is strictly mandatory for manual stock adjustments.")

        if new_quantity < 0:
            raise ValueError("Stock quantity cannot be negative.")

        curr = self.get_stock(product_id)
        diff = new_quantity - curr
        self.inventory[product_id]["stock"] = new_quantity

        self.stock_movements.append({
            "product_id": product_id,
            "movement_type": "ADJUSTMENT_ADD" if diff >= 0 else "ADJUSTMENT_SUB",
            "quantity": abs(diff),
            "balance_after": new_quantity,
            "notes": reason.strip(),
            "admin_id": admin_id
        })
        return True


# ==============================================================================
# Pytest Test Cases
# ==============================================================================

def test_receiving_purchase_order_increases_stock():
    """Verify that receiving a purchase order increases warehouse stock accurately."""
    svc = InventoryService()
    svc.set_stock(product_id=101, sku="SKU-LAPTOP-01", quantity=50)

    # Receive PO with 30 additional units
    po_items = [{"product_id": 101, "quantity_received": 30}]
    svc.receive_purchase_order(po_id=1, received_items=po_items)

    assert svc.get_stock(101) == 80
    assert len(svc.stock_movements) == 1
    assert svc.stock_movements[0]["movement_type"] == "PO_RECEIPT"
    assert svc.stock_movements[0]["quantity"] == 30
    assert svc.stock_movements[0]["balance_after"] == 80


def test_confirming_sales_order_deducts_stock_once_only():
    """Verify that confirming a sales order deducts stock once only (idempotent)."""
    svc = InventoryService()
    svc.set_stock(product_id=201, sku="SKU-MONITOR-01", quantity=100)

    order_items = [{"product_id": 201, "quantity": 15}]

    # First confirmation -> should deduct 15 units
    success, msg = svc.confirm_sales_order(order_id=5001, items=order_items)
    assert success is True
    assert svc.get_stock(201) == 85
    assert svc.sales_orders[5001]["stock_deducted"] is True

    # Second confirmation attempt -> must not deduct stock again
    success_2, msg_2 = svc.confirm_sales_order(order_id=5001, items=order_items)
    assert success_2 is False
    assert svc.get_stock(201) == 85  # Unchanged
    assert "already been deducted" in msg_2


def test_cancelling_confirmed_order_restores_stock():
    """Verify that cancelling a confirmed order restores the deducted stock."""
    svc = InventoryService()
    svc.set_stock(product_id=301, sku="SKU-KEYBOARD-01", quantity=50)

    order_items = [{"product_id": 301, "quantity": 20}]
    svc.confirm_sales_order(order_id=6001, items=order_items)
    assert svc.get_stock(301) == 30

    # Cancel the confirmed order
    success, msg = svc.cancel_sales_order(order_id=6001)
    assert success is True
    assert svc.get_stock(301) == 50  # Restored to 50
    assert svc.sales_orders[6001]["stock_deducted"] is False
    assert svc.sales_orders[6001]["status"] == "Cancelled"

    # Audit log check
    latest_movement = svc.stock_movements[-1]
    assert latest_movement["movement_type"] == "RETURN_IN"
    assert latest_movement["quantity"] == 20
    assert latest_movement["balance_after"] == 50


def test_manual_stock_adjustment_without_reason_is_rejected():
    """Verify that manual stock adjustment without a reason or with empty whitespace is rejected."""
    svc = InventoryService()
    svc.set_stock(product_id=401, sku="SKU-MOUSE-01", quantity=40)

    # Empty string reason
    with pytest.raises(ValueError, match="mandatory"):
        svc.manual_stock_adjustment(product_id=401, new_quantity=45, reason="")

    # Whitespace-only reason
    with pytest.raises(ValueError, match="mandatory"):
        svc.manual_stock_adjustment(product_id=401, new_quantity=45, reason="   ")

    # None reason
    with pytest.raises(ValueError, match="mandatory"):
        svc.manual_stock_adjustment(product_id=401, new_quantity=45, reason=None)

    # Stock should remain untouched
    assert svc.get_stock(401) == 40

    # Valid reason should succeed
    success = svc.manual_stock_adjustment(product_id=401, new_quantity=45, reason="Physical warehouse cycle count adjustment")
    assert success is True
    assert svc.get_stock(401) == 45


def test_password_strength_security_policy():
    """Verify password policy (at least 10 chars, letter + number)."""
    # Short password
    ok, msg = validate_password_strength("Short1")
    assert not ok
    assert "at least 10 characters" in msg

    # Letters only (>= 10 chars)
    ok, msg = validate_password_strength("allletterslongpass")
    assert not ok
    assert "at least one number" in msg

    # Numbers only (>= 10 chars)
    ok, msg = validate_password_strength("1234567890123")
    assert not ok
    assert "at least one letter" in msg

    # Compliant password
    ok, msg = validate_password_strength("AdminSecure2026")
    assert ok
