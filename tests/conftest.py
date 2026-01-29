"""Pytest configuration and fixtures."""

import pytest
from autopsy import report, set_atexit_enabled, generate_html


def pytest_configure(config):
    """Disable atexit handler for tests."""
    set_atexit_enabled(False)


@pytest.fixture(autouse=True)
def reset_report():
    """Automatically reset the report before each test."""
    report.init(clear=True, warn=False)
    yield
    # Cleanup after test if needed


def pytest_sessionfinish(session, exitstatus):
    """Generate HTML report after all tests complete."""
    # Generate report for any test session that has items
    if session.items:
        try:
            generate_html(output_path="test_pytest_report.html")
            print(f"\n→ Test report saved to test_pytest_report.html")
        except Exception as e:
            print(f"\nWarning: Failed to generate test report: {e}")
