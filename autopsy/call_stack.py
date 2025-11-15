import inspect
import os
from typing import Any, Callable, Dict, List, Optional


class Variable:
    """Result type for variable lookups that distinguishes missing variables from None values."""

    def __init__(self, exists: bool, value: Any = None):
        """
        Initialize a Variable result.

        Args:
            exists: Whether the variable exists in the frame
            value: The variable's value (only meaningful if exists is True)
        """
        self.exists = exists
        self.value = value

    def __repr__(self) -> str:
        if self.exists:
            return f"Variable({self.value!r})"
        return "UndefinedVariable"


class Frame:
    """Information about a frame in the call stack."""

    def __init__(self, frame_info: inspect.FrameInfo):
        """
        Initialize a Frame with a FrameInfo.

        Args:
            frame_info: The FrameInfo object for this frame
        """
        self.frame_info = frame_info

        # Extract picklable data from FrameInfo for serialization
        # These are computed eagerly so Frame can be pickled
        frame = frame_info.frame
        self.module = frame.f_globals.get("__name__", "<unknown>")
        self.filename = frame_info.filename
        self.lineno = frame_info.lineno
        self.function = frame_info.function

        # Extract class_name if this is a method
        self.class_name = None
        if "self" in frame.f_locals:
            self_obj = frame.f_locals["self"]
            self.class_name = type(self_obj).__name__

    @property
    def func(self) -> Optional[Callable]:
        """Get the function reference if available."""
        # If frame_info is None (e.g., after unpickling), we can't get the function reference
        if self.frame_info is None:
            return None

        frame = self.frame_info.frame

        # Check if it's a method by looking for 'self' in locals
        if "self" in frame.f_locals:
            self_obj = frame.f_locals["self"]
            # Get the unbound method from the class
            try:
                return getattr(type(self_obj), self.function)
            except AttributeError:
                pass
        else:
            # Try to get function reference from globals first (module-level functions)
            try:
                func_ref = frame.f_globals.get(self.function)
                # Verify it's actually a function and not something else with the same name
                if func_ref is not None and callable(func_ref):
                    return func_ref
            except (KeyError, TypeError):
                pass

            # If not found in globals, try locals (for nested functions)
            # Check current frame's locals first
            try:
                func_ref = frame.f_locals.get(self.function)
                # Verify it's actually a function and not something else with the same name
                if func_ref is not None and callable(func_ref):
                    return func_ref
            except (KeyError, TypeError):
                pass

            # If still not found, check parent frame's locals (nested functions are defined there)
            if frame.f_back is not None:
                try:
                    parent_frame = frame.f_back
                    func_ref = parent_frame.f_locals.get(self.function)
                    # Verify it's actually a function and not something else with the same name
                    if func_ref is not None and callable(func_ref):
                        return func_ref
                except (KeyError, TypeError, AttributeError):
                    pass

        return None

    @property
    def fully_qualified_name(self) -> str:
        """
        Get the fully qualified name in the format 'package.ClassName.method' or 'package.function'.
        """
        if self.class_name:
            return f"{self.module}.{self.class_name}.{self.function}"
        return f"{self.module}.{self.function}"

    @property
    def variables(self) -> Dict[str, Any]:
        """
        Get the variables from this frame, retrieved from FrameInfo when accessed.

        Returns:
            Dictionary mapping variable names to their values
        """
        if self.frame_info is None:
            # After unpickling, return the snapshot
            return getattr(self, "_variables_snapshot", {})
        frame = self.frame_info.frame
        return dict(frame.f_locals) if frame.f_locals else {}

    def variable(self, name: str) -> Variable:
        """
        Get a specific variable's value from this frame.

        Args:
            name: The name of the variable to retrieve

        Returns:
            Variable object indicating whether the variable exists and its value.
            Use Variable.exists to check if the variable exists, and Variable.value
            to get its value (which may be None if the variable exists but is None).
        """
        vars_dict = self.variables
        if name in vars_dict:
            return Variable(exists=True, value=vars_dict[name])
        return Variable(exists=False)

    def __getstate__(self):
        """
        Return state for pickling. Excludes FrameInfo which contains unpicklable frame objects.
        Variables are captured at pickling time since FrameInfo cannot be restored.
        """
        return {
            "module": self.module,
            "class_name": self.class_name,
            "function": self.function,
            "filename": self.filename,
            "lineno": self.lineno,
            "variables": self.variables,  # Capture variables at pickling time
        }

    def __setstate__(self, state):
        """
        Restore state from pickling. FrameInfo is not restored since it can't be pickled.
        Variables are stored as a snapshot since FrameInfo cannot be restored.
        """
        self.module = state["module"]
        self.class_name = state["class_name"]
        self.function = state["function"]
        self.filename = state["filename"]
        self.lineno = state["lineno"]
        self.frame_info = None  # FrameInfo cannot be restored after unpickling
        # Store variables as a snapshot since we can't access FrameInfo after unpickling
        self._variables_snapshot = state["variables"]


class CallStack:
    """Call stack introspection API."""

    _frames: List[inspect.FrameInfo]

    def __init__(self, frames: List[inspect.FrameInfo]):
        """
        Initialize with a list of filtered frames.

        Variables are captured when Frame objects are created, ensuring immutability
        as FrameInfo contains live references to frame objects that can change after
        functions return.
        """
        self._frames = frames

    @property
    def current(self) -> Optional[Frame]:
        """
        Get information about the function that called call_stack().

        Returns:
            Frame object with module, class name (if method), function name, file path, and line number,
            or None if no frames are available
        """
        if len(self._frames) < 1:
            return None

        # _frames[0] is the function that called call_stack()
        return Frame(self._frames[0])

    @property
    def caller(self) -> Optional[Frame]:
        """
        Get information about the immediate caller from the user function's perspective.

        Returns:
            Frame object with module, class name (if method), function name, file path, and line number,
            or None if no caller is available
        """
        if len(self._frames) < 2:
            # Need at least 2 frames: the function that called call_stack(), and its caller
            return None

        # After filtering out autopsy frames:
        # _frames[0] is the function that called call_stack()
        # _frames[1] is the caller of that function (what we want)
        return Frame(self._frames[1])

    def frame(self, frame_index: int) -> Optional[Frame]:
        """
        Get information about a specific frame in the call stack.

        Args:
            frame_index: Index of the frame (0 = current, 1 = caller, 2 = caller's caller, etc.)

        Returns:
            Frame object with module, class name (if method), function name, file path, and line number,
            or None if the frame index is out of range
        """
        if frame_index < 0 or frame_index >= len(self._frames):
            return None
        return Frame(self._frames[frame_index])


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
