# Autopsy Walkthrough: Debugging a Caching Bug

This walkthrough demonstrates how `autopsy` enhances the familiar "printf debugging" workflow. We'll debug a subtle caching bug that requires multiple rounds of investigation—showcasing how autopsy's call stack inspection reveals information you didn't think to log.

## The Scenario

You're building a price calculator for an e-commerce system. To improve performance, you've added a memoization decorator to cache expensive calculations. The code is running, but some orders have incorrect totals—and one is *wildly* wrong.

## The Code

Here's our memoization decorator:

```python
_cache: dict = {}

def memoize(func):
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
```

We use this decorator on three functions:

```python
@memoize
def calculate_bulk_discount(quantity: int) -> float:
    """Returns discount percentage (0.0 to 0.20)"""
    ...

@memoize  
def calculate_loyalty_discount(years: int) -> float:
    """Returns discount percentage (0.0 to 0.15)"""
    ...

@memoize
def calculate_shipping(weight: int) -> float:
    """Returns shipping cost in dollars ($5 to $25)"""
    ...
```

## The Hidden Bug

Here's the twist: the code has a comprehensive unit test suite, and **all unit tests pass**:

```
$ uv run pytest tests/examples/test_price_calculator.py -v

TestBulkDiscount::test_no_discount_zero_items PASSED
TestBulkDiscount::test_no_discount_few_items PASSED
TestBulkDiscount::test_small_discount PASSED
...
TestLoyaltyDiscount::test_no_discount_new_customer PASSED
TestLoyaltyDiscount::test_small_discount_one_year PASSED
...
TestShipping::test_minimum_shipping PASSED
...

13 passed
```

Each function works correctly *in isolation*. The bug only manifests when multiple functions are called together with overlapping argument values.

## Running the Code

```
$ uv run python -m examples.price_calculator

============================================================
Price Calculator - Order Processing
============================================================

Results:
------------------------------------------------------------
✓ Order A: $227.50 (expected $227.50)
✓ Order B: $885.00 (expected $885.00)
✗ ERROR Order C: $140.00 (expected $125.00)
✗ ERROR Order D: $-2099.90 (expected $350.00)
✗ ERROR Order E: $144.05 (expected $138.00)

⚠ 3 order(s) have incorrect totals!
```

Three orders are wrong, with Order D showing an impossible **negative** total. Let's investigate.

---

## Round 1: Examining the Logs

Open the autopsy viewer and switch to the **History** tab to see logs in chronological order.

```bash
cd autopsy_html
cp ../examples/price_calculator_report.json dev-data.json
npm run dev
```

Search for Order D's processing. The `order_total` log shows:

```
order_total: subtotal=500, bulk_discount=0.2, loyalty_discount=5.0, shipping=0.1, final_total=-2099.9
```

Wait—`loyalty_discount=5.0`? That's supposed to be a percentage (0.0 to 0.15), not 5.0! And `shipping=0.1`? Shipping should be dollars ($5-$25), not 0.1.

The values are completely wrong types. A percentage ended up where a dollar amount should be, and vice versa.

**Hypothesis**: Maybe the discount/shipping functions have bugs?

Looking at the function logic... no, the logic is correct. A 5-year customer should get 0.15, not 5.0.

---

## Round 2: Tracking Cache Behavior

Since the functions are memoized, let's check if caching is involved. Click the **Dashboard** tab.

The **Value Counts** section shows:

| Value | Count |
|-------|-------|
| `"cache_miss"` | 10 |
| `"cache_hit"` | 5 |

With 5 orders and 3 calculations each, we'd expect 15 calls total. We're seeing 10 misses and 5 hits. Some cache hits are expected when the same value appears twice... but are all 5 hits legitimate?

---

## Round 3: Investigating the First Suspicious Hit

Click on `"cache_hit"` in the dashboard. The sidebar shows **5 matching call stacks**. Use the dropdown to browse through them.

Look for one where the cached value seems wrong. Select invocation **#18** (Order D's loyalty calculation). The stack trace shows:

```
#1 wrapper
   price_calculator.py:34
   report.log("cache_hit", args, _cache[cache_key])
   
   Local Variables:
   args: [5]
   cache_key: [5]
   _cache[cache_key]: 5.0

#2 calculate_order_total  
   price_calculator.py:107
   loyalty_discount = calculate_loyalty_discount(customer_years)
   
   Local Variables:
   item_price: 5.0
   quantity: 100
   customer_years: 5
   weight: 50
   subtotal: 500.0
   bulk_discount: 0.2
```

**The insight**: Frame #2 shows we're calling `calculate_loyalty_discount(customer_years)` where `customer_years=5`. But the cache returned `5.0`—which is a *dollar amount*, not a percentage!

The cache key `(5,)` was created by an earlier `calculate_shipping(5)` call (for Order C's 5-pound package). When `calculate_loyalty_discount(5)` ran, it found `(5,)` in the cache and returned the shipping cost as if it were a discount percentage.

---

## Round 4: Finding the Pattern

Now we understand the bug. But Order D had *two* wrong values. Let's find the other one.

Click the **←** button to go back to History and find the shipping cache hit. Or browse the other cache_hit stack traces in the dashboard.

Looking at invocation **#19** (Order D's shipping):

```
#1 wrapper
   cache_key: [50]
   _cache[cache_key]: 0.1

#2 calculate_order_total
   shipping = calculate_shipping(weight)
   
   Local Variables:
   weight: 50
   loyalty_discount: 5.0
```

The cache key `(50,)` was returning `0.1`—but that's a *percentage*, not dollars! This was cached by `calculate_bulk_discount(50)` from Order B.

---

## Round 5: Confirming Order C and E

Let's verify Order C's bug. Browse the cache hits and find one for Order C:

```
#2 calculate_order_total
   loyalty_discount = calculate_loyalty_discount(customer_years)
   
   Local Variables:
   customer_years: 10
   bulk_discount: 0.05
```

Here, `calculate_loyalty_discount(10)` got a cache hit for `(10,)`, which was stored by `calculate_bulk_discount(10)` moments earlier. The loyalty discount should be 0.15 (10+ year customer) but got 0.05 (the bulk discount for 10 items).

For Order E, similar analysis reveals two collisions:
- `loyalty(20)` returns `bulk(20)` = 0.05 instead of 0.15
- `shipping(10)` returns `bulk(10)` = 0.05 instead of $10.00

---

## The Root Cause

The memoization decorator uses only the function arguments as the cache key:

```python
cache_key = args  # (10,) for both bulk_discount(10) and loyalty_discount(10)
```

Different functions with the same arguments share cache entries, causing:
- Percentages to be used as dollar amounts
- Dollar amounts to be used as percentages  
- Completely wrong calculation results

## The Fix

Include the function name in the cache key:

```python
cache_key = (func.__name__, *args)  # ("calculate_bulk_discount", 10) vs ("calculate_loyalty_discount", 10)
```

---

## Key Takeaways

1. **Unit tests can miss integration bugs**: All 13 unit tests passed because each function works correctly in isolation. The bug only appears when functions interact—exactly the scenario autopsy's stack traces help debug.

2. **Multi-round investigation is natural**: Real debugging rarely finds the answer immediately. Autopsy preserves your investigation trail across rounds.

3. **Logs show symptoms, stack traces show causes**: The `order_total` log showed `loyalty_discount=5.0` was wrong, but the stack trace revealed *why*—it came from a shipping calculation's cached value.

4. **Type confusion bugs are subtle**: The cache returned valid-looking numbers. Only by seeing the call context (loyalty vs shipping) did the bug become clear.

5. **Dashboard aggregation guides investigation**: Seeing "5 cache hits" and being able to click through each one made it possible to find the problematic ones among legitimate hits.

6. **Local variables tell the full story**: Without modifying code, we could see `customer_years=5`, `weight=50`, and trace exactly which values collided.

---

## Running the Example

```bash
# Run the example
uv run python -m examples.price_calculator

# Or use the generate script
uv run python -m examples.generate json price_calculator

# View the report
cd autopsy_html
npm run dev
```

Open http://localhost:5173 to explore the report.

## Running the Tests

```bash
# Run unit tests (all pass)
uv run pytest examples/test_price_calculator.py::TestBulkDiscount -v
uv run pytest examples/test_price_calculator.py::TestLoyaltyDiscount -v
uv run pytest examples/test_price_calculator.py::TestShipping -v

# Run integration tests (all fail - this is the bug!)
uv run pytest examples/test_price_calculator.py::TestOrderCalculationIntegration -v

# Run all tests and generate an autopsy report
uv run pytest examples/test_price_calculator.py -v --generate-report

# Or use the generate script
uv run python -m examples.generate json price_calculator_tests
```

The test suite is instrumented with autopsy logging, so you can see exactly what happened during each test—including the failing integration tests.
