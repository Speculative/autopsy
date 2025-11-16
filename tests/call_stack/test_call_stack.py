"""Test call stack introspection functionality."""

from autopsy import call_stack


def test_basic_caller():
    """Test basic caller property."""

    def test_function():
        cs = call_stack()
        caller = cs.caller.value
        # The caller is test_basic_caller (who called test_function)
        assert (
            caller.function == "test_basic_caller"
        ), f"Expected 'test_basic_caller', got '{caller.function}'"
        # Validate function reference
        assert caller.func is not None, "Function reference should not be None"
        assert (
            caller.func is test_basic_caller
        ), "Function reference should match test_basic_caller"
        return caller

    caller = test_function()
    assert caller.filename.endswith(
        "test_call_stack.py"
    ), f"Expected test file, got {caller.filename}"


def test_nested_caller():
    """Test caller in nested function calls."""

    def inner():
        cs = call_stack()
        return cs.caller

    def middle():
        return inner()

    def outer():
        return middle()

    caller = outer().value
    # The caller is 'middle' (who called inner())
    assert caller.function == "middle", f"Expected 'middle', got '{caller.function}'"
    # These are module-level nested functions (defined in test function scope),
    # so they should have stable references within the test scope
    assert caller.func is not None, "Function reference should not be None"
    assert caller.func is middle, "Function reference should match middle"


def test_call_stack_omits_autopsy():
    """Test that call_stack() omits its own frames."""

    def test_func():
        cs = call_stack()
        caller = cs.caller.value
        # The caller is test_call_stack_omits_autopsy (who called test_func)
        # Important: it should NOT be from autopsy package
        # Verify the caller is not from autopsy code using fully qualified name
        fully_qualified = caller.fully_qualified_name
        assert not fully_qualified.startswith(
            "autopsy."
        ), f"Caller should not be from autopsy package: {fully_qualified}"
        # Verify it's the expected test function
        assert (
            caller.function == "test_call_stack_omits_autopsy"
        ), f"Expected 'test_call_stack_omits_autopsy', got '{caller.function}'"
        return caller

    caller = test_func()
    assert caller.filename.endswith("test_call_stack.py")
    # Validate function reference
    assert caller.func is not None, "Function reference should not be None"
    assert (
        caller.func is test_call_stack_omits_autopsy
    ), "Function reference should match test_call_stack_omits_autopsy"


def test_class_method_reference():
    """Test that different instances of the same class have the same method reference."""

    class TestClass:
        def method(self):
            cs = call_stack()
            return cs.current

    instance1 = TestClass()
    instance2 = TestClass()

    current1 = instance1.method().value
    current2 = instance2.method().value
    assert (
        current1.function == "method"
    ), f"Expected 'method', got '{current1.function}'"
    assert (
        current2.function == "method"
    ), f"Expected 'method', got '{current2.function}'"

    # Validate that both instances have the same method reference
    assert current1.func is not None, "Function reference should not be None"
    assert current2.func is not None, "Function reference should not be None"
    assert (
        current1.func is current2.func
    ), "Different instances should have the same method reference"
    assert (
        current1.func is TestClass.method
    ), "Method reference should match TestClass.method"


def test_caller_variables():
    """Test retrieving variables from the caller's frame."""

    def test_function(x, y):
        z = x + y
        cs = call_stack()
        caller_vars = cs.caller.value.variables
        return caller_vars

    a = 10
    b = 20
    caller_vars = test_function(a, b)
    assert caller_vars is not None, "Caller variables should not be None"
    assert "a" in caller_vars, "Caller should have variable 'a'"
    assert "b" in caller_vars, "Caller should have variable 'b'"
    assert caller_vars["a"] == 10, f"Expected a=10, got a={caller_vars['a']}"
    assert caller_vars["b"] == 20, f"Expected b=20, got b={caller_vars['b']}"


def test_current_variables():
    """Test retrieving variables from the current frame."""

    def test_function(x, y):
        z = x + y
        w = z * 2
        cs = call_stack()
        current_vars = cs.current.value.variables
        return current_vars

    current_vars = test_function(5, 3)
    assert current_vars is not None, "Current variables should not be None"
    assert "x" in current_vars, "Current frame should have variable 'x'"
    assert "y" in current_vars, "Current frame should have variable 'y'"
    assert "z" in current_vars, "Current frame should have variable 'z'"
    assert "w" in current_vars, "Current frame should have variable 'w'"
    assert current_vars["x"] == 5, f"Expected x=5, got x={current_vars['x']}"
    assert current_vars["y"] == 3, f"Expected y=3, got y={current_vars['y']}"
    assert current_vars["z"] == 8, f"Expected z=8, got z={current_vars['z']}"
    assert current_vars["w"] == 16, f"Expected w=16, got w={current_vars['w']}"


def test_variables_further_up_stack():
    """Test retrieving variables from frames further up the call stack."""

    def inner(value):
        inner_var = value * 2
        cs = call_stack()
        # Get variables from different frames
        current = cs.current.value
        caller = cs.caller.value
        caller_caller_frame = cs.frame(2).value
        return current.variables, caller.variables, caller_caller_frame.variables

    def middle(x):
        middle_var = x + 10
        return inner(middle_var)

    def outer(y):
        outer_var = y * 3
        return middle(outer_var)

    current_vars, caller_vars, caller_caller_vars = outer(5)

    # Check current frame (inner)
    assert current_vars is not None, "Current variables should not be None"
    assert "value" in current_vars, "Inner should have variable 'value'"
    assert "inner_var" in current_vars, "Inner should have variable 'inner_var'"
    assert (
        current_vars["value"] == 25
    ), f"Expected value=25, got value={current_vars['value']}"
    assert (
        current_vars["inner_var"] == 50
    ), f"Expected inner_var=50, got inner_var={current_vars['inner_var']}"

    # Check caller frame (middle)
    assert caller_vars is not None, "Caller variables should not be None"
    assert "x" in caller_vars, "Middle should have variable 'x'"
    assert "middle_var" in caller_vars, "Middle should have variable 'middle_var'"
    assert caller_vars["x"] == 15, f"Expected x=15, got x={caller_vars['x']}"
    assert (
        caller_vars["middle_var"] == 25
    ), f"Expected middle_var=25, got middle_var={caller_vars['middle_var']}"

    # Check caller's caller frame (outer)
    assert (
        caller_caller_vars is not None
    ), "Caller's caller variables should not be None"
    assert "y" in caller_caller_vars, "Outer should have variable 'y'"
    assert "outer_var" in caller_caller_vars, "Outer should have variable 'outer_var'"
    assert (
        caller_caller_vars["y"] == 5
    ), f"Expected y=5, got y={caller_caller_vars['y']}"
    assert (
        caller_caller_vars["outer_var"] == 15
    ), f"Expected outer_var=15, got outer_var={caller_caller_vars['outer_var']}"


def test_variables_out_of_range():
    """Test that frame() returns error for out-of-range frame indices."""

    def test_function():
        cs = call_stack()
        # Try to access frames that don't exist
        negative = cs.frame(-1)
        too_large = cs.frame(100)
        return negative, too_large

    negative, too_large = test_function()
    assert negative.is_err(), "Negative frame index should return error"
    assert too_large.is_err(), "Out-of-range frame index should return error"


def test_variables_immutability():
    """Test that variable snapshots are captured when Caller is created."""

    def test_function(x):
        cs = call_stack()
        # Access current to create Caller and capture variables before modification
        vars_before_modification = cs.current.value.variables
        # Modify the variable after Caller is created
        x = x + 100
        # The snapshot should still have the original value
        return vars_before_modification

    vars_snapshot = test_function(42)
    assert vars_snapshot is not None, "Variables should not be None"
    # The snapshot should have the value when Caller was created (42), not after modification (142)
    assert (
        vars_snapshot["x"] == 42
    ), f"Expected x=42 (value when Caller created), got x={vars_snapshot['x']}"


def test_variable_exists():
    """Test retrieving an existing variable using variable()."""

    def test_function(x, y):
        z = x + y
        cs = call_stack()
        return cs.current.value

    current = test_function(10, 20)
    var_x = current.variable("x").value
    assert var_x.value == 10, f"Expected x=10, got x={var_x.value}"

    var_y = current.variable("y").value
    assert var_y.value == 20, f"Expected y=20, got y={var_y.value}"

    var_z = current.variable("z").value
    assert var_z.value == 30, f"Expected z=30, got z={var_z.value}"


def test_variable_none_value():
    """Test that variable() distinguishes between None values and missing variables."""

    def test_function(x):
        y = None
        cs = call_stack()
        return cs.current.value

    current = test_function(42)
    var_x = current.variable("x").value
    assert var_x.value == 42, f"Expected x=42, got x={var_x.value}"

    var_y = current.variable("y").value
    assert var_y.value is None, "Variable 'y' should have value None"

    var_missing_result = current.variable("nonexistent")
    assert var_missing_result.is_err(), "Variable 'nonexistent' should not exist"


def test_variable_from_caller():
    """Test retrieving variables from the caller's frame."""

    def inner(value):
        cs = call_stack()
        return cs.caller.value

    def outer(x):
        y = x * 2
        return inner(y)

    caller = outer(5)
    var_x = caller.variable("x").value
    assert var_x.value == 5, f"Expected x=5, got x={var_x.value}"

    var_y = caller.variable("y").value
    assert var_y.value == 10, f"Expected y=10, got y={var_y.value}"

    var_value_result = caller.variable("value")
    assert (
        var_value_result.is_err()
    ), "Variable 'value' should not exist in caller frame"


def test_caller_caller_chaining():
    """Test that caller.caller pattern works without creating intermediate Frame objects."""

    def inner(value):
        cs = call_stack()
        # Test caller.caller pattern - basic property access
        caller_caller = cs.caller.caller
        assert (
            caller_caller.function == "outer"
        ), f"Expected 'outer', got '{caller_caller.function}'"
        assert caller_caller.filename.endswith(
            "test_call_stack.py"
        ), f"Expected test file, got {caller_caller.filename}"

        # Test variable access from caller.caller
        var_x = cs.caller.caller.variable("x").value
        assert var_x.value == 42, f"Expected x=42, got x={var_x.value}"
        return var_x.value

    def middle(y):
        middle_var = y + 10
        return inner(middle_var)

    def outer():
        x = 42
        return middle(x)

    result = outer()
    assert result == 42, f"Expected 42, got {result}"


def test_caller_chaining_beyond_available_frames():
    """Test error propagation when chaining caller beyond available frames."""

    def inner():
        cs = call_stack()
        # Test caller chaining - chain enough times to exceed available frames
        frame_count = len(cs._frames)
        # We need to chain (frame_count + 1) times to go beyond available frames
        caller_query = cs.caller
        for _ in range(frame_count):
            caller_query = caller_query.caller

        assert caller_query.is_err(), "Chained caller query should fail"
        error = caller_query.error
        assert (
            error.message == "Frame index out of range"
        ), f"Expected 'Frame index out of range', got '{error.message}'"
        assert (
            "frame_index" in error.context
        ), "Error context should include frame_index"
        expected_frame_index = frame_count + 1
        assert (
            error.context["frame_index"] == expected_frame_index
        ), f"Expected frame_index={expected_frame_index}, got {error.context['frame_index']}"
        return caller_query

    def middle():
        return inner()

    def outer():
        return middle()

    outer()


def test_error_propagation_on_failed_query():
    """Test that accessing properties and variables on a failed query propagates errors correctly."""

    def inner():
        cs = call_stack()
        # Create a query that will definitely fail by using frame() with out-of-range index
        frame_count = len(cs._frames)
        query = cs.frame(frame_count + 10)
        assert query.is_err(), "Query should fail"

        # Accessing .value should raise ValueError
        try:
            value = query.value
            assert False, "Accessing .value should raise ValueError"
        except ValueError as e:
            assert (
                "error result" in str(e).lower()
            ), f"Expected ValueError about error result, got: {e}"
            assert "Frame index out of range" in str(
                e
            ), f"Error message should mention frame index, got: {e}"

        # Accessing properties returns a proxy that defers error propagation
        func_proxy = query.function
        assert func_proxy is not None, "Property access should return a proxy"

        # Accessing variable should return an error AutopsyResult
        var_result = query.variable("x")
        assert var_result.is_err(), "variable() should return error"
        assert (
            var_result.error.message == "Frame index out of range"
        ), f"Expected 'Frame index out of range', got '{var_result.error.message}'"

        return query, var_result

    def middle():
        return inner()

    def outer():
        return middle()

    outer()


def test_caller_chaining_with_multiple_levels():
    """Test caller chaining at multiple levels accessing different frames."""

    def level4():
        cs = call_stack()
        # Access different levels
        caller = cs.caller
        caller_caller = cs.caller.caller
        caller_caller_caller = cs.caller.caller.caller

        assert (
            caller.function == "level3"
        ), f"Expected 'level3', got '{caller.function}'"
        assert (
            caller_caller.function == "level2"
        ), f"Expected 'level2', got '{caller_caller.function}'"
        assert (
            caller_caller_caller.function == "level1"
        ), f"Expected 'level1', got '{caller_caller_caller.function}'"

        # Access variables from different levels
        var_result_3 = caller.variable("var3").value
        var_result_2 = caller_caller.variable("var2").value
        var_result_1 = caller_caller_caller.variable("var1").value

        assert var_result_3.value == 3, "var3 should be 3"
        assert var_result_2.value == 2, "var2 should be 2"
        assert var_result_1.value == 1, "var1 should be 1"

        return var_result_1.value, var_result_2.value, var_result_3.value

    def level3():
        var3 = 3
        return level4()

    def level2():
        var2 = 2
        return level3()

    def level1():
        var1 = 1
        return level2()

    v1, v2, v3 = level1()
    assert v1 == 1, f"Expected v1=1, got {v1}"
    assert v2 == 2, f"Expected v2=2, got {v2}"
    assert v3 == 3, f"Expected v3=3, got {v3}"
