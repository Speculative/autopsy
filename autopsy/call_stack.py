import inspect
import os
from typing import Optional, NamedTuple


class Caller(NamedTuple):
    """Information about a caller in the call stack."""
    function: str
    filename: str
    lineno: int


class CallStack:
    """Call stack introspection API."""
    
    # Store the autopsy package path as a class variable
    _autopsy_module_path = os.path.dirname(os.path.abspath(__file__))
    
    def __init__(self):
        """Capture the current call stack, excluding autopsy's own frames."""
        stack = inspect.stack()
        # Filter out frames from autopsy module and test infrastructure
        self._frames = []
        for frame_info in stack:
            # Skip frames from autopsy package directory
            frame_path = os.path.abspath(frame_info.filename)
            is_autopsy_package = frame_path.startswith(self._autopsy_module_path)
            
            if not is_autopsy_package:
                # Also skip pytest and other test infrastructure
                normalized_path = frame_info.filename.replace('\\', '/')
                filename_lower = normalized_path.lower()
                if 'pytest' not in filename_lower and 'unittest' not in filename_lower:
                    self._frames.append(frame_info)
    
    @property
    def caller(self) -> Optional[Caller]:
        """
        Get information about the immediate caller from the user function's perspective.
        
        Returns:
            Caller object with function name, file path, and line number,
            or None if no caller is available
        """
        if len(self._frames) < 2:
            # Need at least 2 frames: the function that called call_stack(), and its caller
            return None
        
        # After filtering out autopsy frames:
        # _frames[0] is the function that called call_stack()
        # _frames[1] is the caller of that function (what we want)
        caller_frame = self._frames[1]
        return Caller(
            function=caller_frame.function,
            filename=caller_frame.filename,
            lineno=caller_frame.lineno
        )


def call_stack() -> CallStack:
    """Create a CallStack instance for the current call site."""
    return CallStack()

