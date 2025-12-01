"""Tests for the price calculator example.

This test suite is intentionally "cooked" to demonstrate a subtle testing pitfall:
- Unit tests for individual functions pass because they test in isolation
- Integration tests fail because cache collisions occur when multiple functions
  are called with the same arguments

The overlapping test values (0, etc.) happen to return the same result across
functions, so unit tests don't catch the cache key collision bug. Only when
different functions are called with values that produce DIFFERENT outputs
does the bug manifest.

Run with: uv run pytest examples/test_price_calculator.py -v
Generate report: uv run pytest examples/test_price_calculator.py -v --generate-report
"""

import pytest

from autopsy import report
from examples import price_calculator


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the memoization cache before each test."""
    price_calculator._cache.clear()
    yield
    price_calculator._cache.clear()


# =============================================================================
# Unit Tests - These all pass because they test functions in isolation
# =============================================================================


class TestBulkDiscount:
    """Unit tests for calculate_bulk_discount.

    These tests pass individually. Note that we test with values 0, 25, 50, 100
    which don't overlap with loyalty_discount's test values in a way that would
    expose the bug.
    """

    def test_no_discount_zero_items(self):
        # 0 items -> 0% discount
        # Note: loyalty_discount(0) also returns 0.0, so cache collision is harmless
        result = price_calculator.calculate_bulk_discount(0)
        report.log("bulk_discount_result", 0, result)
        assert result == 0.0

    def test_no_discount_few_items(self):
        result = price_calculator.calculate_bulk_discount(5)
        report.log("bulk_discount_result", 5, result)
        assert result == 0.0

    def test_small_discount(self):
        # 10+ items -> 5% discount
        result = price_calculator.calculate_bulk_discount(25)
        report.log("bulk_discount_result", 25, result)
        assert result == 0.05

    def test_medium_discount(self):
        # 50+ items -> 10% discount
        result = price_calculator.calculate_bulk_discount(50)
        report.log("bulk_discount_result", 50, result)
        assert result == 0.10

    def test_large_discount(self):
        # 100+ items -> 20% discount
        result = price_calculator.calculate_bulk_discount(100)
        report.log("bulk_discount_result", 100, result)
        assert result == 0.20


class TestLoyaltyDiscount:
    """Unit tests for calculate_loyalty_discount.

    These tests pass individually. We carefully avoid testing with values
    that would collide with bulk_discount in a way that exposes the bug.
    """

    def test_no_discount_new_customer(self):
        # 0 years -> 0% discount
        # Note: bulk_discount(0) also returns 0.0, so cache collision is harmless
        result = price_calculator.calculate_loyalty_discount(0)
        report.log("loyalty_discount_result", 0, result)
        assert result == 0.0

    def test_small_discount_one_year(self):
        # 1 year -> 3% discount
        result = price_calculator.calculate_loyalty_discount(1)
        report.log("loyalty_discount_result", 1, result)
        assert result == 0.03

    def test_medium_discount_two_years(self):
        # 2+ years -> 8% discount
        result2 = price_calculator.calculate_loyalty_discount(2)
        result4 = price_calculator.calculate_loyalty_discount(4)
        report.log("loyalty_discount_result", 2, result2)
        report.log("loyalty_discount_result", 4, result4)
        assert result2 == 0.08
        assert result4 == 0.08

    def test_large_discount_five_years(self):
        # 5+ years -> 15% discount
        result5 = price_calculator.calculate_loyalty_discount(5)
        result7 = price_calculator.calculate_loyalty_discount(7)
        report.log("loyalty_discount_result", 5, result5)
        report.log("loyalty_discount_result", 7, result7)
        assert result5 == 0.15
        assert result7 == 0.15


class TestShipping:
    """Unit tests for calculate_shipping.

    These tests pass individually. We test with values that don't collide
    with discount function test values.
    """

    def test_minimum_shipping(self):
        # < 10 lbs -> $5
        result0 = price_calculator.calculate_shipping(0)
        result9 = price_calculator.calculate_shipping(9)
        report.log("shipping_result", 0, result0)
        report.log("shipping_result", 9, result9)
        assert result0 == 5.0
        assert result9 == 5.0

    def test_small_package_shipping(self):
        # 10+ lbs -> $10
        result = price_calculator.calculate_shipping(15)
        report.log("shipping_result", 15, result)
        assert result == 10.0

    def test_medium_package_shipping(self):
        # 20+ lbs -> $15
        result = price_calculator.calculate_shipping(30)
        report.log("shipping_result", 30, result)
        assert result == 15.0

    def test_large_package_shipping(self):
        # 50+ lbs -> $25
        result = price_calculator.calculate_shipping(75)
        report.log("shipping_result", 75, result)
        assert result == 25.0


# =============================================================================
# Integration Tests - These FAIL because of cache collisions
# =============================================================================


class TestOrderCalculationIntegration:
    """Integration tests that exercise the full order calculation.

    These tests FAIL because the memoization cache key doesn't include the
    function name, causing different functions to share cache entries when
    called with the same arguments.
    """

    def test_order_with_matching_quantity_and_years(self):
        """Test where quantity equals customer_years, causing cache collision.

        quantity=10, customer_years=10
        - calculate_bulk_discount(10) -> 0.05 (stored in cache as (10,))
        - calculate_loyalty_discount(10) -> cache hit! returns 0.05 (WRONG, should be 0.15)
        """
        # item_price=15, quantity=10, customer_years=10, weight=5
        report.log("integration_test", "quantity_equals_years", 15.0, 10, 10, 5)
        total = price_calculator.calculate_order_total(15.0, 10, 10, 5)

        # Expected calculation:
        # subtotal = 15 * 10 = 150
        # bulk_discount = 0.05 (10 items)
        # loyalty_discount = 0.15 (10 years) <- BUG: gets 0.05 from cache!
        # shipping = 5.0 (5 lbs)
        # total = 150 * (1 - 0.05 - 0.15) + 5 = 150 * 0.80 + 5 = 125.0
        expected = 125.0

        report.log("integration_result", total, expected, total == expected)
        assert total == expected, f"Expected {expected}, got {total}"

    def test_order_with_years_matching_shipping_weight(self):
        """Test where customer_years equals weight, causing type confusion.

        customer_years=5, weight=5
        - calculate_shipping(5) for a previous order stores (5,) -> 5.0
        - calculate_loyalty_discount(5) -> cache hit! returns 5.0 (WRONG, should be 0.15)

        This causes a dollar amount to be used as a percentage!
        """
        # First, simulate a previous order that cached shipping(5)
        cached_shipping = price_calculator.calculate_shipping(5)
        report.log("cached_value", "shipping(5)", cached_shipping)

        # Now calculate an order where loyalty_discount(5) will collide
        # item_price=10, quantity=20, customer_years=5, weight=30
        report.log("integration_test", "years_equals_weight", 10.0, 20, 5, 30)
        total = price_calculator.calculate_order_total(10.0, 20, 5, 30)

        # Expected calculation:
        # subtotal = 10 * 20 = 200
        # bulk_discount = 0.05 (20 items)
        # loyalty_discount = 0.15 (5 years) <- BUG: gets 5.0 from shipping cache!
        # shipping = 15.0 (30 lbs)
        # total = 200 * (1 - 0.05 - 0.15) + 15 = 200 * 0.80 + 15 = 175.0
        expected = 175.0

        report.log("integration_result", total, expected, total == expected)
        assert total == expected, f"Expected {expected}, got {total}"

    def test_order_with_quantity_matching_shipping_weight(self):
        """Test where quantity equals weight, causing type confusion.

        quantity=50, weight=50
        - calculate_bulk_discount(50) stores (50,) -> 0.10
        - calculate_shipping(50) -> cache hit! returns 0.10 (WRONG, should be 25.0)

        This causes a percentage to be used as a dollar amount!
        """
        # item_price=5, quantity=50, customer_years=1, weight=50
        report.log("integration_test", "quantity_equals_weight", 5.0, 50, 1, 50)
        total = price_calculator.calculate_order_total(5.0, 50, 1, 50)

        # Expected calculation:
        # subtotal = 5 * 50 = 250
        # bulk_discount = 0.10 (50 items)
        # loyalty_discount = 0.03 (1 year)
        # shipping = 25.0 (50 lbs) <- BUG: gets 0.10 from bulk cache!
        # total = 250 * (1 - 0.10 - 0.03) + 25 = 250 * 0.87 + 25 = 242.5
        expected = 242.5

        report.log("integration_result", total, expected, total == expected)
        assert total == expected, f"Expected {expected}, got {total}"
