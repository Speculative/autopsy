"""History and stream view scenario for e2e testing."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from autopsy import report, call_stack
from autopsy.report import generate_html


def helper_function_a(value):
    """Helper function to create varied call stacks."""
    report.log("from_helper_a", value)
    return value * 2


def helper_function_b(value):
    """Another helper function to create varied call stacks."""
    report.log("from_helper_b", value)
    return value + 10


def nested_function(depth, max_depth):
    """Create nested call stacks."""
    if depth >= max_depth:
        report.log("deepest_level", depth)
        return depth

    report.log("nesting", depth, max_depth)
    return nested_function(depth + 1, max_depth)


def scenario_history_stream():
    """Generate a comprehensive report for testing history and stream views."""
    report.init(clear=True, warn=False)

    # Create lots of logs from different call sites (200 items for virtual scrolling)
    for i in range(200):
        # Mix up the call sites
        if i % 3 == 0:
            helper_function_a(i)
        elif i % 3 == 1:
            helper_function_b(i)
        else:
            # Log nested objects so TreeView has expandable items
            data = {"index": i, "squared": i ** 2, "info": {"name": f"item_{i}", "tags": [f"tag_{j}" for j in range(i % 4)]}}
            report.log("main_loop", data)

        # Add some counts
        report.count(f"category_{i % 5}")

        # Add histogram data
        report.hist(float(i * 1.5))

    # Create nested call stacks to test the call stack panel
    for depth in [3, 5, 7]:
        nested_function(0, depth)

    # Add timeline events
    report.timeline("phase_1_start")
    for i in range(10):
        report.log("processing_item", i)
    report.timeline("phase_1_end")

    report.timeline("phase_2_start")
    for i in range(10, 20):
        report.log("processing_item", i)
    report.timeline("phase_2_end")

    # Generate HTML
    output_path = Path(__file__).parent.parent / "fixtures" / "history_stream.html"
    generate_html(report, output_path=str(output_path))
    print(f"✓ Generated {output_path}")


if __name__ == "__main__":
    scenario_history_stream()
