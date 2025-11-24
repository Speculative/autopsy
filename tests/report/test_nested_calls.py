"""Test nested function calls to validate per-call-site tracking."""

from autopsy import report


def inner_function(x):
    """Inner function that logs its parameter."""
    report.log(x, f"inner: {x}")
    return x * 2


def middle_function(y):
    """Middle function that calls inner."""
    report.log(y, f"middle: {y}")
    result = inner_function(y)
    report.log(result, f"middle result: {result}")
    return result


def outer_function(z):
    """Outer function that calls middle."""
    report.log(z, f"outer: {z}")
    result = middle_function(z)
    report.log(result, f"outer result: {result}")
    return result


def test_nested_calls():
    """Test that nested calls create separate call sites."""
    report.init()

    # Call the outer function
    result = outer_function(5)

    assert result == 10, f"Expected result 10, got {result}"

    # Verify we have multiple call sites
    call_sites = report.get_call_sites()
    assert (
        len(call_sites) >= 3
    ), f"Expected at least 3 call sites, got {len(call_sites)}"

    # Verify each call site has logged values
    logs = report.get_logs()
    for call_site in call_sites:
        assert call_site in logs, f"Call site {call_site} not in logs"
        assert len(logs[call_site]) > 0, f"Call site {call_site} has no values"


def test_recursive_function():
    """Test that recursive calls create separate call sites."""
    report.init()

    def factorial(n):
        report.log(n, f"factorial({n})")
        if n <= 1:
            return 1
        return n * factorial(n - 1)

    result = factorial(4)
    assert result == 24, f"Expected 24, got {result}"

    # Each recursive call should be at the same call site (same line)
    # but we should have multiple log entries
    call_sites = report.get_call_sites()
    logs = report.get_logs()

    # Find the factorial call site (line 55 where report.log is called)
    factorial_site = None
    for site in call_sites:
        filename, lineno = site
        if lineno == 55:  # Line where report.log is called inside factorial
            factorial_site = site
            break

    assert (
        factorial_site is not None
    ), f"Could not find factorial call site. Found sites: {call_sites}"

    # Should have 4 log entries (one for each call: 4, 3, 2, 1)
    pickled_values = logs[factorial_site]
    assert (
        len(pickled_values) >= 4
    ), f"Expected at least 4 values, got {len(pickled_values)}"
