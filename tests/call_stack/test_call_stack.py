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


if __name__ == "__main__":
    test_basic_caller()
    test_nested_caller()
    test_call_stack_omits_autopsy()
    print("All call stack tests passed!")
