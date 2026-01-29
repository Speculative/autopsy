import inspect
import os
import site
import sys
import time
from dataclasses import dataclass
from types import FrameType
from typing import Any, Callable, Dict, List, Optional

from .autopsy_result import (
    AutopsyResult,
    ErrorInfo,
    Location,
    _AttributeProxy,
    _capture_error_location,
)


@dataclass
class SerializableFrame:
    """A serializable representation of a stack frame."""

    filename: str
    function_name: str
    line_number: int
    code_context: str
    local_variables: Dict[str, Any]


@dataclass
class StackTrace:
    """A complete stack trace with all frames and their local variables."""

    frames: List[SerializableFrame]
    timestamp: float


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


class FrameQuery:
    """
    Query builder for navigating the call stack.

    Defers Frame creation until data is actually accessed, enabling efficient
    chaining like caller.caller without creating intermediate Frame objects.
    """

    def __init__(self, call_stack: "CallStack", frame_offset: int):
        """
        Initialize a FrameQuery.

        Args:
            call_stack: The CallStack instance this query belongs to
            frame_offset: Offset from current frame (0 = current, 1 = caller, etc.)
        """
        self._call_stack = call_stack
        self._frame_offset = frame_offset

    def _resolve(self) -> AutopsyResult[Frame]:
        """Resolve this query to an actual Frame."""
        return self._call_stack.frame(self._frame_offset)

    @property
    def caller(self) -> "FrameQuery":
        """Navigate to the caller frame - no Frame object created."""
        return FrameQuery(self._call_stack, self._frame_offset + 1)

    def is_ok(self) -> bool:
        """Check if this query can be resolved successfully."""
        return self._resolve().is_ok()

    def is_err(self) -> bool:
        """Check if this query would fail to resolve."""
        return self._resolve().is_err()

    @property
    def value(self) -> Frame:
        """Get the resolved Frame value, raising if resolution fails."""
        return self._resolve().value

    @property
    def error(self) -> ErrorInfo:
        """Get error information if resolution failed."""
        return self._resolve().error

    def variable(self, name: str) -> AutopsyResult[Variable]:
        """Get a variable from the resolved frame."""
        frame_result = self._resolve()
        if frame_result.is_err():
            # Propagate the error, but with the correct return type
            return AutopsyResult.err(frame_result.error)
        return frame_result.value.variable(name)

    def __getattr__(self, name: str) -> Any:
        """
        Forward attribute access to the resolved Frame.

        This enables direct property access like query.function, query.filename, etc.
        """
        frame_result = self._resolve()
        if frame_result.is_err():
            # Return a proxy that propagates the error
            return _AttributeProxy(frame_result, name)
        return getattr(frame_result.value, name)


class CallStack:
    """Call stack introspection API."""

    _frames: List[inspect.FrameInfo]
    _autopsy_module_path: str
    _captured_trace: Optional[StackTrace]

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
        self._captured_trace = None

    @property
    def current(self) -> FrameQuery:
        """
        Get information about the function that called call_stack().

        Returns:
            FrameQuery for the current frame (offset 0)
        """
        return FrameQuery(self, 0)

    @property
    def caller(self) -> FrameQuery:
        """
        Get information about the immediate caller from the user function's perspective.

        Returns:
            FrameQuery for the caller frame (offset 1)
        """
        return FrameQuery(self, 1)

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

    def _is_autopsy_object(self, value: Any) -> bool:
        """Check if an object is from the autopsy module."""
        if hasattr(value, "__module__"):
            module = value.__module__
            if module and ("autopsy" in module or "autopsy" in str(type(value))):
                return True
        # Check type name
        type_name = type(value).__name__
        if "Autopsy" in type_name or "CallStack" in type_name or "Frame" in type_name:
            return True
        return False

    def _is_function_or_module(self, value: Any) -> bool:
        """Check if a value is a function, module, or type (class)."""
        import types

        # Check if it's a type/class
        if isinstance(value, type):
            return True

        # Check if it's a function or module
        return isinstance(
            value,
            (
                types.FunctionType,
                types.BuiltinFunctionType,
                types.MethodType,
                types.BuiltinMethodType,
                types.ModuleType,
            ),
        )

    def _serialize_to_json(
        self, value: Any, visited: Optional[set] = None, max_depth: int = 10
    ) -> Any:
        """
        Recursively serialize a value to JSON-compatible format.

        Args:
            value: The value to serialize
            visited: Set of object IDs already visited (for circular reference detection)
            max_depth: Maximum recursion depth

        Returns:
            JSON-serializable representation of the value
        """
        if visited is None:
            visited = set()

        if max_depth <= 0:
            return "<max_depth_reached>"

        # Handle None
        if value is None:
            return None

        # Skip autopsy objects
        if self._is_autopsy_object(value):
            return f"<autopsy.{type(value).__name__}>"

        # Skip functions and modules
        if self._is_function_or_module(value):
            return f"<{type(value).__name__}>"

        # Handle primitive types
        if isinstance(value, (int, float, bool, str)):
            # Truncate long strings
            if isinstance(value, str) and len(value) > 1000:
                return value[:997] + "..."
            return value

        # Handle circular references
        obj_id = id(value)
        if obj_id in visited:
            return "<circular_reference>"

        # Add to visited set for mutable types
        is_mutable = isinstance(value, (list, dict, set)) or (
            hasattr(value, "__dict__") and not isinstance(value, type)
        )
        if is_mutable:
            visited.add(obj_id)

        try:
            # Handle lists and tuples
            if isinstance(value, (list, tuple)):
                result = [
                    self._serialize_to_json(item, visited, max_depth - 1)
                    for item in value
                ]
                if is_mutable:
                    visited.remove(obj_id)
                return result

            # Handle dictionaries
            if isinstance(value, dict):
                result = {}
                for k, v in value.items():
                    # Skip keys that aren't JSON-serializable
                    try:
                        key_str = (
                            str(k)
                            if isinstance(k, (str, int, float, bool))
                            else repr(k)
                        )
                        result[key_str] = self._serialize_to_json(
                            v, visited, max_depth - 1
                        )
                    except Exception:
                        continue
                if is_mutable:
                    visited.remove(obj_id)
                return result

            # Handle sets
            if isinstance(value, set):
                result = [
                    self._serialize_to_json(item, visited, max_depth - 1)
                    for item in value
                ]
                if is_mutable:
                    visited.remove(obj_id)
                return result

            # Handle objects with __dict__
            if hasattr(value, "__dict__") and not isinstance(value, type):
                result = {}
                try:
                    for attr_name, attr_value in value.__dict__.items():
                        # Skip private attributes and autopsy objects
                        if attr_name.startswith("_"):
                            continue
                        if self._is_autopsy_object(attr_value):
                            continue
                        if self._is_function_or_module(attr_value):
                            continue
                        try:
                            result[attr_name] = self._serialize_to_json(
                                attr_value, visited, max_depth - 1
                            )
                        except Exception:
                            result[attr_name] = "<serialization_error>"
                    if is_mutable:
                        visited.remove(obj_id)
                    return result
                except Exception:
                    if is_mutable:
                        visited.discard(obj_id)
                    return f"<{type(value).__name__}: serialization_failed>"

            # Try to convert to JSON directly
            import json

            try:
                json.dumps(value)
                if is_mutable:
                    visited.discard(obj_id)
                return value
            except (TypeError, ValueError):
                pass

            # Fallback: return type name
            if is_mutable:
                visited.discard(obj_id)
            return f"<{type(value).__name__}>"

        except Exception as e:
            if is_mutable:
                visited.discard(obj_id)
            return f"<{type(value).__name__}: {str(e)[:50]}>"

    def _extract_local_variables(self, frame: FrameType) -> Dict[str, Any]:
        """Extract local variables from frame and convert to JSON-serializable form."""
        local_vars = {}

        filtered_items = [
            (var_name, var_value)
            for var_name, var_value in frame.f_locals.items()
            if not var_name.startswith("_")
            and var_name not in ("__builtins__", "__file__", "__name__")
        ]

        for var_name, var_value in filtered_items:
            # Skip autopsy objects, functions, modules, and types (classes)
            if self._is_autopsy_object(var_value):
                continue
            if self._is_function_or_module(var_value):
                continue

            try:
                local_vars[var_name] = self._serialize_to_json(var_value)
            except Exception:
                # If serialization fails completely, skip the variable
                continue

        return local_vars

    def _get_line_content(self, filename: str, line_no: int) -> str:
        """Get line content from a file, capturing multi-line calls."""
        try:
            import textwrap
            with open(filename, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if 0 < line_no <= len(lines):
                    # Try to detect if this is a multi-line call using AST
                    end_line = self._find_call_end_line(filename, line_no)
                    if end_line and end_line > line_no:
                        # Multi-line call: capture all lines from line_no to end_line
                        captured_lines = []
                        for i in range(line_no - 1, min(end_line, len(lines))):
                            captured_lines.append(lines[i].rstrip("\n\r"))
                        # Dedent to remove common leading whitespace
                        dedented = textwrap.dedent("\n".join(captured_lines))
                        return dedented.strip()
                    else:
                        # Single line or AST parsing failed: return just the single line
                        return lines[line_no - 1].strip()
        except Exception:
            pass
        return ""

    def _find_call_end_line(self, filename: str, line_no: int) -> Optional[int]:
        """
        Find the ending line number of a call that starts at line_no.

        Args:
            filename: Path to the source file
            line_no: Line number where the call starts

        Returns:
            Ending line number if found, None otherwise
        """
        try:
            import ast
            with open(filename, "r", encoding="utf-8") as f:
                source_code = f.read()

            tree = ast.parse(source_code, filename=filename)

            # Walk the AST to find a Call node that spans from line_no
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    # Check if this call starts at or contains our line_no
                    if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
                        if node.lineno <= line_no <= node.end_lineno:
                            return node.end_lineno

            return None
        except Exception:
            return None

    def _create_serializable_frame(self, frame: FrameType) -> SerializableFrame:
        """Create a serializable frame from a Python frame object."""
        filename = frame.f_code.co_filename
        function_name = frame.f_code.co_name
        line_number = frame.f_lineno
        code_context = self._get_line_content(filename, line_number)
        local_variables = self._extract_local_variables(frame)

        return SerializableFrame(
            filename=filename,
            function_name=function_name,
            line_number=line_number,
            code_context=code_context,
            local_variables=local_variables,
        )

    def _is_stdlib_frame(self, frame: FrameType) -> bool:
        """Check if frame is from Python standard library."""
        filename = frame.f_code.co_filename

        # Check for generated/frozen code
        if filename.startswith("<") and filename.endswith(">"):
            module_name = frame.f_globals.get("__name__")
            return bool(module_name and module_name in sys.builtin_module_names)

        # Check if file is in stdlib directory
        abs_filename = os.path.abspath(filename)
        stdlib_dir = os.path.dirname(os.__file__)
        if abs_filename.startswith(stdlib_dir):
            return True

        # Check if module is in stdlib module names (Python 3.10+)
        if sys.version_info >= (3, 10):
            module_name = frame.f_globals.get("__name__")
            if module_name and hasattr(sys, "stdlib_module_names"):
                return bool(module_name in sys.stdlib_module_names)

        return False

    def _is_site_packages_frame(self, frame: FrameType) -> bool:
        """Check if frame is from site-packages."""
        filename = frame.f_code.co_filename

        # Skip generated code
        if filename.startswith("<") and filename.endswith(">"):
            return False

        abs_filename = os.path.abspath(filename)
        site_packages_dirs = site.getsitepackages()
        user_site = site.getusersitepackages()
        if user_site not in site_packages_dirs:
            site_packages_dirs.append(user_site)

        for sp_dir in site_packages_dirs:
            if sp_dir and os.path.isdir(sp_dir):
                if abs_filename.startswith(os.path.abspath(sp_dir)):
                    return True

        return False

    def _is_entry_point_frame(self, frame: FrameType) -> bool:
        """
        Check if frame is a Python entry point (like _run_module_as_main, _run_code).

        These are stdlib frames that represent the entry point of execution,
        and we should stop capturing here since everything below is execution infrastructure.
        """
        function_name = frame.f_code.co_name
        filename = frame.f_code.co_filename

        # Entry point functions in runpy module
        entry_point_functions = {
            "_run_module_as_main",
            "_run_code",
            "run_path",
            "run_module",
        }

        if function_name in entry_point_functions:
            # Check if it's actually from runpy
            if "runpy.py" in filename:
                return True

        # Check for exec/eval entry points
        if function_name in ("exec", "eval") and filename.startswith("<"):
            return True

        return False

    def _capture_full_stack(self) -> StackTrace:
        """
        Capture the complete stack trace from the current frames.

        Includes stdlib frames that are in the middle of the call chain (like map, filter, etc.)
        but stops at entry point frames (like _run_module_as_main) since those represent
        execution infrastructure rather than user code.
        """
        frames = []

        # Walk through all frames in self._frames
        # Include stdlib frames in the middle, but stop at entry point frames
        for frame_info in self._frames:
            try:
                frame = frame_info.frame

                # Stop capturing at entry point frames (execution infrastructure)
                if self._is_entry_point_frame(frame):
                    break

                # Include all frames (user code and stdlib in the middle)
                # Only skip site-packages frames
                if self._is_site_packages_frame(frame):
                    continue

                serializable_frame = self._create_serializable_frame(frame)
                frames.append(serializable_frame)
            except Exception:
                # Skip problematic frames but continue
                pass

        return StackTrace(frames=frames, timestamp=time.time())

    def capture_stack_trace(self) -> StackTrace:
        """
        Capture full stack trace lazily.

        Returns:
            StackTrace object with all frames and variables
        """
        if self._captured_trace is None:
            self._captured_trace = self._capture_full_stack()
        return self._captured_trace


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
