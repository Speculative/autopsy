"""Sticky header alignment scenario for e2e testing.

This scenario creates a table with many columns (wide table) and many rows
to test sticky header alignment when scrolling.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from autopsy import report
from autopsy.report import generate_html


def process_wide_data(row_num: int):
    """Process data with many columns to create a wide table."""
    report.log(
        f"value_a_{row_num}",
        f"value_b_{row_num}",
        f"value_c_{row_num}",
        f"value_d_{row_num}",
        f"value_e_{row_num}",
        f"value_f_{row_num}",
        f"value_g_{row_num}",
        f"value_h_{row_num}",
        f"value_i_{row_num}",
        f"value_j_{row_num}",
        f"value_k_{row_num}",
        f"value_l_{row_num}",
        f"value_m_{row_num}",
        f"value_n_{row_num}",
        f"value_o_{row_num}",
        f"value_p_{row_num}",
        f"value_q_{row_num}",
        f"value_r_{row_num}",
        f"value_s_{row_num}",
        f"value_t_{row_num}",
    )


def scenario_sticky_header_alignment():
    """Generate a report with wide table to test sticky header alignment."""
    report.init(clear=True, warn=False)

    # Create many rows with wide data to trigger scrolling and sticky header
    for i in range(100):
        process_wide_data(i)

    # Generate HTML
    output_path = Path(__file__).parent.parent / "fixtures" / "sticky_header_alignment.html"
    generate_html(report, output_path=str(output_path))
    print(f"✓ Generated {output_path}")


if __name__ == "__main__":
    scenario_sticky_header_alignment()
