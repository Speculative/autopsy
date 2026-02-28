"""Pytest configuration for example test suites.

This conftest provides autopsy report integration for example tests.
Report output format is controlled by the AUTOPSY_MODE environment variable.
"""

import pytest

from autopsy import report


@pytest.fixture(scope="session", autouse=True)
def init_report(request):
    """Initialize autopsy report at the start of the test session."""
    report.init()
    report.timeline("Test session started")

    yield

    report.timeline("Test session completed")


@pytest.fixture(autouse=True)
def log_test_name(request):
    """Log the start and end of each test for tracing."""
    test_name = request.node.name
    report.log("test_start", test_name)
    yield
    report.log("test_end", test_name)
