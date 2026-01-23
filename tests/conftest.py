"""Pytest configuration and fixtures."""

import pytest
from autopsy import report, set_atexit_enabled


def pytest_configure(config):
    """Disable atexit handler for tests."""
    set_atexit_enabled(False)


@pytest.fixture(autouse=True)
def reset_report():
    """Automatically reset the report before each test."""
    report.init(clear=True, warn=False)
    yield
    # Cleanup after test if needed
