"""Test call stack introspection functionality."""

from autopsy import call_stack


def test_basic_caller():
    """Test basic caller property."""

    def test_function():
        cs = call_stack()
        caller_result = cs.caller
        assert caller_result.is_ok(), "Caller should be ok"
        caller = caller_result.value
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

    caller_result = outer()
    assert caller_result.is_ok(), "Caller should be ok"
    caller = caller_result.value
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
        caller_result = cs.caller
        # The caller is test_call_stack_omits_autopsy (who called test_func)
        # Important: it should NOT be from autopsy package
        assert caller_result.is_ok(), "Caller should be ok"
        caller = caller_result.value
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

    current1_result = instance1.method()
    current2_result = instance2.method()

    assert current1_result.is_ok(), "Current1 should be ok"
    assert current2_result.is_ok(), "Current2 should be ok"
    current1 = current1_result.value
    current2 = current2_result.value
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
        caller_result = cs.caller
        assert caller_result.is_ok(), "Caller should be ok"
        caller = caller_result.value
        caller_vars = caller.variables
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
        current_result = cs.current
        assert current_result.is_ok(), "Current should be ok"
        current = current_result.value
        current_vars = current.variables
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
        current_result = cs.current
        assert current_result.is_ok(), "Current should be ok"
        current = current_result.value
        caller_result = cs.caller
        assert caller_result.is_ok(), "Caller should be ok"
        caller = caller_result.value
        caller_caller_frame_result = cs.frame(2)
        assert caller_caller_frame_result.is_ok(), "Caller's caller frame should be ok"
        caller_caller_frame = caller_caller_frame_result.value
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
        current_result = cs.current
        assert current_result.is_ok(), "Current should be ok"
        current = current_result.value
        vars_before_modification = current.variables
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
        current_result = cs.current
        assert current_result.is_ok(), "Current should be ok"
        return current_result.value

    current = test_function(10, 20)
    var_x_result = current.variable("x")
    assert var_x_result.is_ok(), "Variable 'x' should exist"
    var_x = var_x_result.value
    assert var_x.value == 10, f"Expected x=10, got x={var_x.value}"

    var_y_result = current.variable("y")
    assert var_y_result.is_ok(), "Variable 'y' should exist"
    var_y = var_y_result.value
    assert var_y.value == 20, f"Expected y=20, got y={var_y.value}"

    var_z_result = current.variable("z")
    assert var_z_result.is_ok(), "Variable 'z' should exist"
    var_z = var_z_result.value
    assert var_z.value == 30, f"Expected z=30, got z={var_z.value}"


def test_variable_none_value():
    """Test that variable() distinguishes between None values and missing variables."""

    def test_function(x):
        y = None
        cs = call_stack()
        current_result = cs.current
        assert current_result.is_ok(), "Current should be ok"
        return current_result.value

    current = test_function(42)
    var_x_result = current.variable("x")
    assert var_x_result.is_ok(), "Variable 'x' should exist"
    var_x = var_x_result.value
    assert var_x.value == 42, f"Expected x=42, got x={var_x.value}"

    var_y_result = current.variable("y")
    assert (
        var_y_result.is_ok()
    ), "Variable 'y' should exist even though its value is None"
    var_y = var_y_result.value
    assert var_y.value is None, "Variable 'y' should have value None"

    var_missing_result = current.variable("nonexistent")
    assert var_missing_result.is_err(), "Variable 'nonexistent' should not exist"


def test_variable_from_caller():
    """Test retrieving variables from the caller's frame."""

    def inner(value):
        cs = call_stack()
        caller_result = cs.caller
        assert caller_result.is_ok(), "Caller should be ok"
        return caller_result.value

    def outer(x):
        y = x * 2
        return inner(y)

    caller = outer(5)
    var_x_result = caller.variable("x")
    assert var_x_result.is_ok(), "Variable 'x' should exist in caller frame"
    var_x = var_x_result.value
    assert var_x.value == 5, f"Expected x=5, got x={var_x.value}"

    var_y_result = caller.variable("y")
    assert var_y_result.is_ok(), "Variable 'y' should exist in caller frame"
    var_y = var_y_result.value
    assert var_y.value == 10, f"Expected y=10, got y={var_y.value}"

    var_value_result = caller.variable("value")
    assert (
        var_value_result.is_err()
    ), "Variable 'value' should not exist in caller frame"
