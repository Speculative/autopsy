"""Pytest configuration and fixtures."""

import pytest
from autopsy import report


@pytest.fixture(autouse=True)
def reset_report():
    """Automatically reset the report before each test."""
    report.init()
    yield
    # Cleanup after test if needed
