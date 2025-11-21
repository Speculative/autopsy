#!/usr/bin/env python3
"""Generate autopsy reports from example programs.

This CLI tool allows you to run example programs and generate reports in different formats.
"""

import argparse
import sys
from pathlib import Path

from autopsy import report
from autopsy.report import generate_html, generate_json


# Registry of available examples
EXAMPLES = {
    "kv_store": {
        "name": "KV Store with Transactions",
        "description": "Demonstrates a key-value store with transaction management",
        "module": "examples.kv_store_example",
    },
}


def load_example(example_name: str):
    """
    Load and return the run_example function from an example module.

    Args:
        example_name: Name of the example to load

    Returns:
        The run_example function from the module

    Raises:
        ImportError: If the example module cannot be loaded
        AttributeError: If the module doesn't have a run_example function
    """
    if example_name not in EXAMPLES:
        raise ValueError(f"Unknown example: {example_name}")

    example_info = EXAMPLES[example_name]
    module_name = example_info["module"]

    # Import the module using importlib to handle dotted names correctly
    import importlib
    module = importlib.import_module(module_name)

    if not hasattr(module, "run_example"):
        raise AttributeError(
            f"Example module '{module_name}' must have a 'run_example' function"
        )

    return module.run_example


def generate_html_report(example_name: str, output_path: str) -> None:
    """
    Generate an HTML report from an example program.

    Args:
        example_name: Name of the example to run
        output_path: Path to write the HTML report
    """
    print(f"Running example: {EXAMPLES[example_name]['name']}")
    report.init()

    # Load and run the example
    run_example = load_example(example_name)
    run_example()

    # Generate HTML
    print(f"\nGenerating HTML report: {output_path}")
    html = generate_html(output_path=output_path)

    print(f"✓ HTML report generated: {output_path}")
    print(f"✓ Report size: {len(html)} bytes")
    print(f"\nOpen {output_path} in your browser to view the report!")


def generate_json_report(example_name: str, output_path: str) -> None:
    """
    Generate a JSON report from an example program.

    Args:
        example_name: Name of the example to run
        output_path: Path to write the JSON report
    """
    print(f"Running example: {EXAMPLES[example_name]['name']}")
    report.init()

    # Load and run the example
    run_example = load_example(example_name)
    run_example()

    # Generate JSON
    print(f"\nGenerating JSON report: {output_path}")
    json_str = generate_json(output_path=output_path)

    print(f"✓ JSON report generated: {output_path}")
    print(f"✓ Report size: {len(json_str)} bytes")


def list_examples() -> None:
    """List all available examples."""
    print("Available examples:\n")
    for name, info in EXAMPLES.items():
        print(f"  {name:15} - {info['description']}")
    print()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate autopsy reports from example programs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # HTML subcommand
    html_parser = subparsers.add_parser(
        "html", help="Generate HTML report (report.html)"
    )
    html_parser.add_argument(
        "example",
        nargs="?",
        default="kv_store",
        choices=EXAMPLES.keys(),
        help="Example to run (default: kv_store)",
    )
    html_parser.add_argument(
        "-o",
        "--output",
        default="report.html",
        help="Output file path (default: report.html)",
    )

    # JSON subcommand
    json_parser = subparsers.add_parser(
        "json", help="Generate JSON report (autopsy_html/dev-data.json)"
    )
    json_parser.add_argument(
        "example",
        nargs="?",
        default="kv_store",
        choices=EXAMPLES.keys(),
        help="Example to run (default: kv_store)",
    )
    json_parser.add_argument(
        "-o",
        "--output",
        default="autopsy_html/dev-data.json",
        help="Output file path (default: autopsy_html/dev-data.json)",
    )

    # List subcommand
    list_parser = subparsers.add_parser("list", help="List available examples")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "html":
            generate_html_report(args.example, args.output)
        elif args.command == "json":
            generate_json_report(args.example, args.output)
        elif args.command == "list":
            list_examples()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
