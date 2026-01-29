"""Demo test showing pytest integration with passing and failing tests."""

import autopsy


def test_passing_with_logs():
    """A passing test that generates logs."""
    autopsy.log("Starting computation")
    x = 10
    y = 20
    autopsy.log("x", x, "y", y)

    result = x + y
    autopsy.log("result", result)

    assert result == 30
    autopsy.log("Test passed successfully")


def test_failing_with_logs():
    """A failing test that generates logs - demonstrates failure tracking."""
    autopsy.log("Setting up test data")

    data = {"name": "test", "value": 42}
    autopsy.log("data", data)

    autopsy.log("Performing calculation")
    calculated = data["value"] * 2
    autopsy.log("calculated", calculated)

    # This assertion will fail
    assert calculated == 100, f"Expected 100 but got {calculated}"


def test_with_dashboard_functions():
    """Test using various dashboard functions."""
    autopsy.log("Running multiple operations")

    for i in range(5):
        autopsy.count("compute")
        autopsy.hist(i * 10.5)
        autopsy.log(f"Iteration {i}", i)

    autopsy.happened("checkpoint_reached")
    autopsy.timeline("operation_completed")

    assert True
