"""Table resize scenario for e2e testing.

This scenario creates a table with multiple columns to test that the table
always fills the available width when columns are added, removed, or when
the viewport changes size.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from autopsy import report
from autopsy.report import generate_html


def process_data(row_num: int):
    """Create rows with 5 columns - enough to test hiding/showing."""
    report.log(
        f"alpha_{row_num}",
        f"bravo_{row_num}",
        f"charlie_{row_num}",
        f"delta_{row_num}",
        f"echo_{row_num}",
    )


def scenario_table_resize():
    """Generate a report with a multi-column table for resize testing."""
    report.init(clear=True, warn=False)

    for i in range(20):
        process_data(i)

    # Generate HTML
    output_path = Path(__file__).parent.parent / "fixtures" / "table_resize.html"
    generate_html(report, output_path=str(output_path))
    print(f"✓ Generated {output_path}")


if __name__ == "__main__":
    scenario_table_resize()
