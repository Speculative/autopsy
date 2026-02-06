"""Test serialization of special float values (Infinity, -Infinity, NaN)."""

import json
import math

from autopsy.report import Report, ReportConfiguration


def test_infinity_in_log():
    """Test that infinity values can be logged and serialized."""
    report = Report(ReportConfiguration(auto_stack_trace=False))

    # Log infinity values
    report.log(float('inf'), float('-inf'), float('nan'))

    # Convert to JSON
    json_data = report.to_json()

    # Serialize to JSON string (should not raise)
    json_str = json.dumps(json_data, allow_nan=False)

    # Parse back (should be valid JSON)
    parsed = json.loads(json_str)

    # Check that values are serialized as strings
    assert len(parsed['call_sites']) == 1
    call_site = parsed['call_sites'][0]
    assert len(call_site['value_groups']) == 1
    value_group = call_site['value_groups'][0]
    assert len(value_group['values']) == 3

    # Check serialized values
    assert value_group['values'][0]['value'] == 'Infinity'
    assert value_group['values'][1]['value'] == '-Infinity'
    assert value_group['values'][2]['value'] == 'NaN'


def test_infinity_in_hist():
    """Test that infinity values in histograms are serialized correctly."""
    report = Report(ReportConfiguration(auto_stack_trace=False))

    # Add histogram values including infinity (all on same line via loop)
    for val in [float('inf'), float('-inf'), float('nan'), 42.5]:
        report.hist(val)

    # Convert to JSON
    json_data = report.to_json()

    # Serialize to JSON string (should not raise)
    json_str = json.dumps(json_data, allow_nan=False)

    # Parse back
    parsed = json.loads(json_str)

    # Check histogram data (single call site since all in loop)
    assert 'dashboard' in parsed
    assert len(parsed['dashboard']['histograms']) == 1
    hist = parsed['dashboard']['histograms'][0]
    assert len(hist['values']) == 4

    # Check serialized values
    assert hist['values'][0]['value'] == 'Infinity'
    assert hist['values'][1]['value'] == '-Infinity'
    assert hist['values'][2]['value'] == 'NaN'
    assert hist['values'][3]['value'] == 42.5


def test_infinity_in_count():
    """Test that infinity values in count are serialized correctly."""
    report = Report(ReportConfiguration(auto_stack_trace=False))

    # Count different values including infinity (all on same line via loop)
    for val in [float('inf'), float('-inf'), float('nan'), float('inf')]:
        report.count(val)

    # Convert to JSON
    json_data = report.to_json()

    # Serialize to JSON string (should not raise)
    json_str = json.dumps(json_data, allow_nan=False)

    # Parse back
    parsed = json.loads(json_str)

    # Check count data (single call site since all in loop)
    assert 'dashboard' in parsed
    assert len(parsed['dashboard']['counts']) == 1
    count_entry = parsed['dashboard']['counts'][0]

    # Verify the values are serialized as strings in the keys
    value_counts = count_entry['value_counts']

    # Count of infinity should be 2
    inf_key = json.dumps("Infinity")
    assert inf_key in value_counts
    assert value_counts[inf_key]['count'] == 2

    # Count of -infinity should be 1
    neg_inf_key = json.dumps("-Infinity")
    assert neg_inf_key in value_counts
    assert value_counts[neg_inf_key]['count'] == 1

    # Count of NaN should be 1
    nan_key = json.dumps("NaN")
    assert nan_key in value_counts
    assert value_counts[nan_key]['count'] == 1


def test_nested_infinity():
    """Test that infinity values in nested structures are handled."""
    report = Report(ReportConfiguration(auto_stack_trace=False))

    # Log nested structures with infinity
    report.log([float('inf'), float('-inf'), float('nan')])
    report.log({'x': float('inf'), 'y': float('-inf'), 'z': float('nan')})

    # Convert to JSON
    json_data = report.to_json()

    # Serialize to JSON string (should not raise)
    json_str = json.dumps(json_data, allow_nan=False)

    # Parse back
    parsed = json.loads(json_str)

    # Check that nested values are serialized (2 separate call sites)
    assert len(parsed['call_sites']) == 2

    # Check list (first call site)
    list_value = parsed['call_sites'][0]['value_groups'][0]['values'][0]['value']
    assert list_value == ['Infinity', '-Infinity', 'NaN']

    # Check dict (second call site)
    dict_value = parsed['call_sites'][1]['value_groups'][0]['values'][0]['value']
    assert dict_value == {'x': 'Infinity', 'y': '-Infinity', 'z': 'NaN'}


def test_to_json_serializable():
    """Test the _to_json_serializable method directly."""
    report = Report(ReportConfiguration(auto_stack_trace=False))

    # Test individual values
    assert report._to_json_serializable(float('inf')) == 'Infinity'
    assert report._to_json_serializable(float('-inf')) == '-Infinity'
    assert report._to_json_serializable(float('nan')) == 'NaN'

    # Test in lists
    result = report._to_json_serializable([float('inf'), 1.5, float('-inf')])
    assert result == ['Infinity', 1.5, '-Infinity']

    # Test in dicts
    result = report._to_json_serializable({'a': float('inf'), 'b': float('nan')})
    assert result == {'a': 'Infinity', 'b': 'NaN'}

    # Verify all results are JSON serializable with allow_nan=False
    json.dumps(report._to_json_serializable(float('inf')), allow_nan=False)
    json.dumps(report._to_json_serializable([float('inf'), float('nan')]), allow_nan=False)
