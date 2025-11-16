"""Demo script showing end-to-end HTML report generation."""

from autopsy.report import Report, generate_html


def main():
    """Demonstrate HTML report generation."""
    # Create a new report
    report = Report()

    # Log some sample data
    print("Logging sample data...")
    report.log(42, "hello", "world")
    report.log({"user_id": 123, "name": "Alice"})
    report.log([1, 2, 3, 4, 5])
    report.log("Another log entry")

    # Generate HTML report
    print("Generating HTML report...")
    output_file = "report.html"
    html = generate_html(report, output_file)

    print(f"✓ HTML report generated: {output_file}")
    print(f"✓ Report size: {len(html)} bytes")
    print(f"\nOpen {output_file} in your browser to view the report!")


if __name__ == "__main__":
    main()

