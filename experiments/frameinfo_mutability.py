"""Test script to validate FrameInfo immutability."""

from autopsy import call_stack


def test_frameinfo_immutability():
    """Test whether FrameInfo captures state at inspection time or is a live reference."""

    # Test with a variable in the caller's scope
    caller_var = "initial_value"

    def test_function():
        # This function will capture the caller's frame
        cs = call_stack()
        return cs

    # First call - capture CallStack BEFORE updating caller_var
    print(f"caller_var before first call_stack(): {caller_var}")
    cs_before = test_function()

    # Update the variable
    caller_var = "updated_value"
    print(f"caller_var after update: {caller_var}")

    # Second call - capture CallStack AFTER updating caller_var
    cs_after = test_function()

    # Check what values are captured in each CallStack
    # _frames[0] is test_function (the one that called call_stack())
    # _frames[1] is this function (the caller) - that's where caller_var is
    print("\n" + "=" * 60)
    print("Checking captured values in caller's frame (_frames[1]):")

    if cs_before and len(cs_before._frames) > 1:
        caller_frame_before = cs_before._frames[1].frame
        # Check caller_var in the caller frame's locals
        if "caller_var" in caller_frame_before.f_locals:
            captured_before = caller_frame_before.f_locals["caller_var"]
            print(f"cs_before captured caller_var: {captured_before}")
        else:
            print("cs_before: caller_var not found in f_locals")
            print(f"  f_locals keys: {list(caller_frame_before.f_locals.keys())}")

    if cs_after and len(cs_after._frames) > 1:
        caller_frame_after = cs_after._frames[1].frame
        if "caller_var" in caller_frame_after.f_locals:
            captured_after = caller_frame_after.f_locals["caller_var"]
            print(f"cs_after captured caller_var: {captured_after}")
        else:
            print("cs_after: caller_var not found in f_locals")

    # Now re-check cs_before to see if it shows the updated value
    print("\n" + "=" * 60)
    print("Re-checking cs_before after caller_var update:")
    if cs_before and len(cs_before._frames) > 1:
        caller_frame_recheck = cs_before._frames[1].frame
        if "caller_var" in caller_frame_recheck.f_locals:
            recheck_value = caller_frame_recheck.f_locals["caller_var"]
            print(f"cs_before caller_var on recheck: {recheck_value}")

            if recheck_value == "initial_value":
                print(
                    "\n[PASS] FrameInfo appears IMMUTABLE - captured value didn't change"
                )
                print("  The frame captured the variable value at inspection time")
            elif recheck_value == "updated_value":
                print("\n[FAIL] FrameInfo appears MUTABLE - captured value changed")
                print("  The frame contains a live reference to the variable")
            else:
                print(f"\n? Unexpected value: {recheck_value}")
        else:
            print("caller_var not found in f_locals on recheck")

    # Also test modifying the frame's locals directly
    print("\n" + "=" * 60)
    print("Testing direct modification of frame.f_locals:")
    if cs_before and len(cs_before._frames) > 1:
        caller_frame = cs_before._frames[1].frame
        original_value = caller_frame.f_locals.get("caller_var", "NOT FOUND")
        print(f"Original value in frame: {original_value}")

        # Modify it
        caller_frame.f_locals["caller_var"] = "modified_directly"
        modified_value = caller_frame.f_locals.get("caller_var")
        print(f"After modifying frame.f_locals['caller_var']: {modified_value}")

        # Check if this affects the actual variable
        print(f"Actual caller_var value: {caller_var}")
        if caller_var == "modified_directly":
            print(
                "  -> Modifying frame.f_locals affected the actual variable (live reference)"
            )
        else:
            print("  -> Modifying frame.f_locals did NOT affect the actual variable")

    print("\n" + "=" * 60)
    print("SUMMARY:")
    print("FrameInfo is a named tuple (immutable tuple structure)")
    print("BUT it contains a reference to a frame object (mutable)")
    print("The frame object provides live access to execution state")
    print("Once a function returns, accessing its frame may give undefined behavior")
    print("\nKey finding: FrameInfo.frame is a LIVE REFERENCE, not a snapshot")


if __name__ == "__main__":
    test_frameinfo_immutability()
