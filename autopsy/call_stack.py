import inspect
import os
from typing import List, Optional, NamedTuple, Callable


class Caller(NamedTuple):
    """Information about a caller in the call stack."""

    module: str
    class_name: Optional[str]
    function: str
    func: Optional[Callable]
    filename: str
    lineno: int

    @property
    def fully_qualified_name(self) -> str:
        """
        Get the fully qualified name in the format 'package.ClassName.method' or 'package.function'.
        """
        if self.class_name:
            return f"{self.module}.{self.class_name}.{self.function}"
        return f"{self.module}.{self.function}"


class CallStack:
    """Call stack introspection API."""

    _frames: List[inspect.FrameInfo]

    def __init__(self, frames: List[inspect.FrameInfo]):
        """
        Initialize with a list of filtered frames.

        TODO: FrameInfo contains a live reference to the frame object (not a snapshot).
        The frame object provides mutable access to execution state, which can change
        after the function returns. We should extract all needed state from frames at
        initialization time to ensure immutability, rather than accessing frame objects
        lazily through properties.
        """
        self._frames = frames

    def _extract_caller_info(self, frame_info: inspect.FrameInfo) -> Caller:
        """Extract caller information from a frame info object."""
        frame = frame_info.frame

        # Get module name from frame globals
        module = frame.f_globals.get("__name__", "<unknown>")

        # Check if it's a method by looking for 'self' in locals
        class_name = None
        func_ref = None
        if "self" in frame.f_locals:
            self_obj = frame.f_locals["self"]
            class_name = type(self_obj).__name__
            # Get the unbound method from the class
            try:
                func_ref = getattr(type(self_obj), frame_info.function)
            except AttributeError:
                pass
        else:
            # Try to get function reference from globals first (module-level functions)
            try:
                func_ref = frame.f_globals.get(frame_info.function)
                # Verify it's actually a function and not something else with the same name
                if func_ref is not None and not callable(func_ref):
                    func_ref = None
            except (KeyError, TypeError):
                pass

            # If not found in globals, try locals (for nested functions)
            # Check current frame's locals first
            if func_ref is None:
                try:
                    func_ref = frame.f_locals.get(frame_info.function)
                    # Verify it's actually a function and not something else with the same name
                    if func_ref is not None and not callable(func_ref):
                        func_ref = None
                except (KeyError, TypeError):
                    pass

            # If still not found, check parent frame's locals (nested functions are defined there)
            if func_ref is None and frame.f_back is not None:
                try:
                    parent_frame = frame.f_back
                    func_ref = parent_frame.f_locals.get(frame_info.function)
                    # Verify it's actually a function and not something else with the same name
                    if func_ref is not None and not callable(func_ref):
                        func_ref = None
                except (KeyError, TypeError, AttributeError):
                    pass

        return Caller(
            module=module,
            class_name=class_name,
            function=frame_info.function,
            func=func_ref,
            filename=frame_info.filename,
            lineno=frame_info.lineno,
        )

    @property
    def current(self) -> Optional[Caller]:
        """
        Get information about the function that called call_stack().

        Returns:
            Caller object with module, class name (if method), function name, file path, and line number,
            or None if no frames are available
        """
        if len(self._frames) < 1:
            return None

        # _frames[0] is the function that called call_stack()
        return self._extract_caller_info(self._frames[0])

    @property
    def caller(self) -> Optional[Caller]:
        """
        Get information about the immediate caller from the user function's perspective.

        Returns:
            Caller object with module, class name (if method), function name, file path, and line number,
            or None if no caller is available
        """
        if len(self._frames) < 2:
            # Need at least 2 frames: the function that called call_stack(), and its caller
            return None

        # After filtering out autopsy frames:
        # _frames[0] is the function that called call_stack()
        # _frames[1] is the caller of that function (what we want)
        return self._extract_caller_info(self._frames[1])


def call_stack() -> CallStack:
    """Create a CallStack instance for the current call site."""
    # Compute the autopsy package path
    autopsy_module_path = os.path.dirname(os.path.abspath(__file__))

    # Capture the current call stack, excluding autopsy's own frames
    stack = inspect.stack()
    # Filter out frames from autopsy module
    frames = []
    for frame_info in stack:
        # Skip frames from autopsy package directory
        frame_path = os.path.abspath(frame_info.filename)
        is_autopsy_package = frame_path.startswith(autopsy_module_path)

        if not is_autopsy_package:
            frames.append(frame_info)

    return CallStack(frames)
