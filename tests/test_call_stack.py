"""Test call stack introspection functionality."""
from autopsy import call_stack


def test_basic_caller():
    """Test basic caller property."""
    def test_function():
        cs = call_stack()
        caller = cs.caller
        assert caller is not None, "Caller should not be None"
        # The caller is test_basic_caller (who called test_function)
        assert caller.function == "test_basic_caller", f"Expected 'test_basic_caller', got '{caller.function}'"
        return caller
    
    caller = test_function()
    assert caller.filename.endswith('test_call_stack.py'), f"Expected test file, got {caller.filename}"


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
    import os
    from autopsy.call_stack import CallStack
    
    def test_func():
        cs = call_stack()
        caller = cs.caller
        # The caller is test_call_stack_omits_autopsy (who called test_func)
        # Important: it should NOT be call_stack or CallStack.__init__
        assert caller is not None, "Caller should not be None"
        assert caller.function == "test_call_stack_omits_autopsy", \
            f"Expected 'test_call_stack_omits_autopsy', got '{caller.function}'"
        # Verify it's not from autopsy package directory
        autopsy_path = CallStack._autopsy_module_path
        caller_path = os.path.abspath(caller.filename)
        assert not caller_path.startswith(autopsy_path), \
            f"Caller should not be from autopsy package: {caller.filename}"
        return caller
    
    caller = test_func()
    assert caller.filename.endswith('test_call_stack.py')


if __name__ == "__main__":
    test_basic_caller()
    test_nested_caller()
    test_call_stack_omits_autopsy()
    print("All call stack tests passed!")

