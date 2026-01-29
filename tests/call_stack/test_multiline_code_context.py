"""Test that multi-line call sites are fully captured in code_context."""

import autopsy


def test_single_line_code_context():
    """Test that single-line calls are captured correctly."""
    autopsy.init(clear=True, warn=False)

    x = 10
    autopsy.log(x)

    report = autopsy.get_report()
    json_data = report.to_json()

    # Find the stack trace for this call
    call_sites = json_data['call_sites']
    assert len(call_sites) == 1

    value_group = call_sites[0]['value_groups'][0]
    assert 'stack_trace_id' in value_group

    stack_trace_id = value_group['stack_trace_id']
    trace = json_data['stack_traces'][stack_trace_id]

    # Find our frame in the trace
    frame = None
    for f in trace['frames']:
        if f['function_name'] == 'test_single_line_code_context':
            frame = f
            break

    assert frame is not None, "Could not find test function in stack trace"

    # Check that code context contains the log call
    code_context = frame['code_context']
    assert 'autopsy.log(x)' in code_context
    # For single-line calls, there should be no newlines
    assert '\n' not in code_context or code_context.count('\n') == 0


def test_multiline_code_context():
    """Test that multi-line calls are fully captured in code_context."""
    autopsy.init(clear=True, warn=False)

    x = 10
    y = 20
    z = 30

    # Multi-line call
    autopsy.log(
        x,
        y,
        z
    )

    report = autopsy.get_report()
    json_data = report.to_json()

    # Find the stack trace for this call
    call_sites = json_data['call_sites']
    assert len(call_sites) == 1

    value_group = call_sites[0]['value_groups'][0]
    assert 'stack_trace_id' in value_group

    stack_trace_id = value_group['stack_trace_id']
    trace = json_data['stack_traces'][stack_trace_id]

    # Find our frame in the trace
    frame = None
    for f in trace['frames']:
        if f['function_name'] == 'test_multiline_code_context':
            frame = f
            break

    assert frame is not None, "Could not find test function in stack trace"

    # Check that code context contains the full multi-line call
    code_context = frame['code_context']

    # The context should contain all parts of the call
    assert 'autopsy.log(' in code_context
    assert 'x,' in code_context
    assert 'y,' in code_context
    assert 'z' in code_context
    assert ')' in code_context

    # There should be multiple lines
    lines = code_context.split('\n')
    assert len(lines) > 1, f"Expected multiple lines but got: {code_context!r}"


def test_multiline_with_complex_args():
    """Test multi-line calls with complex argument expressions."""
    autopsy.init(clear=True, warn=False)

    data = {'key': 'value'}
    result = [1, 2, 3]

    # Multi-line call with complex expressions
    autopsy.log(
        data['key'],
        len(result),
        result[0] + result[1]
    )

    report = autopsy.get_report()
    json_data = report.to_json()

    call_sites = json_data['call_sites']
    assert len(call_sites) == 1

    value_group = call_sites[0]['value_groups'][0]
    stack_trace_id = value_group['stack_trace_id']
    trace = json_data['stack_traces'][stack_trace_id]

    # Find our frame
    frame = None
    for f in trace['frames']:
        if f['function_name'] == 'test_multiline_with_complex_args':
            frame = f
            break

    assert frame is not None

    code_context = frame['code_context']

    # Verify all parts are captured
    assert 'autopsy.log(' in code_context
    assert "data['key']" in code_context
    assert 'len(result)' in code_context
    assert 'result[0] + result[1]' in code_context
    assert ')' in code_context

    # Should be multi-line
    lines = code_context.split('\n')
    assert len(lines) > 1
