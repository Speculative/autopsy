import inspect
import json
import os
import pickle
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


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
            if not frame_info.filename.endswith("autopsy/report.py"):
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

    def to_json(self) -> Dict[str, Any]:
        """
        Convert report data to JSON-serializable format.

        Returns:
            Dictionary with 'generated_at' timestamp and 'call_sites' key containing
            list of call site data. Each call site has 'filename', 'line', and 'values' keys.
        """
        call_sites = []

        for call_site, pickled_values in self._logs.items():
            filename, line_number = call_site

            # Unpickle and convert values to JSON-serializable format
            json_values = []
            for pickled_value in pickled_values:
                if isinstance(pickled_value, str) and pickled_value.startswith(
                    "<PickleError"
                ):
                    # Already an error string, include as-is
                    json_values.append(pickled_value)
                elif isinstance(pickled_value, bytes):
                    try:
                        # Unpickle the value
                        unpickled = pickle.loads(pickled_value)
                        # Try to convert to JSON-serializable format
                        json_values.append(self._to_json_serializable(unpickled))
                    except Exception as e:
                        # If unpickling fails, store error info
                        json_values.append(f"<UnpickleError: {str(e)}>")
                else:
                    # Not bytes, try to serialize directly
                    json_values.append(self._to_json_serializable(pickled_value))

            call_sites.append(
                {
                    "filename": filename,
                    "line": line_number,
                    "values": json_values,
                }
            )

        return {
            "generated_at": datetime.now().isoformat(),
            "call_sites": call_sites,
        }

    def _to_json_serializable(self, value: Any) -> Any:
        """
        Convert a value to JSON-serializable format.

        Args:
            value: Value to convert

        Returns:
            JSON-serializable representation of the value
        """
        # Try to serialize directly with json.dumps to test if it's already serializable
        try:
            json.dumps(value)
            return value
        except (TypeError, ValueError):
            # Not directly serializable, try to convert
            if isinstance(value, (int, float, str, bool, type(None))):
                return value
            elif isinstance(value, (list, tuple)):
                return [self._to_json_serializable(item) for item in value]
            elif isinstance(value, dict):
                return {str(k): self._to_json_serializable(v) for k, v in value.items()}
            else:
                # For other types, try to get a string representation
                try:
                    return f"<{type(value).__name__}: {repr(value)}>"
                except Exception:
                    return f"<{type(value).__name__}: (unable to represent)>"


# Global singleton instance
_report_instance = Report()


def get_report() -> Report:
    """Get the global report instance."""
    return _report_instance


def init():
    """Initialize/reset the global report instance."""
    global _report_instance
    _report_instance = Report()


def generate_html(
    report: Optional[Report] = None, output_path: Optional[str] = None
) -> str:
    """
    Generate HTML report from Report data.

    Args:
        report: Report instance to generate HTML from. If None, uses the global report instance.
        output_path: Optional path to write the HTML file to. If None, returns the HTML as a string.

    Returns:
        The generated HTML as a string.
    """
    if report is None:
        report = get_report()

    # Load the template file
    template_path = Path(__file__).parent / "template.html"
    if not template_path.exists():
        raise FileNotFoundError(
            f"Template file not found at {template_path}. "
            "Make sure template.html exists in the autopsy package directory."
        )

    template_content = template_path.read_text(encoding="utf-8")

    # Get JSON data from report
    report_data = report.to_json()
    json_str = json.dumps(report_data, indent=2)

    # Inject JSON into the template
    # Find and replace the content of the <script id="autopsy-data"> tag
    pattern = r'(<script id="autopsy-data" type="application/json">)(.*?)(</script>)'
    replacement = r"\1" + json_str + r"\3"
    html_content = re.sub(pattern, replacement, template_content, flags=re.DOTALL)

    # Write to file if output_path is provided
    if output_path is not None:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(html_content, encoding="utf-8")

    return html_content
