"""Test log ordering in various scenarios: loops, recursion, and async code."""

import asyncio
from typing import Any, Dict, List, Tuple

from autopsy.report import Report


def get_logs_in_order(
    report: Report,
) -> List[Tuple[int, Tuple[str, int], Dict[str, Any]]]:
    """
    Get all logs from a report in chronological order.

    Returns a list of tuples: (log_index, call_site, group)
    where call_site is (filename, line_number).
    """
    logs = report.get_logs()
    all_groups = []
    for call_site, value_groups in logs.items():
        for group in value_groups:
            all_groups.append((group["log_index"], call_site, group))

    # Sort by log_index to get chronological order
    all_groups.sort(key=lambda x: x[0])
    return all_groups


def test_loop_ordering():
    """Test that logs inside a loop maintain correct order."""
    report = Report()

    # Log before the loop
    report.log("before_loop")

    # Log inside a loop
    for i in range(5):
        report.log("iteration", i)

    # Log after the loop
    report.log("after_loop")

    # Get all logs in chronological order
    all_groups = get_logs_in_order(report)

    # Verify we have the expected number of logs: 1 + 5 + 1 = 7
    assert len(all_groups) == 7, f"Expected 7 log entries, got {len(all_groups)}"

    # Verify indices are sequential
    for i, (log_index, call_site, group) in enumerate(all_groups):
        assert log_index == i, f"Expected log_index {i}, got {log_index}"

    # Verify the first log is "before_loop"
    # Verify the last log is "after_loop"
    # Verify the middle 5 logs are "iteration" logs
    assert (
        all_groups[0][2]["values"][0] == b'"before_loop"'
        or b"before_loop" in all_groups[0][2]["values"][0]
    )
    assert (
        all_groups[-1][2]["values"][0] == b'"after_loop"'
        or b"after_loop" in all_groups[-1][2]["values"][0]
    )


def test_recursive_ordering():
    """Test that logs in recursive function calls maintain correct order."""
    report = Report()

    def factorial(n: int, depth: int = 0) -> int:
        """Compute factorial with logging at entry and exit."""
        # Log entry
        report.log("enter", n, depth)

        if n <= 1:
            result = 1
        else:
            result = n * factorial(n - 1, depth + 1)

        # Log exit
        report.log("exit", n, result, depth)
        return result

    # Call factorial(5)
    result = factorial(5)
    assert result == 120

    # Get all logs in chronological order
    all_groups = get_logs_in_order(report)

    # We should have:
    # enter(5,0), enter(4,1), enter(3,2), enter(2,3), enter(1,4),
    # exit(1,1,4), exit(2,2,3), exit(3,6,2), exit(4,24,1), exit(5,120,0)
    # Total: 10 logs (5 enter + 5 exit)
    assert len(all_groups) == 10, f"Expected 10 log entries, got {len(all_groups)}"

    # Verify indices are sequential
    for i, (log_index, call_site, group) in enumerate(all_groups):
        assert log_index == i, f"Expected log_index {i}, got {log_index}"

    # Verify the pattern: first 5 should be enters (going deeper), next 5 should be exits (unwinding)
    # The first 5 logs should all be from the "enter" line
    # The next 5 logs should all be from the "exit" line
    enter_call_site = None
    exit_call_site = None

    for i in range(5):
        call_site = all_groups[i][1]
        if enter_call_site is None:
            enter_call_site = call_site
        assert call_site == enter_call_site, f"Log {i} should be from enter call site"

    for i in range(5, 10):
        call_site = all_groups[i][1]
        if exit_call_site is None:
            exit_call_site = call_site
        assert call_site == exit_call_site, f"Log {i} should be from exit call site"

    # Verify enter and exit are from different call sites
    assert enter_call_site != exit_call_site


def test_async_ordering():
    """Test that logs in async code with forced ordering maintain correct order."""
    report = Report()

    # Create events to control execution order
    event1 = asyncio.Event()
    event2 = asyncio.Event()
    event3 = asyncio.Event()

    async def task1():
        """First task - logs, then waits, then logs again."""
        report.log("task1_start")
        event1.set()  # Signal that task1 started
        await event2.wait()  # Wait for task2 to start
        report.log("task1_end")
        event3.set()  # Signal task1 completed

    async def task2():
        """Second task - waits, then logs."""
        await event1.wait()  # Wait for task1 to start
        report.log("task2_start")
        event2.set()  # Signal task2 started
        await event3.wait()  # Wait for task1 to complete
        report.log("task2_end")

    async def run_tasks():
        """Run both tasks concurrently."""
        await asyncio.gather(task1(), task2())

    # Run the async tasks
    asyncio.run(run_tasks())

    # Get all logs in chronological order
    all_groups = get_logs_in_order(report)

    # Expected order: task1_start, task2_start, task1_end, task2_end
    assert len(all_groups) == 4, f"Expected 4 log entries, got {len(all_groups)}"

    # Verify indices are sequential
    for i, (log_index, call_site, group) in enumerate(all_groups):
        assert log_index == i, f"Expected log_index {i}, got {log_index}"


def test_mixed_scenario():
    """Test a complex scenario with loops, function calls, and multiple call sites."""
    report = Report()

    def helper(x: int):
        """Helper function that logs."""
        report.log("helper_start", x)
        result = x * 2
        report.log("helper_end", x, result)
        return result

    # Main execution
    report.log("main_start")

    results = []
    for i in range(3):
        report.log("loop_iteration", i)
        result = helper(i)
        results.append(result)
        report.log("loop_result", i, result)

    report.log("main_end", results)

    # Get all logs in chronological order
    all_groups = get_logs_in_order(report)

    # Expected sequence:
    # main_start (1)
    # For each iteration (3 iterations):
    #   loop_iteration, helper_start, helper_end, loop_result (4 logs per iteration = 12)
    # main_end (1)
    # Total: 1 + 12 + 1 = 14
    assert len(all_groups) == 14, f"Expected 14 log entries, got {len(all_groups)}"

    # Verify indices are sequential
    for i, (log_index, call_site, group) in enumerate(all_groups):
        assert log_index == i, f"Expected log_index {i}, got {log_index}"
