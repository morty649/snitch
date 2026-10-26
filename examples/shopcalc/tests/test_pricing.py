"""Looks thorough. Coverage is 100%. It is not thorough. (Intentionally weak for the Snitch demo.)"""
import pytest

from shopcalc.pricing import apply_coupon, bulk_discount, order_total, refund_amount


def test_bulk_discount():
    assert bulk_discount(1) == 0.0
    assert bulk_discount(25) == 0.10
    assert bulk_discount(100) == 0.20


def test_coupon():
    assert apply_coupon(100, "SAVE5") == 95
    assert apply_coupon(100, None) == 100
    assert apply_coupon(10, "SAVE5") == 10


def test_order_total():
    assert order_total(10.0, 2) == 20.0
    assert order_total(10.0, 20, "save5") == 175.0
    with pytest.raises(ValueError):
        order_total(10.0, 0)


def test_refund():
    assert refund_amount(100, 3) == 100
    assert refund_amount(100, 20) == 50
    assert refund_amount(100, 60) == 0.0
