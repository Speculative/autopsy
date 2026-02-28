#!/usr/bin/env python3
"""Generate autopsy reports from example programs.

Output format is controlled by the AUTOPSY_MODE environment variable
("json", "html", or "live"). Defaults to "json" if unset.
"""

import argparse
import sys

from autopsy import report
from autopsy.report import generate_html, generate_json, set_atexit_enabled


# Registry of available examples
EXAMPLES = {
    "kv_store": {
        "name": "KV Store with Transactions",
        "description": "Demonstrates a key-value store with transaction management",
        "module": "examples.kv_store_example",
    },
    "price_calculator": {
        "name": "Price Calculator (Caching Bug)",
        "description": "Demonstrates debugging a memoization cache collision bug",
        "module": "examples.price_calculator",
    },
    "price_calculator_tests": {
        "name": "Price Calculator Test Suite",
        "description": "Runs the test suite with autopsy instrumentation",
        "module": "examples.test_price_calculator",
        "is_test_suite": True,
    },
}


def load_example(example_name: str):
    """
    Load and return the run_example function from an example module.

    Args:
        example_name: Name of the example to load

    Returns:
        The run_example function from the module, or None for test suites

    Raises:
        ImportError: If the example module cannot be loaded
        AttributeError: If the module doesn't have a run_example function
    """
    if example_name not in EXAMPLES:
        raise ValueError(f"Unknown example: {example_name}")

    example_info = EXAMPLES[example_name]

    # Test suites are handled differently
    if example_info.get("is_test_suite"):
        return None

    module_name = example_info["module"]

    # Import the module using importlib to handle dotted names correctly
    import importlib

    module = importlib.import_module(module_name)

    if not hasattr(module, "run_example"):
        raise AttributeError(
            f"Example module '{module_name}' must have a 'run_example' function"
        )

    return module.run_example


def run_test_suite(example_name: str) -> int:
    """
    Run a test suite with autopsy instrumentation.

    Report output is handled by the autopsy pytest plugin based on AUTOPSY_MODE.

    Args:
        example_name: Name of the test suite example

    Returns:
        pytest exit code
    """
    import subprocess
    import sys

    example_info = EXAMPLES[example_name]
    module_name = example_info["module"]

    # Convert module name to file path
    test_file = module_name.replace(".", "/") + ".py"

    # Run pytest - report generation is handled by the autopsy pytest plugin
    # based on AUTOPSY_MODE env var (inherited from parent process)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            test_file,
            "-v",
            "--tb=short",
        ],
        cwd=".",
    )

    return result.returncode


def run_example_report(example_name: str, output_path: str = None) -> None:
    """
    Run an example and generate a report.

    Output format is determined by AUTOPSY_MODE env var or init() config.

    Args:
        example_name: Name of the example to run
        output_path: Optional path to write the report. If None, uses default.
    """
    example_info = EXAMPLES[example_name]
    print(f"Running example: {example_info['name']}")

    if example_info.get("is_test_suite"):
        exit_code = run_test_suite(example_name)
        if exit_code == 0:
            print("\n✓ All tests passed")
        elif exit_code == 1:
            print("\n⚠ Some tests failed (this is expected for this example)")
        else:
            print(f"\n✗ Test suite exited with code {exit_code}")
        return

    report.init()
    mode = report._config.mode

    if mode == "live":
        # In live mode, let the atexit handler manage the server lifecycle
        run_example = load_example(example_name)
        run_example()
        return

    # For file-based modes, disable atexit so we control output path explicitly
    set_atexit_enabled(False)

    # Load and run the example
    run_example = load_example(example_name)
    run_example()

    # Generate report based on configured mode
    if mode == "html":
        if output_path is None:
            output_path = "autopsy_report.html"
        print(f"\nGenerating HTML report: {output_path}")
        html = generate_html(output_path=output_path)
        print(f"✓ HTML report generated: {output_path}")
        print(f"✓ Report size: {len(html)} bytes")
        print(f"\nOpen {output_path} in your browser to view the report!")
    else:
        if output_path is None:
            output_path = "autopsy_report.json"
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
        description="Generate autopsy reports from example programs.\n\n"
        "Output format is controlled by the AUTOPSY_MODE environment variable\n"
        '("json", "html", or "live"). Defaults to "json" if unset.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Run subcommand
    run_parser = subparsers.add_parser(
        "run", help="Run an example and generate a report"
    )
    run_parser.add_argument(
        "example",
        nargs="?",
        default="kv_store",
        choices=EXAMPLES.keys(),
        help="Example to run (default: kv_store)",
    )
    run_parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output file path (default: autopsy_report.json or autopsy_report.html based on AUTOPSY_MODE)",
    )

    # List subcommand
    subparsers.add_parser("list", help="List available examples")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "run":
            run_example_report(args.example, args.output)
        elif args.command == "list":
            list_examples()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
