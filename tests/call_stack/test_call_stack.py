"""Test call stack introspection functionality."""

from autopsy import call_stack


def test_basic_caller():
    """Test basic caller property."""

    def test_function():
        cs = call_stack()
        caller = cs.caller
        assert caller is not None, "Caller should not be None"
        # The caller is test_basic_caller (who called test_function)
        assert caller.function == "test_basic_caller", (
            f"Expected 'test_basic_caller', got '{caller.function}'"
        )
        # Validate function reference
        assert caller.func is not None, "Function reference should not be None"
        assert caller.func is test_basic_caller, (
            "Function reference should match test_basic_caller"
        )
        return caller

    caller = test_function()
    assert caller.filename.endswith("test_call_stack.py"), (
        f"Expected test file, got {caller.filename}"
    )


def test_nested_caller():
    """Test caller in nested function calls."""

    def inner():
        cs = call_stack()
        return cs.caller

    def middle():
        return inner()

    def outer():
        return middle()

    caller = outer()
    assert caller is not None, "Caller should not be None"
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
        caller = cs.caller
        # The caller is test_call_stack_omits_autopsy (who called test_func)
        # Important: it should NOT be from autopsy package
        assert caller is not None, "Caller should not be None"
        # Verify the caller is not from autopsy code using fully qualified name
        fully_qualified = caller.fully_qualified_name
        assert not fully_qualified.startswith("autopsy."), (
            f"Caller should not be from autopsy package: {fully_qualified}"
        )
        # Verify it's the expected test function
        assert caller.function == "test_call_stack_omits_autopsy", (
            f"Expected 'test_call_stack_omits_autopsy', got '{caller.function}'"
        )
        return caller

    caller = test_func()
    assert caller.filename.endswith("test_call_stack.py")
    # Validate function reference
    assert caller.func is not None, "Function reference should not be None"
    assert caller.func is test_call_stack_omits_autopsy, (
        "Function reference should match test_call_stack_omits_autopsy"
    )


def test_class_method_reference():
    """Test that different instances of the same class have the same method reference."""

    class TestClass:
        def method(self):
            cs = call_stack()
            return cs.current

    instance1 = TestClass()
    instance2 = TestClass()

    current1 = instance1.method()
    current2 = instance2.method()

    assert current1 is not None, "Current1 should not be None"
    assert current2 is not None, "Current2 should not be None"
    assert current1.function == "method", (
        f"Expected 'method', got '{current1.function}'"
    )
    assert current2.function == "method", (
        f"Expected 'method', got '{current2.function}'"
    )

    # Validate that both instances have the same method reference
    assert current1.func is not None, "Function reference should not be None"
    assert current2.func is not None, "Function reference should not be None"
    assert current1.func is current2.func, (
        "Different instances should have the same method reference"
    )
    assert current1.func is TestClass.method, (
        "Method reference should match TestClass.method"
    )
