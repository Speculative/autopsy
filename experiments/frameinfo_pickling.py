"""Test script to check if FrameInfo objects can be pickled."""

import inspect
import pickle


def test_frameinfo_pickling():
    """Test whether FrameInfo objects can be pickled and if pickling preserves frame data."""

    def test_function(x, y):
        z = x + y
        # Capture the current stack
        stack = inspect.stack()
        # Get the frame info for the current function
        current_frame_info = stack[0]
        # Get the frame info for the caller
        caller_frame_info = stack[1] if len(stack) > 1 else None
        return current_frame_info, caller_frame_info

    print("=" * 60)
    print("Testing FrameInfo pickling")
    print("=" * 60)

    # Call the function to get FrameInfo objects
    a = 10
    b = 20
    current_frame_info, caller_frame_info = test_function(a, b)

    # Test 1: Can we pickle FrameInfo itself?
    print("\n[Test 1] Attempting to pickle FrameInfo object...")
    try:
        pickled_frame_info = pickle.dumps(current_frame_info)
        print("  ✓ FrameInfo can be pickled")
        unpickled_frame_info = pickle.loads(pickled_frame_info)
        print("  ✓ FrameInfo can be unpickled")
        print(f"  FrameInfo attributes: {current_frame_info._fields}")
        print(f"    filename: {current_frame_info.filename}")
        print(f"    lineno: {current_frame_info.lineno}")
        print(f"    function: {current_frame_info.function}")
        print(f"    code_context: {current_frame_info.code_context}")
        print(f"    index: {current_frame_info.index}")
    except Exception as e:
        print(f"  ✗ Failed to pickle FrameInfo: {e}")
        print(f"    Error type: {type(e).__name__}")

    # Test 2: Can we pickle the frame object inside FrameInfo?
    print("\n[Test 2] Attempting to pickle frame object (frame_info.frame)...")
    try:
        frame = current_frame_info.frame
        print(f"  Frame type: {type(frame)}")
        print(f"  Frame locals: {list(frame.f_locals.keys())}")
        pickled_frame = pickle.dumps(frame)
        print("  ✓ Frame object can be pickled")
        unpickled_frame = pickle.loads(pickled_frame)
        print("  ✓ Frame object can be unpickled")
        print(f"  Unpickled frame locals: {list(unpickled_frame.f_locals.keys())}")
    except Exception as e:
        print(f"  ✗ Failed to pickle frame object: {e}")
        print(f"    Error type: {type(e).__name__}")

    # Test 3: Can we pickle f_locals directly?
    print("\n[Test 3] Attempting to pickle f_locals dictionary...")
    try:
        frame = current_frame_info.frame
        locals_dict = frame.f_locals
        print(f"  f_locals: {locals_dict}")
        pickled_locals = pickle.dumps(locals_dict)
        print("  ✓ f_locals can be pickled")
        unpickled_locals = pickle.loads(pickled_locals)
        print("  ✓ f_locals can be unpickled")
        print(f"  Unpickled f_locals: {unpickled_locals}")
        print(f"  Values match: {locals_dict == unpickled_locals}")
    except Exception as e:
        print(f"  ✗ Failed to pickle f_locals: {e}")
        print(f"    Error type: {type(e).__name__}")

    # Test 4: Can we pickle a copy of f_locals?
    print("\n[Test 4] Attempting to pickle a copy of f_locals...")
    try:
        frame = current_frame_info.frame
        locals_copy = dict(frame.f_locals)
        print(f"  f_locals copy: {locals_copy}")
        pickled_copy = pickle.dumps(locals_copy)
        print("  ✓ f_locals copy can be pickled")
        unpickled_copy = pickle.loads(pickled_copy)
        print("  ✓ f_locals copy can be unpickled")
        print(f"  Unpickled copy: {unpickled_copy}")
        print(f"  Values match: {locals_copy == unpickled_copy}")
    except Exception as e:
        print(f"  ✗ Failed to pickle f_locals copy: {e}")
        print(f"    Error type: {type(e).__name__}")

    # Test 5: Test with caller frame info
    if caller_frame_info:
        print("\n[Test 5] Testing pickling of caller FrameInfo...")
        try:
            pickled_caller = pickle.dumps(caller_frame_info)
            print("  ✓ Caller FrameInfo can be pickled")
            unpickled_caller = pickle.loads(pickled_caller)
            print("  ✓ Caller FrameInfo can be unpickled")
            print(f"    Caller function: {unpickled_caller.function}")
            print(f"    Caller filename: {unpickled_caller.filename}")

            # Try to access caller's f_locals
            caller_frame = unpickled_caller.frame
            print(f"    Caller frame locals: {list(caller_frame.f_locals.keys())}")
            if "a" in caller_frame.f_locals:
                print(f"    Caller variable 'a': {caller_frame.f_locals['a']}")
        except Exception as e:
            print(f"  ✗ Failed to pickle caller FrameInfo: {e}")
            print(f"    Error type: {type(e).__name__}")

    print("\n" + "=" * 60)
    print("SUMMARY:")
    print("=" * 60)
    print("Testing whether FrameInfo objects can be pickled as a way to")
    print("create immutable snapshots of frame information.")


if __name__ == "__main__":
    test_frameinfo_pickling()
