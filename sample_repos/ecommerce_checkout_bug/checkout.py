"""
E-Commerce Order & Checkout Service
Contains intentional bugs for the AI Software Engineering Agent to diagnose, fix, and test.
"""

from typing import List, Dict, Optional


class Item:
    def __init__(self, sku: str, name: str, price: float, quantity: int, discount_pct: float = 0.0):
        self.sku = sku
        self.name = name
        self.price = price
        self.quantity = quantity
        self.discount_pct = discount_pct


class CheckoutProcessor:
    def __init__(self, tax_rate: float = 0.08):
        self.tax_rate = tax_rate

    def calculate_item_subtotal(self, item: Item) -> float:
        """Calculate subtotal for a single line item after percentage discount."""
        if item.price < 0 or item.quantity < 0:
            raise ValueError("Price and quantity must be non-negative")
        # BUG 1: Discount percentage (e.g. 20 for 20%) is subtracted directly or multiplied wrong
        # Instead of price * quantity * (1 - discount_pct / 100.0), it divides by discount_pct when > 0
        # or subtracts raw discount_pct!
        gross = item.price * item.quantity
        if item.discount_pct > 0:
            discount_amount = gross * (item.discount_pct / 10.0)  # Bug: divided by 10 instead of 100!
            return round(gross - discount_amount, 2)
        return round(gross, 2)

    def calculate_average_item_price(self, items: List[Item]) -> float:
        """Calculate weighted average unit price across all items in the cart."""
        total_units = sum(item.quantity for item in items)
        total_cost = sum(self.calculate_item_subtotal(item) for item in items)
        # BUG 2: ZeroDivisionError when cart is empty or total_units == 0
        return round(total_cost / total_units, 2)

    def apply_loyalty_coupon(self, subtotal: float, coupon_code: Optional[str]) -> float:
        """Apply flat coupon discount without letting total drop below 0.0."""
        coupons: Dict[str, float] = {
            "SAVE10": 10.0,
            "SAVE25": 25.0,
            "VIP50": 50.0,
        }
        if not coupon_code:
            return subtotal
        code = coupon_code.strip().upper()
        if code not in coupons:
            raise ValueError(f"Invalid coupon code: {coupon_code}")
        # BUG 3: Does not clamp to 0.0 when coupon exceeds subtotal (returns negative total)
        return round(subtotal - coupons[code], 2)

    def process_checkout(self, items: List[Item], coupon_code: Optional[str] = None) -> Dict[str, float]:
        """Compute full checkout summary including subtotal, tax, and final total."""
        subtotal = round(sum(self.calculate_item_subtotal(i) for i in items), 2)
        discounted_subtotal = self.apply_loyalty_coupon(subtotal, coupon_code)
        tax = round(discounted_subtotal * self.tax_rate, 2)
        total = round(discounted_subtotal + tax, 2)
        avg_unit_price = self.calculate_average_item_price(items)
        return {
            "subtotal": subtotal,
            "discounted_subtotal": discounted_subtotal,
            "tax": tax,
            "total": total,
            "average_unit_price": avg_unit_price,
        }

