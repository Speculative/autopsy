"""
Minimal Live Mode Test - Simple example to verify live mode works.

This is a very basic test that logs a few values with live mode enabled.
"""

import time
from autopsy import report
from autopsy.report import ReportConfiguration


def run_example():
    """Run minimal live mode test."""
    # Initialize autopsy with live mode enabled
    report.init(ReportConfiguration(
        auto_stack_trace=True,
        live_mode=True,
        live_mode_host="localhost",
        live_mode_port=8765
    ))

    print("\nLive mode test started!")
    print("Open http://localhost:8765/ in your browser")
    print("Press Ctrl+C to stop\n")

    # Log some test data
    for i in range(10):
        report.log(f"Iteration {i}", i * 2)
        report.count(i % 3)
        report.hist(i * 10.5)
        report.timeline(f"iteration_{i}_complete")

        if i == 5:
            report.happened("Reached halfway point!")

        print(f"Logged iteration {i}")
        time.sleep(2)  # Wait 2 seconds between iterations

    print("\nTest complete! Server will keep running...")
    print("Press Ctrl+C to stop")

    # Keep the server running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")


if __name__ == "__main__":
    run_example()
