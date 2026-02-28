"""Test view scenario for e2e testing - generates a report with multiple test results."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from autopsy import report
from autopsy.report import generate_html
from autopsy.pytest import get_test_capture, AutopsyTestResult, AutopsyTestCapture
import autopsy.pytest as autopsy_pytest


def scenario_test_view():
    """Generate an autopsy report with multiple test results for e2e testing."""
    report.init(clear=True, warn=False)

    # Reset the global test capture
    autopsy_pytest._test_capture = AutopsyTestCapture()
    capture = get_test_capture()

    # Generate logs and test results for multiple tests
    # We need enough tests to exercise overflow behavior

    # Test 1: passing test with logs
    start_idx = report._log_index
    report.log("Starting test_addition")
    report.log(2, 3, 5)
    report.log("test_addition passed")
    t1 = AutopsyTestResult("tests/test_math.py::test_addition", "passed")
    t1.location = ("tests/test_math.py", 10, "test_addition")
    t1.start_log_index = start_idx
    t1.end_log_index = report._log_index - 1
    t1.log_count = report._log_index - start_idx
    capture.test_results.append(t1)

    # Test 2: failing test with logs
    start_idx = report._log_index
    report.log("Starting test_subtraction")
    report.log(10, 5, 3)
    report.log("Unexpected result")
    t2 = AutopsyTestResult("tests/test_math.py::test_subtraction", "failed")
    t2.location = ("tests/test_math.py", 20, "test_subtraction")
    t2.longrepr = (
        "def test_subtraction():\n"
        "    result = 10 - 5\n"
        ">   assert result == 3\n"
        "E   AssertionError: assert 5 == 3\n"
        "\n"
        "tests/test_math.py:23: AssertionError"
    )
    t2.error_summary = "AssertionError: assert 5 == 3"
    t2.start_log_index = start_idx
    t2.end_log_index = report._log_index - 1
    t2.log_count = report._log_index - start_idx
    capture.test_results.append(t2)

    # Test 3: passing test
    start_idx = report._log_index
    report.log("Starting test_multiply")
    report.log(4, 5, 20)
    t3 = AutopsyTestResult("tests/test_math.py::test_multiply", "passed")
    t3.location = ("tests/test_math.py", 30, "test_multiply")
    t3.start_log_index = start_idx
    t3.end_log_index = report._log_index - 1
    t3.log_count = report._log_index - start_idx
    capture.test_results.append(t3)

    # Test 4: skipped test
    start_idx = report._log_index
    t4 = AutopsyTestResult("tests/test_math.py::test_division_by_zero", "skipped")
    t4.location = ("tests/test_math.py", 40, "test_division_by_zero")
    t4.longrepr = "Skipped: division by zero not yet implemented"
    t4.start_log_index = start_idx
    t4.end_log_index = start_idx
    t4.log_count = 0
    capture.test_results.append(t4)

    # Test 5: another passing test
    start_idx = report._log_index
    report.log("Starting test_modulo")
    report.log(10, 3, 1)
    t5 = AutopsyTestResult("tests/test_math.py::test_modulo", "passed")
    t5.location = ("tests/test_math.py", 50, "test_modulo")
    t5.start_log_index = start_idx
    t5.end_log_index = report._log_index - 1
    t5.log_count = report._log_index - start_idx
    capture.test_results.append(t5)

    # Test 6: another failing test
    start_idx = report._log_index
    report.log("Starting test_power")
    report.log(2, 10, 512)
    t6 = AutopsyTestResult("tests/test_math.py::test_power", "failed")
    t6.location = ("tests/test_math.py", 60, "test_power")
    t6.longrepr = (
        "def test_power():\n"
        "    result = 2 ** 10\n"
        ">   assert result == 512\n"
        "E   AssertionError: assert 1024 == 512\n"
        "\n"
        "tests/test_math.py:63: AssertionError"
    )
    t6.error_summary = "AssertionError: assert 1024 == 512"
    t6.start_log_index = start_idx
    t6.end_log_index = report._log_index - 1
    t6.log_count = report._log_index - start_idx
    capture.test_results.append(t6)

    # Test 7: passing test
    start_idx = report._log_index
    report.log("Starting test_abs")
    report.log(-5, 5)
    t7 = AutopsyTestResult("tests/test_math.py::test_abs", "passed")
    t7.location = ("tests/test_math.py", 70, "test_abs")
    t7.start_log_index = start_idx
    t7.end_log_index = report._log_index - 1
    t7.log_count = report._log_index - start_idx
    capture.test_results.append(t7)

    # Test 8: passing test
    start_idx = report._log_index
    report.log("Starting test_floor")
    report.log(3.7, 3)
    t8 = AutopsyTestResult("tests/test_math.py::test_floor", "passed")
    t8.location = ("tests/test_math.py", 80, "test_floor")
    t8.start_log_index = start_idx
    t8.end_log_index = report._log_index - 1
    t8.log_count = report._log_index - start_idx
    capture.test_results.append(t8)

    # Generate HTML
    output_path = Path(__file__).parent.parent / "fixtures" / "test_view.html"
    generate_html(report, output_path=str(output_path))
    print(f"✓ Generated {output_path}")


if __name__ == "__main__":
    scenario_test_view()
