import inspect
import pickle
from typing import Dict, List, Tuple, Any


class Report:
    """Core report class for capturing debug values at call sites."""
    
    def __init__(self):
        """Initialize a fresh report with empty storage."""
        self._logs: Dict[Tuple[str, int], List[Any]] = {}
    
    def log(self, *args):
        """
        Capture values at the current call site.
        
        Args:
            *args: Variable number of values to capture
        """
        # Get the call site (file path and line number) from the caller's frame
        stack = inspect.stack()
        # Skip frames from autopsy module itself
        caller_frame = None
        for frame_info in stack[1:]:  # Skip current frame
            if not frame_info.filename.endswith('autopsy/report.py'):
                caller_frame = frame_info
                break
        
        if caller_frame is None:
            # Fallback if we can't find a non-autopsy frame
            caller_frame = stack[1]
        
        call_site = (caller_frame.filename, caller_frame.lineno)
        
        # Serialize and store the values
        serialized_values = []
        for value in args:
            try:
                # Pickle the value for storage
                pickled = pickle.dumps(value)
                serialized_values.append(pickled)
            except Exception as e:
                # Store error info if pickling fails
                serialized_values.append(f"<PickleError: {str(e)}>")
        
        # Append to the list for this call site
        if call_site not in self._logs:
            self._logs[call_site] = []
        self._logs[call_site].extend(serialized_values)
    
    def init(self):
        """Reset/initialize the report with fresh storage."""
        self._logs.clear()
    
    def get_logs(self) -> Dict[Tuple[str, int], List[Any]]:
        """
        Get all captured logs.
        
        Returns:
            Dictionary mapping call sites to lists of pickled values
        """
        return self._logs.copy()
    
    def get_call_sites(self) -> List[Tuple[str, int]]:
        """
        Get list of call sites that have logged data.
        
        Returns:
            List of (filepath, line_number) tuples
        """
        return list(self._logs.keys())


# Global singleton instance
_report_instance = Report()


def get_report() -> Report:
    """Get the global report instance."""
    return _report_instance


def init():
    """Initialize/reset the global report instance."""
    global _report_instance
    _report_instance = Report()

