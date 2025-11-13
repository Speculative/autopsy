"""Validate that nested functions create new function objects on each call."""

from autopsy import call_stack

intermediate_func_1 = None
intermediate_func_2 = None


def top_level():
    def intermediate():
        def thing_to_validate():
            return call_stack()

        return thing_to_validate()

    return intermediate(), intermediate


# Test
print("Testing nested function references...")
call_stack_1, intermediate_func_1 = top_level()
call_stack_2, intermediate_func_2 = top_level()

print(f"call_stack_1.caller.func: {call_stack_1.caller.func}")
print(f"intermediate_func_1: {intermediate_func_1}")
print(f"call_stack_2.caller.func: {call_stack_2.caller.func}")
print(f"intermediate_func_2: {intermediate_func_2}")

print(
    f"\ncall_stack_1.caller.func is intermediate_func_1: {call_stack_1.caller.func is intermediate_func_1}"
)
print(
    f"call_stack_2.caller.func is intermediate_func_2: {call_stack_2.caller.func is intermediate_func_2}"
)
print(
    f"call_stack_1.caller.func is call_stack_2.caller.func: {call_stack_1.caller.func is call_stack_2.caller.func}"
)

# Validate that each call creates a new function object
if call_stack_1.caller.func is not None and call_stack_2.caller.func is not None:
    if call_stack_1.caller.func is intermediate_func_1:
        print(
            "\n[PASS] First call's function reference matches stored reference (as expected)"
        )
    else:
        print(
            "\n[FAIL] First call's function reference does NOT match stored reference"
        )

    if call_stack_2.caller.func is intermediate_func_2:
        print(
            "[PASS] Second call's function reference matches stored reference (as expected)"
        )
    else:
        print("[FAIL] Second call's function reference does NOT match stored reference")

    if call_stack_1.caller.func is not call_stack_2.caller.func:
        print(
            "[PASS] Different calls create different function objects (as expected - nested functions create new objects)"
        )
    else:
        print("[FAIL] Different calls create the same function object (UNEXPECTED)")
else:
    print(
        "[INFO] Function references are None (nested functions not accessible - current limitation)"
    )
