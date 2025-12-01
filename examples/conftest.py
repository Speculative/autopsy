"""Pytest configuration for example test suites.

This conftest provides autopsy report integration for example tests.
"""

import pytest

from autopsy import report
from autopsy.report import generate_html


def pytest_addoption(parser):
    """Add command-line option to generate autopsy report."""
    parser.addoption(
        "--generate-report",
        action="store_true",
        default=False,
        help="Generate autopsy report after running tests",
    )
    parser.addoption(
        "--report-output",
        action="store",
        default=None,
        help="Output path for autopsy report (default: examples/<test_file>_report.html)",
    )


@pytest.fixture(scope="session", autouse=True)
def init_report(request):
    """Initialize autopsy report at the start of the test session."""
    report.init()
    report.timeline("Test session started")

    yield

    report.timeline("Test session completed")

    # Generate report if requested
    if request.config.getoption("--generate-report", default=False):
        output_path = request.config.getoption("--report-output")
        if output_path is None:
            output_path = "examples/test_report.html"
        generate_html(output_path=output_path)
        print(f"\n✓ Autopsy report saved to {output_path}")


@pytest.fixture(autouse=True)
def log_test_name(request):
    """Log the start and end of each test for tracing."""
    test_name = request.node.name
    report.log("test_start", test_name)
    yield
    report.log("test_end", test_name)
