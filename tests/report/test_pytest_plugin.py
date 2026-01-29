"""Test pytest plugin integration with autopsy."""

import autopsy


def test_basic_pass():
    """A simple passing test with logs."""
    autopsy.log("Starting test")
    x = 5
    autopsy.log(x)
    assert x == 5
    autopsy.log("Test passed")


def test_with_multiple_logs():
    """Test with multiple log statements."""
    for i in range(3):
        autopsy.log(i)
    assert True


def test_no_logs():
    """Test without any logs."""
    assert 1 + 1 == 2


def test_with_dashboard():
    """Test using dashboard functions."""
    autopsy.count("event_a")
    autopsy.count("event_b")
    autopsy.count("event_a")
    autopsy.hist(42.5)
    autopsy.happened("checkpoint reached")
    assert True
