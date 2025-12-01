"""Test basic logging functionality with multiple call sites."""

import pickle
from autopsy import report


def test_basic_logging():
    """Test that values are captured at different call sites."""
    report.init()

    # Log from different lines
    report.log(1)
    report.log(2, 3)
    report.log("hello", "world")  # Add second arg so "hello" isn't inferred as name
    report.log(4)

    # Verify we have logs
    logs = report.get_logs()
    call_sites = report.get_call_sites()

    assert len(call_sites) == 4, f"Expected 4 call sites, got {len(call_sites)}"

    # Verify values can be unpickled
    for call_site, value_groups in logs.items():
        assert len(value_groups) > 0, f"Call site {call_site} has no value groups"
        for group in value_groups:
            assert "values" in group, (
                f"Call site {call_site} group missing 'values' key"
            )
            assert len(group["values"]) > 0, (
                f"Call site {call_site} has empty value group"
            )
            for pickled in group["values"]:
                if isinstance(pickled, bytes):
                    _ = pickle.loads(pickled)


def test_multiple_calls_same_site():
    """Test that multiple calls at the same line accumulate."""
    report.init()

    for i in range(5):
        report.log(i)  # All calls are at the same line

    logs = report.get_logs()
    call_sites = report.get_call_sites()

    # Should have one call site
    assert len(call_sites) == 1, f"Expected 1 call site, got {len(call_sites)}"

    # Should have 5 value groups (one per call)
    value_groups = logs[call_sites[0]]
    assert len(value_groups) == 5, f"Expected 5 value groups, got {len(value_groups)}"

    # Verify values - each group should have one value
    values = [pickle.loads(group["values"][0]) for group in value_groups]
    assert values == [0, 1, 2, 3, 4], f"Expected [0,1,2,3,4], got {values}"
