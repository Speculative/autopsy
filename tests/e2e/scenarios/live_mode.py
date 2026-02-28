"""Live mode scenario for e2e testing."""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from autopsy import report
from autopsy.report import ReportConfiguration


def scenario_live_mode():
    """Generate autopsy data in live mode for e2e testing."""
    # Initialize with live mode
    report.init(ReportConfiguration(
        auto_stack_trace=True,
        mode="live",
        live_mode_host="localhost",
        live_mode_port=8765
    ))

    print("Live mode test started!")
    print("Open http://localhost:8765/ in your browser")
    print("Waiting for client to connect...\n")

    # Wait for a client to connect before generating logs
    from autopsy.live_server import logs_transmitted
    max_wait = 10  # Wait up to 10 seconds for client
    for _ in range(max_wait * 2):
        if logs_transmitted():
            print("Client connected!")
            break
        time.sleep(0.5)
    else:
        print("No client connected, generating logs anyway...")

    print("Generating test data...\n")

    # Generate initial batch of logs
    for i in range(5):
        report.log(f"initial_log_{i}", i, i * 2)
        report.count(f"initial_count_{i % 2}")
        print(f"✓ Logged iteration {i}")
        time.sleep(0.1)  # Small delay to ensure logs are transmitted

    # Wait a bit, then add more logs
    time.sleep(2)
    print("\nAdding more logs...")

    for i in range(5, 10):
        report.log(f"additional_log_{i}", i, i * 2)
        report.count(f"additional_count_{i % 2}")
        report.hist(float(i * 1.5))
        print(f"✓ Logged iteration {i}")

    # Add timeline event
    report.timeline("live_test_complete")
    report.happened("Live mode test completed successfully")

    print("\n✓ Live mode scenario complete")
    print("Server will run for 30 more seconds for testing...")

    # Keep server running briefly for tests to connect
    time.sleep(30)
    print("Shutting down...")


if __name__ == "__main__":
    scenario_live_mode()
