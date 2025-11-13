"""Test basic logging functionality with multiple call sites."""

import pickle
from autopsy import report


def test_basic_logging():
    """Test that values are captured at different call sites."""
    report.init()

    # Log from different lines
    report.log(1)
    report.log(2, 3)
    report.log("hello")
    report.log(4)

    # Verify we have logs
    logs = report.get_logs()
    call_sites = report.get_call_sites()

    assert len(call_sites) == 4, f"Expected 4 call sites, got {len(call_sites)}"

    # Verify values can be unpickled
    for call_site, pickled_values in logs.items():
        assert len(pickled_values) > 0, f"Call site {call_site} has no values"
        for pickled in pickled_values:
            if isinstance(pickled, bytes):
                unpickled = pickle.loads(pickled)


def test_multiple_calls_same_site():
    """Test that multiple calls at the same line accumulate."""
    report.init()

    for i in range(5):
        report.log(i)  # All calls are at the same line

    logs = report.get_logs()
    call_sites = report.get_call_sites()

    # Should have one call site
    assert len(call_sites) == 1, f"Expected 1 call site, got {len(call_sites)}"

    # Should have 5 values
    pickled_values = logs[call_sites[0]]
    assert len(pickled_values) == 5, f"Expected 5 values, got {len(pickled_values)}"

    # Verify values
    values = [pickle.loads(p) for p in pickled_values]
    assert values == [0, 1, 2, 3, 4], f"Expected [0,1,2,3,4], got {values}"
