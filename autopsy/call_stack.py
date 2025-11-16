import inspect
import os
from typing import Any, Callable, Dict, List, Optional

from .autopsy_result import AutopsyResult, ErrorInfo, Location, _capture_error_location


class Variable:
    """Represents a variable from a frame."""

    def __init__(self, name: str, value: Any):
        """
        Initialize a Variable.

        Args:
            name: The name of the variable
            value: The variable's value
        """
        self.name = name
        self.value = value

    def __repr__(self) -> str:
        return f"Variable(name={self.name!r}, value={self.value!r})"


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
        module = frame.f_globals.get("__name__", "<unknown>")
        self.location = Location(
            filename=frame_info.filename,
            lineno=frame_info.lineno,
            function=frame_info.function,
            module=module,
        )

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
                return getattr(type(self_obj), self.location.function)
            except AttributeError:
                pass
        else:
            # Try to get function reference from globals first (module-level functions)
            try:
                func_ref = frame.f_globals.get(self.location.function)
                # Verify it's actually a function and not something else with the same name
                if func_ref is not None and callable(func_ref):
                    return func_ref
            except (KeyError, TypeError):
                pass

            # If not found in globals, try locals (for nested functions)
            # Check current frame's locals first
            try:
                func_ref = frame.f_locals.get(self.location.function)
                # Verify it's actually a function and not something else with the same name
                if func_ref is not None and callable(func_ref):
                    return func_ref
            except (KeyError, TypeError):
                pass

            # If still not found, check parent frame's locals (nested functions are defined there)
            if frame.f_back is not None:
                try:
                    parent_frame = frame.f_back
                    func_ref = parent_frame.f_locals.get(self.location.function)
                    # Verify it's actually a function and not something else with the same name
                    if func_ref is not None and callable(func_ref):
                        return func_ref
                except (KeyError, TypeError, AttributeError):
                    pass

        return None

    @property
    def filename(self) -> str:
        """Get the filename from location (backward compatibility)."""
        return self.location.filename

    @property
    def lineno(self) -> int:
        """Get the line number from location (backward compatibility)."""
        return self.location.lineno

    @property
    def function(self) -> str:
        """Get the function name from location (backward compatibility)."""
        return self.location.function

    @property
    def module(self) -> str:
        """Get the module name from location (backward compatibility)."""
        return self.location.module

    @property
    def fully_qualified_name(self) -> str:
        """
        Get the fully qualified name in the format 'package.ClassName.method' or 'package.function'.
        """
        if self.class_name:
            return f"{self.location.module}.{self.class_name}.{self.location.function}"
        return f"{self.location.module}.{self.location.function}"

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

    def variable(self, name: str) -> AutopsyResult[Variable]:
        """
        Get a specific variable's value from this frame.

        Args:
            name: The name of the variable to retrieve

        Returns:
            AutopsyResult containing Variable object with the variable's name and value,
            or an error if the variable doesn't exist in this frame.
        """
        vars_dict = self.variables
        if name in vars_dict:
            return AutopsyResult.ok(Variable(name=name, value=vars_dict[name]))

        # Variable doesn't exist - create error
        # Use the frame's location for the error location
        error_location = Location(
            filename=self.location.filename,
            lineno=self.location.lineno,
            function=self.location.function,
            module=self.location.module,
        )
        error = ErrorInfo(
            message=f"Variable '{name}' not found in frame",
            context={
                "variable_name": name,
                "available_variables": list(vars_dict.keys()),
            },
            location=error_location,
        )
        return AutopsyResult.err(error)

    def __getstate__(self):
        """
        Return state for pickling. Excludes FrameInfo which contains unpicklable frame objects.
        Variables are captured at pickling time since FrameInfo cannot be restored.
        """
        return {
            "location": self.location,
            "class_name": self.class_name,
            "variables": self.variables,  # Capture variables at pickling time
        }

    def __setstate__(self, state):
        """
        Restore state from pickling. FrameInfo is not restored since it can't be pickled.
        Variables are stored as a snapshot since FrameInfo cannot be restored.
        """
        self.location = state["location"]
        self.class_name = state["class_name"]
        self.frame_info = None  # FrameInfo cannot be restored after unpickling
        # Store variables as a snapshot since we can't access FrameInfo after unpickling
        self._variables_snapshot = state["variables"]


class CallStack:
    """Call stack introspection API."""

    _frames: List[inspect.FrameInfo]
    _autopsy_module_path: str

    def __init__(self, frames: List[inspect.FrameInfo], autopsy_module_path: str):
        """
        Initialize with a list of filtered frames.

        Variables are captured when Frame objects are created, ensuring immutability
        as FrameInfo contains live references to frame objects that can change after
        functions return.

        Args:
            frames: List of filtered FrameInfo objects
            autopsy_module_path: Path to the autopsy module directory (for error location capture)
        """
        self._frames = frames
        self._autopsy_module_path = autopsy_module_path

    @property
    def current(self) -> AutopsyResult[Frame]:
        """
        Get information about the function that called call_stack().

        Returns:
            AutopsyResult containing Frame object with module, class name (if method),
            function name, file path, and line number, or an error if no frames are available
        """
        if len(self._frames) < 1:
            location = _capture_error_location(
                self._autopsy_module_path, inspect.stack()
            )
            error = ErrorInfo(
                message="No current frame available",
                context={"available_frames": len(self._frames)},
                location=location,
            )
            return AutopsyResult.err(error)

        # _frames[0] is the function that called call_stack()
        return AutopsyResult.ok(Frame(self._frames[0]))

    @property
    def caller(self) -> AutopsyResult[Frame]:
        """
        Get information about the immediate caller from the user function's perspective.

        Returns:
            AutopsyResult containing Frame object with module, class name (if method),
            function name, file path, and line number, or an error if no caller is available
        """
        if len(self._frames) < 2:
            # Need at least 2 frames: the function that called call_stack(), and its caller
            location = _capture_error_location(
                self._autopsy_module_path, inspect.stack()
            )
            error = ErrorInfo(
                message="No caller frame available",
                context={
                    "available_frames": len(self._frames),
                    "required_frames": 2,
                },
                location=location,
            )
            return AutopsyResult.err(error)

        # After filtering out autopsy frames:
        # _frames[0] is the function that called call_stack()
        # _frames[1] is the caller of that function (what we want)
        return AutopsyResult.ok(Frame(self._frames[1]))

    def frame(self, frame_index: int) -> AutopsyResult[Frame]:
        """
        Get information about a specific frame in the call stack.

        Args:
            frame_index: Index of the frame (0 = current, 1 = caller, 2 = caller's caller, etc.)

        Returns:
            AutopsyResult containing Frame object with module, class name (if method),
            function name, file path, and line number, or an error if the frame index is out of range
        """
        if frame_index < 0 or frame_index >= len(self._frames):
            location = _capture_error_location(
                self._autopsy_module_path, inspect.stack()
            )
            valid_range = (
                (0, len(self._frames) - 1) if len(self._frames) > 0 else (0, -1)
            )
            error = ErrorInfo(
                message="Frame index out of range",
                context={
                    "frame_index": frame_index,
                    "available_frames": len(self._frames),
                    "valid_range": valid_range,
                },
                location=location,
            )
            return AutopsyResult.err(error)
        return AutopsyResult.ok(Frame(self._frames[frame_index]))


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

    return CallStack(frames, autopsy_module_path)
