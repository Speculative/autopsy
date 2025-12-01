"""Test dashboard collection features: count, hist, timeline, happened."""

import json
import time

from autopsy import report


def test_count_basic():
    """Test basic value counting."""
    report.init()

    # Count some values from the same call site (helper function)
    def count_value1():
        report.count("value1")

    def count_value2():
        report.count("value2")

    # Call helper functions multiple times - all calls will be at same call site
    count_value1()
    count_value1()
    count_value2()
    count_value1()

    # Check JSON output
    data = report.to_json()
    assert "dashboard" in data
    assert "counts" in data["dashboard"]
    # Should have 2 call sites (one for value1, one for value2)
    assert len(data["dashboard"]["counts"]) == 2

    # Aggregate counts across call sites
    total_value1_count = 0
    total_value2_count = 0
    for count_entry in data["dashboard"]["counts"]:
        for key, value_data in count_entry["value_counts"].items():
            parsed_key = json.loads(key)
            if parsed_key == "value1":
                total_value1_count += value_data["count"]
            elif parsed_key == "value2":
                total_value2_count += value_data["count"]

    assert total_value1_count == 3, f"Expected value1 count 3, got {total_value1_count}"
    assert total_value2_count == 1, f"Expected value2 count 1, got {total_value2_count}"


def test_count_multiple_call_sites():
    """Test counting from different call sites."""
    report.init()

    def func1():
        report.count("func1_value")

    def func2():
        report.count("func2_value")

    func1()
    func1()
    func2()

    data = report.to_json()
    assert len(data["dashboard"]["counts"]) == 2

    # Verify each call site has correct counts
    call_sites = {
        entry["call_site"]["function_name"]: entry
        for entry in data["dashboard"]["counts"]
    }
    assert "func1" in call_sites
    assert "func2" in call_sites

    func1_entry = call_sites["func1"]
    func1_value_key = None
    for key, value_data in func1_entry["value_counts"].items():
        parsed_key = json.loads(key)
        if parsed_key == "func1_value":
            func1_value_key = key
            assert value_data["count"] == 2
            break
    assert func1_value_key is not None


def test_count_with_class():
    """Test counting from class methods."""
    report.init()

    class TestClass:
        def method(self):
            report.count("class_value")

    obj = TestClass()
    obj.method()
    obj.method()

    data = report.to_json()
    assert len(data["dashboard"]["counts"]) == 1
    count_entry = data["dashboard"]["counts"][0]
    assert count_entry["call_site"]["class_name"] == "TestClass"
    assert count_entry["call_site"]["function_name"] == "method"


def test_hist_basic():
    """Test basic histogram collection."""
    report.init()

    # Collect some numbers from the same call site (helper function)
    def collect_number(num):
        report.hist(num)

    # Call helper function multiple times - all calls will be at same call site
    collect_number(1.5)
    collect_number(2.0)
    collect_number(1.5)
    collect_number(3.0)

    data = report.to_json()
    assert "dashboard" in data
    assert "histograms" in data["dashboard"]
    assert len(data["dashboard"]["histograms"]) == 1

    hist_entry = data["dashboard"]["histograms"][0]
    assert "call_site" in hist_entry
    assert "values" in hist_entry
    assert len(hist_entry["values"]) == 4

    # Verify values
    values = [v["value"] for v in hist_entry["values"]]
    assert values == [1.5, 2.0, 1.5, 3.0]

    # Verify stack traces are captured
    stack_trace_ids = [
        v["stack_trace_id"] for v in hist_entry["values"] if v["stack_trace_id"]
    ]
    assert len(stack_trace_ids) == 4


def test_hist_multiple_call_sites():
    """Test histogram collection from different call sites."""
    report.init()

    def func1():
        report.hist(10.0)

    def func2():
        report.hist(20.0)

    func1()
    func2()

    data = report.to_json()
    assert len(data["dashboard"]["histograms"]) == 2


def test_timeline_basic():
    """Test basic timeline event recording."""
    report.init()

    # Record some events
    report.timeline("event1")
    time.sleep(0.01)  # Small delay to ensure different timestamps
    report.timeline("event2")
    time.sleep(0.01)
    report.timeline("event3")

    data = report.to_json()
    assert "dashboard" in data
    assert "timeline" in data["dashboard"]
    assert len(data["dashboard"]["timeline"]) == 3

    timeline = data["dashboard"]["timeline"]
    assert timeline[0]["event_name"] == "event1"
    assert timeline[1]["event_name"] == "event2"
    assert timeline[2]["event_name"] == "event3"

    # Verify timestamps are in order
    timestamps = [e["timestamp"] for e in timeline]
    assert timestamps == sorted(timestamps), "Timeline should be sorted by timestamp"

    # Verify timestamps are different
    assert timestamps[0] < timestamps[1] < timestamps[2]

    # Verify call site and stack trace info
    for event in timeline:
        assert "call_site" in event
        assert "function_name" in event["call_site"]
        assert event["stack_trace_id"] is not None


def test_timeline_multiple_call_sites():
    """Test timeline events from different call sites."""
    report.init()

    def func1():
        report.timeline("func1_event")

    def func2():
        report.timeline("func2_event")

    func1()
    func2()

    data = report.to_json()
    assert len(data["dashboard"]["timeline"]) == 2

    # Verify function names are captured
    function_names = {
        e["call_site"]["function_name"] for e in data["dashboard"]["timeline"]
    }
    assert "func1" in function_names
    assert "func2" in function_names


def test_happened_basic():
    """Test basic invocation counting."""
    report.init()

    # Count invocations from the same call site (helper function)
    def count_invocation():
        report.happened()

    # Call helper function multiple times - all calls will be at same call site
    count_invocation()
    count_invocation()
    count_invocation()

    data = report.to_json()
    assert "dashboard" in data
    assert "happened" in data["dashboard"]
    assert len(data["dashboard"]["happened"]) == 1

    happened_entry = data["dashboard"]["happened"][0]
    assert happened_entry["count"] == 3
    assert len(happened_entry["stack_trace_ids"]) == 3
    assert "call_site" in happened_entry


def test_happened_with_message():
    """Test invocation counting with messages."""
    report.init()

    # Count invocations from the same call site (helper function)
    def count_with_message(msg):
        report.happened(msg)

    # Call helper function multiple times - all calls will be at same call site
    count_with_message("test message")
    count_with_message("test message")
    count_with_message("different message")

    data = report.to_json()
    happened_entry = data["dashboard"]["happened"][0]
    assert happened_entry["count"] == 3
    # Message should be the first one provided
    assert happened_entry["message"] == "test message"


def test_happened_multiple_call_sites():
    """Test invocation counting from different call sites."""
    report.init()

    def func1():
        report.happened("func1")

    def func2():
        report.happened("func2")

    func1()
    func1()
    func2()

    data = report.to_json()
    assert len(data["dashboard"]["happened"]) == 2

    # Verify counts per call site
    call_sites = {
        entry["call_site"]["function_name"]: entry
        for entry in data["dashboard"]["happened"]
    }
    assert call_sites["func1"]["count"] == 2
    assert call_sites["func2"]["count"] == 1


def test_happened_with_class():
    """Test invocation counting from class methods."""
    report.init()

    class TestClass:
        def method(self):
            report.happened("class_method")

    obj = TestClass()
    obj.method()
    obj.method()

    data = report.to_json()
    assert len(data["dashboard"]["happened"]) == 1
    happened_entry = data["dashboard"]["happened"][0]
    assert happened_entry["call_site"]["class_name"] == "TestClass"
    assert happened_entry["call_site"]["function_name"] == "method"
    assert happened_entry["count"] == 2


def test_dashboard_with_stack_traces_disabled():
    """Test dashboard features when stack traces are disabled."""
    from autopsy.report import ReportConfiguration

    config = ReportConfiguration(auto_stack_trace=False)
    report.init(config)

    report.count("value")
    report.hist(1.0)
    report.timeline("event")
    report.happened()

    data = report.to_json()
    assert "dashboard" in data

    # Counts should still work but without stack trace IDs
    count_entry = data["dashboard"]["counts"][0]
    for value_data in count_entry["value_counts"].values():
        assert len(value_data["stack_trace_ids"]) == 0

    # Histogram should still work but without stack trace IDs
    hist_entry = data["dashboard"]["histograms"][0]
    for value in hist_entry["values"]:
        assert value["stack_trace_id"] is None

    # Timeline should still work but without stack trace ID
    timeline_entry = data["dashboard"]["timeline"][0]
    assert timeline_entry["stack_trace_id"] is None

    # Happened should still work but without stack trace IDs
    happened_entry = data["dashboard"]["happened"][0]
    assert len(happened_entry["stack_trace_ids"]) == 0


def test_dashboard_init_clears_data():
    """Test that init() clears dashboard data."""
    report.init()

    report.count("value")
    report.hist(1.0)
    report.timeline("event")
    report.happened()

    data1 = report.to_json()
    assert "dashboard" in data1

    # Reinitialize
    report.init()

    data2 = report.to_json()
    assert "dashboard" not in data2 or (
        len(data2["dashboard"]["counts"]) == 0
        and len(data2["dashboard"]["histograms"]) == 0
        and len(data2["dashboard"]["timeline"]) == 0
        and len(data2["dashboard"]["happened"]) == 0
    )


def test_dashboard_mixed_with_logs():
    """Test that dashboard features work alongside regular logs."""
    report.init()

    report.log("regular log")
    report.count("counted value")
    report.hist(5.0)
    report.timeline("timeline event")
    report.happened("happened")
    report.log("another log")

    data = report.to_json()
    # call_sites includes both regular log() calls and dashboard call sites
    # 2 regular log() calls + 4 dashboard calls (count, hist, timeline, happened) = 6 total
    assert len(data["call_sites"]) == 6
    assert "dashboard" in data
    assert len(data["dashboard"]["counts"]) == 1
    assert len(data["dashboard"]["histograms"]) == 1
    assert len(data["dashboard"]["timeline"]) == 1
    assert len(data["dashboard"]["happened"]) == 1


def test_count_with_complex_values():
    """Test counting with complex values (lists, dicts, etc.)."""
    report.init()

    # Count complex values - use a loop to ensure same call site
    def count_complex():
        for _ in range(2):
            report.count([1, 2, 3])
        report.count({"key": "value"})

    count_complex()

    # Verify JSON serialization works and contains the expected data
    data = report.to_json()
    assert "dashboard" in data
    assert "counts" in data["dashboard"]
    assert len(data["dashboard"]["counts"]) > 0

    # Verify that complex values (lists and dicts) can be counted and serialized
    found_list = False
    found_dict = False

    for count_entry in data["dashboard"]["counts"]:
        for key, value_data in count_entry["value_counts"].items():
            try:
                parsed = json.loads(key)
                if isinstance(parsed, list):
                    found_list = True
                    # Verify the count structure is correct
                    assert "count" in value_data
                    assert "stack_trace_ids" in value_data
                    assert isinstance(value_data["count"], int)
                elif isinstance(parsed, dict):
                    found_dict = True
                    # Verify the count structure is correct
                    assert "count" in value_data
                    assert "stack_trace_ids" in value_data
                    assert isinstance(value_data["count"], int)
            except (json.JSONDecodeError, ValueError):
                # Not JSON, skip
                pass

    # Verify that we found at least one list and one dict value
    # This confirms that complex (unhashable) values can be counted
    assert found_list, (
        "Should find at least one list value in counts - verifies unhashable values work"
    )
    assert found_dict, (
        "Should find at least one dict value in counts - verifies unhashable values work"
    )
