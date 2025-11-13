"""Test fibonacci computation with call stack tracking."""

import pickle
from autopsy import report, call_stack


def fibonacci_iterative(n):
    """Compute fibonacci iteratively."""
    report.log(n, "fibonacci_iterative start")
    if n <= 1:
        return n

    a, b = 0, 1
    for i in range(2, n + 1):
        report.log(i, a, b, f"fibonacci_iterative step {i}")
        a, b = b, a + b

    report.log(b, "fibonacci_iterative result")
    return b


def fibonacci_recursive(n):
    """Compute fibonacci recursively."""
    cs = call_stack()
    caller_info = cs.caller

    report.log(n, caller_info, f"fibonacci_recursive({n})")

    if n <= 1:
        return n

    return fibonacci_recursive(n - 1) + fibonacci_recursive(n - 2)


def test_fibonacci_iterative():
    """Test iterative fibonacci with logging."""
    report.init()

    result = fibonacci_iterative(7)
    assert result == 13, f"Expected 13, got {result}"

    # Verify we have logs
    call_sites = report.get_call_sites()
    assert len(call_sites) > 0, "Should have at least one call site"

    logs = report.get_logs()
    total_logs = sum(len(values) for values in logs.values())
    assert total_logs > 0, "Should have logged values"

    print(
        f"✓ Iterative fibonacci logged {total_logs} values across {len(call_sites)} call sites"
    )


def test_fibonacci_recursive():
    """Test recursive fibonacci with call stack tracking."""
    report.init()

    result = fibonacci_recursive(5)
    assert result == 5, f"Expected 5, got {result}"

    # Verify we have logs with call stack info
    call_sites = report.get_call_sites()
    assert len(call_sites) > 0, "Should have at least one call site"

    logs = report.get_logs()
    # Check that we captured caller info
    found_caller_info = False
    for pickled_values in logs.values():
        for pickled in pickled_values:
            if isinstance(pickled, bytes):
                try:
                    value = pickle.loads(pickled)
                    # Check if we have a Caller object
                    if hasattr(value, "function") and hasattr(value, "filename"):
                        found_caller_info = True
                        break
                except:
                    pass

    assert found_caller_info, "Should have captured caller information in logs"
    print("✓ Recursive fibonacci captured call stack information")


if __name__ == "__main__":
    test_fibonacci_iterative()
    test_fibonacci_recursive()
    print("\nAll fibonacci tests passed!")
