# Purpose: Determine whether FrameInfo objects remain accessible after a function
# returns, and what variable values they contain (initial values, final values, or
# something else).
#
# Conclusion: FrameInfo.frame remains accessible after function return and contains
# the final variable values from when the function exited, not the values from when
# FrameInfo was captured.

import inspect


def test_frameinfo_after_return():
    """Test whether FrameInfo continues to exist and contain valid values after function return."""

    captured_frame_info = None
    captured_variables = None

    def test_function(x, y):
        """A function that captures its own FrameInfo and returns."""
        nonlocal captured_frame_info, captured_variables

        z = x + y
        w = z * 2

        # Capture FrameInfo for this function's frame
        stack = inspect.stack()
        # stack[0] is this function (test_function)
        captured_frame_info = stack[0]

        # Capture variables at this point
        frame = captured_frame_info.frame
        captured_variables = dict(frame.f_locals) if frame.f_locals else {}

        print(f"Inside test_function:")
        print(f"  x = {x}, y = {y}, z = {z}, w = {w}")
        print(f"  Captured variables: {captured_variables}")
        print(f"  FrameInfo: {captured_frame_info}")

        # Modify variables before returning
        x = x + 100
        y = y + 200
        z = z + 300
        w = w + 400

        print(f"  After modification: x = {x}, y = {y}, z = {z}, w = {w}")

        # Return - function exits here
        return x + y

    print("=" * 60)
    print("Testing FrameInfo behavior after function return")
    print("=" * 60)

    # Call the function
    result = test_function(10, 20)
    print(f"\nFunction returned: {result}")

    # Now check FrameInfo after function has returned
    print("\n" + "=" * 60)
    print("After function return:")
    print("=" * 60)

    if captured_frame_info is None:
        print("ERROR: FrameInfo was not captured!")
        return

    print(f"FrameInfo still exists: {captured_frame_info}")
    print(f"FrameInfo.filename: {captured_frame_info.filename}")
    print(f"FrameInfo.lineno: {captured_frame_info.lineno}")
    print(f"FrameInfo.function: {captured_frame_info.function}")

    # Try to access the frame object
    print("\n" + "-" * 60)
    print("Accessing frame object:")
    print("-" * 60)

    try:
        frame = captured_frame_info.frame
        print(f"Frame object still exists: {frame}")
        print(f"Frame type: {type(frame)}")

        # Try to access frame locals
        print("\nAccessing frame.f_locals:")
        try:
            frame_locals = frame.f_locals
            print(f"  frame.f_locals exists: {frame_locals}")
            print(f"  frame.f_locals type: {type(frame_locals)}")
            print(f"  frame.f_locals contents: {frame_locals}")

            # Check individual variables
            if "x" in frame_locals:
                print(f"  x in frame_locals: {frame_locals['x']}")
            else:
                print("  x NOT in frame_locals")

            if "y" in frame_locals:
                print(f"  y in frame_locals: {frame_locals['y']}")
            else:
                print("  y NOT in frame_locals")

            if "z" in frame_locals:
                print(f"  z in frame_locals: {frame_locals['z']}")
            else:
                print("  z NOT in frame_locals")

            if "w" in frame_locals:
                print(f"  w in frame_locals: {frame_locals['w']}")
            else:
                print("  w NOT in frame_locals")

        except Exception as e:
            print(f"  ERROR accessing frame.f_locals: {e}")
            print(f"  Error type: {type(e).__name__}")

        # Try to access frame globals
        print("\nAccessing frame.f_globals:")
        try:
            frame_globals = frame.f_globals
            print(f"  frame.f_globals exists: {frame_globals}")
            print(f"  frame.f_globals type: {type(frame_globals)}")
        except Exception as e:
            print(f"  ERROR accessing frame.f_globals: {e}")
            print(f"  Error type: {type(e).__name__}")

    except Exception as e:
        print(f"ERROR accessing frame: {e}")
        print(f"Error type: {type(e).__name__}")

    # Compare with captured variables
    print("\n" + "-" * 60)
    print("Comparing with captured variables:")
    print("-" * 60)
    print(f"Captured variables at capture time: {captured_variables}")

    try:
        frame = captured_frame_info.frame
        current_locals = dict(frame.f_locals) if frame.f_locals else {}
        print(f"Current frame.f_locals: {current_locals}")

        if captured_variables == current_locals:
            print("\n✓ Variables match - FrameInfo contains values from capture time")
        else:
            print("\n✗ Variables differ:")
            print(f"  Captured: {captured_variables}")
            print(f"  Current:  {current_locals}")

            # Check if current values are the "last values" (after modifications)
            if "x" in current_locals and current_locals.get("x") == 110:  # 10 + 100
                print(
                    "\n  → Current values appear to be LAST values (after modifications)"
                )
            elif "x" in current_locals and current_locals.get("x") == 10:
                print(
                    "\n  → Current values appear to be INITIAL values (before modifications)"
                )

    except Exception as e:
        print(f"ERROR comparing variables: {e}")

    print("\n" + "=" * 60)
    print("SUMMARY:")
    print("=" * 60)
    print("Testing whether FrameInfo.frame continues to be accessible")
    print("after the function has returned, and what values it contains.")


if __name__ == "__main__":
    test_frameinfo_after_return()
