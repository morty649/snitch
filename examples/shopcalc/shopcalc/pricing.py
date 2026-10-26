"""Tiny e-commerce pricing module. Demo target for Snitch.

Its test suite is green and touches every function, yet it misses many realistic bugs.
"""


def bulk_discount(quantity: int) -> float:
    """10% off for 10+ items, 20% off for 50+ items."""
    if quantity >= 50:
        return 0.20
    if quantity >= 10:
        return 0.10
    return 0.0


def apply_coupon(total: float, code: str | None) -> float:
    """SAVE5 takes 5 off orders of at least 20. Unknown or missing codes do nothing."""
    if not code:
        return total
    if code.upper() == "SAVE5" and total >= 20:
        return total - 5
    return total


def order_total(unit_price: float, quantity: int, code: str | None = None) -> float:
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    subtotal = unit_price * quantity
    subtotal = subtotal * (1 - bulk_discount(quantity))
    subtotal = apply_coupon(subtotal, code)
    return round(max(subtotal, 0.0), 2)


def refund_amount(paid: float, days_since_purchase: int) -> float:
    """Full refund within 14 days, half refund up to 30 days, nothing after."""
    if days_since_purchase <= 14:
        return paid
    if days_since_purchase <= 30:
        return round(paid / 2, 2)
    return 0.0
