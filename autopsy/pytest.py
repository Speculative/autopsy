"""Pytest plugin for capturing test results and associating them with autopsy logs."""

import pytest
from typing import Optional, List, Dict, Any
from pathlib import Path

from .report import get_report


class AutopsyTestResult:
    """Represents a single test case result."""

    def __init__(self, nodeid: str, outcome: str):
        self.nodeid = nodeid  # Test identifier like "tests/test_foo.py::test_bar"
        self.outcome = outcome  # "passed", "failed", "skipped", "error"
        self.longrepr: Optional[str] = None  # Failure message/traceback
        self.location: Optional[tuple] = None  # (filename, line, test_name)
        self.start_log_index: Optional[int] = None  # First log during this test
        self.end_log_index: Optional[int] = None  # Last log during this test
        self.log_count: int = 0  # Number of logs during this test

    def to_dict(self) -> Dict[str, Any]:
        """Convert test result to JSON-serializable dict."""
        result = {
            "nodeid": self.nodeid,
            "outcome": self.outcome,
            "log_count": self.log_count,
        }

        if self.location:
            result["filename"] = str(self.location[0])
            result["line"] = self.location[1]
            result["test_name"] = self.location[2]

        if self.longrepr:
            result["failure_message"] = self.longrepr

        if self.start_log_index is not None:
            result["start_log_index"] = self.start_log_index

        if self.end_log_index is not None:
            result["end_log_index"] = self.end_log_index

        return result


class AutopsyTestCapture:
    """Captures test execution and associates with autopsy logs."""

    def __init__(self):
        self.test_results: List[AutopsyTestResult] = []
        self.current_test: Optional[AutopsyTestResult] = None
        self.test_start_log_index: Optional[int] = None

    def start_test(self, nodeid: str):
        """Called when a test starts."""
        report = get_report()
        # Record the current log index when test starts
        self.test_start_log_index = report._log_index

    def finish_test(self, item, outcome: str, longrepr=None):
        """Called when a test finishes."""
        report = get_report()

        # Create test result
        test_result = AutopsyTestResult(item.nodeid, outcome)

        # Get location (file, line, test name)
        try:
            fspath = str(item.fspath) if hasattr(item, 'fspath') else str(item.path)
            test_result.location = (fspath, item.location[1] if hasattr(item, 'location') else 0, item.name)
        except Exception:
            pass

        # Record failure message if test failed
        if longrepr:
            test_result.longrepr = str(longrepr)

        # Calculate log indices for this test
        if self.test_start_log_index is not None:
            test_result.start_log_index = self.test_start_log_index
            test_result.end_log_index = report._log_index - 1
            test_result.log_count = max(0, report._log_index - self.test_start_log_index)

        self.test_results.append(test_result)
        self.test_start_log_index = None

    def get_results(self) -> List[Dict[str, Any]]:
        """Get all test results as JSON-serializable dicts."""
        return [result.to_dict() for result in self.test_results]


# Global instance to capture test results
_test_capture = AutopsyTestCapture()


def get_test_capture() -> AutopsyTestCapture:
    """Get the global test capture instance."""
    return _test_capture


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    """Hook called for each test item."""
    _test_capture.start_test(item.nodeid)
    outcome = yield
    # Note: We'll capture the result in pytest_runtest_makereport
    # We don't suppress the outcome - it propagates normally


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook called to create test reports."""
    outcome = yield
    report = outcome.get_result()

    # Record test results after the "call" phase, but also handle failures in other phases
    # We need to track if we've already recorded this test to avoid duplicates
    if not hasattr(item, '_autopsy_recorded'):
        item._autopsy_recorded = False

    # Record on the "call" phase (main test execution)
    if report.when == "call":
        longrepr = None
        if report.failed:
            longrepr = str(report.longrepr) if report.longrepr else "Test failed"
        elif report.skipped:
            longrepr = str(report.longrepr) if report.longrepr else "Test skipped"

        _test_capture.finish_test(item, report.outcome, longrepr)
        item._autopsy_recorded = True

    # If test failed during setup, record it
    elif report.when == "setup" and report.failed and not item._autopsy_recorded:
        longrepr = str(report.longrepr) if report.longrepr else "Setup failed"
        _test_capture.finish_test(item, "error", longrepr)
        item._autopsy_recorded = True

    # If test failed during teardown and we haven't recorded yet, record it
    elif report.when == "teardown" and report.failed and not item._autopsy_recorded:
        longrepr = str(report.longrepr) if report.longrepr else "Teardown failed"
        _test_capture.finish_test(item, "error", longrepr)
        item._autopsy_recorded = True


def pytest_configure(config):
    """Called after command line options have been parsed."""
    # Reset test capture at start of pytest session
    global _test_capture
    _test_capture = AutopsyTestCapture()
