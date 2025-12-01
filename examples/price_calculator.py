"""Example: Price Calculator with a Caching Bug

This example demonstrates debugging a subtle caching bug using autopsy.
A memoization decorator has a bug where the cache key doesn't include
the function name, causing different functions to share cache entries.

This example is designed to require multiple rounds of investigation:
1. First, the user sees wrong totals and suspects discount logic
2. Then, they track cache behavior and see suspicious patterns
3. Finally, stack trace inspection reveals the root cause
"""

from autopsy import report
from autopsy.report import generate_json


# Simple memoization cache
_cache: dict = {}


def memoize(func):
    """Memoize decorator that caches function results.

    Bug: The cache key only uses the arguments, not the function name.
    This causes cache collisions when different functions are called
    with the same arguments!
    """

    def wrapper(*args):
        cache_key = args  # Bug: should be (func.__name__, *args)

        if cache_key in _cache:
            report.count("cache_hit")
            report.log("cache_hit", args, _cache[cache_key])
            return _cache[cache_key]

        report.count("cache_miss")
        result = func(*args)
        _cache[cache_key] = result
        report.log("cache_store", args, result)
        return result

    return wrapper


@memoize
def calculate_bulk_discount(quantity: int) -> float:
    """Calculate discount percentage based on order quantity.

    - 100+ items: 20% off
    - 50+ items: 10% off
    - 10+ items: 5% off
    - Otherwise: no discount
    """
    if quantity >= 100:
        return 0.20
    elif quantity >= 50:
        return 0.10
    elif quantity >= 10:
        return 0.05
    return 0.0


@memoize
def calculate_loyalty_discount(years: int) -> float:
    """Calculate discount percentage based on customer loyalty.

    - 5+ years: 15% off
    - 2+ years: 8% off
    - 1+ year: 3% off
    - Otherwise: no discount
    """
    if years >= 5:
        return 0.15
    elif years >= 2:
        return 0.08
    elif years >= 1:
        return 0.03
    return 0.0


@memoize
def calculate_shipping(weight: int) -> float:
    """Calculate shipping cost based on weight in pounds.

    - 50+ lbs: $25 flat rate
    - 20+ lbs: $15 flat rate
    - 10+ lbs: $10 flat rate
    - Otherwise: $5 flat rate
    """
    if weight >= 50:
        return 25.0
    elif weight >= 20:
        return 15.0
    elif weight >= 10:
        return 10.0
    return 5.0


def calculate_order_total(
    item_price: float, quantity: int, customer_years: int, weight: int
) -> float:
    """Calculate final order total with discounts and shipping."""
    subtotal = item_price * quantity

    bulk_discount = calculate_bulk_discount(quantity)
    loyalty_discount = calculate_loyalty_discount(customer_years)
    shipping = calculate_shipping(weight)

    total_discount = bulk_discount + loyalty_discount
    discounted_price = subtotal * (1 - total_discount)
    final_total = discounted_price + shipping

    report.log(
        "order_total",
        subtotal,
        bulk_discount,
        loyalty_discount,
        shipping,
        final_total,
    )
    return final_total


def process_orders():
    """Process a batch of customer orders."""
    # Orders: (item_price, quantity, customer_years, weight_lbs)
    orders = [
        # Order A: 25 items, 3yr customer, 15lbs
        # Expects: bulk=0%, loyalty=8%, shipping=$10
        (10.00, 25, 3, 15),
        # Order B: 50 items, 1yr customer, 30lbs
        # Expects: bulk=10%, loyalty=3%, shipping=$15
        (20.00, 50, 1, 30),
        # Order C: 10 items, 10yr customer, 5lbs
        # BUG HERE: loyalty(10) collides with bulk(10)!
        # Expects: bulk=5%, loyalty=15%, shipping=$5
        # Gets: bulk=5%, loyalty=5% (wrong!), shipping=$5
        (15.00, 10, 10, 5),
        # Order D: 100 items, 5yr customer, 50lbs
        # BUG HERE: loyalty(5) collides with shipping(5), shipping(50) collides with bulk(50)!
        # Expects: bulk=20%, loyalty=15%, shipping=$25
        # Gets: bulk=20%, loyalty=$5.00 (wrong!), shipping=10% (wrong!) -> NEGATIVE TOTAL!
        (5.00, 100, 5, 50),
        # Order E: 20 items, 20yr customer, 10lbs
        # BUG HERE: loyalty(20) collides with bulk(20), shipping(10) collides with bulk(10)!
        # Expects: bulk=5%, loyalty=15%, shipping=$10
        # Gets: bulk=5%, loyalty=5% (wrong!), shipping=$0.05 (wrong!)
        (8.00, 20, 20, 10),
    ]

    report.timeline("Starting order processing")

    results = []
    for i, (item_price, quantity, customer_years, weight) in enumerate(orders):
        order_name = f"Order {chr(65 + i)}"
        report.log(
            "processing_order", order_name, item_price, quantity, customer_years, weight
        )

        total = calculate_order_total(item_price, quantity, customer_years, weight)

        # Calculate expected total for verification
        exp_bulk = (
            0.20
            if quantity >= 100
            else 0.10
            if quantity >= 50
            else 0.05
            if quantity >= 10
            else 0.0
        )
        exp_loyalty = (
            0.15
            if customer_years >= 5
            else 0.08
            if customer_years >= 2
            else 0.03
            if customer_years >= 1
            else 0.0
        )
        exp_shipping = (
            25.0
            if weight >= 50
            else 15.0
            if weight >= 20
            else 10.0
            if weight >= 10
            else 5.0
        )
        expected = (item_price * quantity) * (1 - exp_bulk - exp_loyalty) + exp_shipping

        is_correct = abs(total - expected) < 0.01
        results.append(
            {
                "order": order_name,
                "actual": total,
                "expected": expected,
                "correct": is_correct,
            }
        )

        if not is_correct:
            report.log("order_error", order_name, total, expected)

    report.timeline("Order processing complete")
    return results


def run_example():
    """Run the price calculator example (called by generate.py)."""
    # Clear the cache to ensure fresh state
    _cache.clear()
    process_orders()


def main():
    """Run the price calculator example with output."""
    report.init()

    print("=" * 60)
    print("Price Calculator - Order Processing")
    print("=" * 60)

    # Clear cache for fresh run
    _cache.clear()
    results = process_orders()

    print("\nResults:")
    print("-" * 60)
    for r in results:
        status = "✓" if r["correct"] else "✗ ERROR"
        print(
            f"{status} {r['order']}: ${r['actual']:.2f} (expected ${r['expected']:.2f})"
        )

    errors = [r for r in results if not r["correct"]]
    if errors:
        print(f"\n⚠ {len(errors)} order(s) have incorrect totals!")

    # Save the autopsy report for analysis
    generate_json(output_path="examples/price_calculator_report.json")
    print("\n→ Autopsy report saved to examples/price_calculator_report.json")


if __name__ == "__main__":
    main()
