# Purpose: Determine whether nested functions defined inside a function create new
# function objects on each call, and whether call_stack can correctly retrieve
# function references for these nested functions.
#
# Conclusion: Nested functions do create new function objects on each call, and
# call_stack correctly retrieves the function reference that matches the specific
# function object created during that call.

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

caller1_result = call_stack_1.caller
caller2_result = call_stack_2.caller

if caller1_result.is_ok() and caller2_result.is_ok():
    caller1 = caller1_result.value
    caller2 = caller2_result.value

    print(f"call_stack_1.caller.func: {caller1.func}")
    print(f"intermediate_func_1: {intermediate_func_1}")
    print(f"call_stack_2.caller.func: {caller2.func}")
    print(f"intermediate_func_2: {intermediate_func_2}")

    print(
        f"\ncall_stack_1.caller.func is intermediate_func_1: {caller1.func is intermediate_func_1}"
    )
    print(
        f"call_stack_2.caller.func is intermediate_func_2: {caller2.func is intermediate_func_2}"
    )
    print(
        f"call_stack_1.caller.func is call_stack_2.caller.func: {caller1.func is caller2.func}"
    )

    # Validate that each call creates a new function object
    if caller1.func is not None and caller2.func is not None:
        if caller1.func is intermediate_func_1:
            print(
                "\n[PASS] First call's function reference matches stored reference (as expected)"
            )
        else:
            print(
                "\n[FAIL] First call's function reference does NOT match stored reference"
            )

        if caller2.func is intermediate_func_2:
            print(
                "[PASS] Second call's function reference matches stored reference (as expected)"
            )
        else:
            print(
                "[FAIL] Second call's function reference does NOT match stored reference"
            )

        if caller1.func is not caller2.func:
            print(
                "[PASS] Different calls create different function objects (as expected - nested functions create new objects)"
            )
        else:
            print("[FAIL] Different calls create the same function object (UNEXPECTED)")
    else:
        print(
            "[INFO] Function references are None (nested functions not accessible - current limitation)"
        )
else:
    print("[INFO] Caller results are errors (no caller available)")
