"""Basic logging scenario for e2e testing."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from autopsy import report
from autopsy.report import generate_html


def scenario_basic_logging():
    """Generate a basic autopsy report with logging from multiple call sites."""
    report.init(clear=True, warn=False)

    # Basic logs with different types
    report.log(42, name="single_value")
    report.log("hello", "world", name="multiple_values")
    report.log({"key": "value", "nested": {"data": 123}}, name="dict_value")
    report.log([1, 2, 3, 4, 5], name="list_value")

    # Multiple calls from the same site
    for i in range(10):
        report.log(i, i * 2, name=f"iteration_{i}")

    # Test different report methods
    report.count("count_test")
    report.count("count_test")
    report.count("count_test")

    for val in [1.5, 2.3, 4.1, 2.8, 3.9, 1.2, 5.5, 4.7]:
        report.hist(val)

    report.happened("Important event occurred")

    # Generate HTML
    output_path = Path(__file__).parent.parent / "fixtures" / "basic_logging.html"
    generate_html(report, output_path=str(output_path))
    print(f"✓ Generated {output_path}")


if __name__ == "__main__":
    scenario_basic_logging()
