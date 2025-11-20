import ast
import inspect
import json
import pickle
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .call_stack import CallStack, StackTrace, call_stack


@dataclass
class ReportConfiguration:
    """Configuration for Report behavior."""

    auto_stack_trace: bool = True


class Report:
    """Core report class for capturing debug values at call sites."""

    def __init__(self, config: Optional[ReportConfiguration] = None):
        """
        Initialize a fresh report with empty storage.

        Args:
            config: Optional configuration object. If None, uses default configuration.
        """
        # Store groups of values with metadata, where each group represents one log() call
        # Format: Dict[call_site, List[LogGroup]]
        # LogGroup contains: values (list of pickled values), function_name, arg_names, log_index
        self._logs: Dict[Tuple[str, int], List[Dict[str, Any]]] = {}
        # Global log index to track total ordering across all log calls
        self._log_index: int = 0
        # Configuration
        self._config = config if config is not None else ReportConfiguration()
        # Stack traces stored by CallStack object ID
        self._stack_traces: Dict[int, StackTrace] = {}
        # Map from CallStack object ID to list of log indices that use it
        self._stack_trace_id_to_log_indices: Dict[int, List[int]] = {}

    def _ast_node_to_expression(self, node: ast.expr) -> Optional[str]:
        """
        Convert an AST expression node to its source code representation.

        Args:
            node: AST expression node

        Returns:
            String representation of the expression, or None if not extractable
        """
        try:
            # Use ast.unparse if available (Python 3.9+)
            if hasattr(ast, "unparse"):
                return ast.unparse(node)
        except Exception:
            pass

        # Fallback: manually reconstruct common patterns
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            # Handle attribute access like obj.attr or obj.attr.subattr
            parts: List[str] = []
            current: ast.expr = node
            while isinstance(current, ast.Attribute):
                parts.insert(0, current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.insert(0, current.id)
                return ".".join(parts)
            return None
        elif isinstance(node, ast.Call):
            # Handle function/method calls
            func_str = self._ast_node_to_expression(node.func)
            if func_str:
                args_str = ", ".join(
                    self._ast_node_to_expression(arg) or "" for arg in node.args
                )
                return f"{func_str}({args_str})"
            return None
        elif isinstance(node, ast.Constant):
            # Literal values - return None to indicate no expression name
            return None
        elif isinstance(node, ast.BinOp):
            # Binary operations like x + y, a * b, etc.
            left = self._ast_node_to_expression(node.left)
            right = self._ast_node_to_expression(node.right)
            op_str = self._binop_to_str(node.op)
            if left and right and op_str:
                return f"{left} {op_str} {right}"
            return None
        elif isinstance(node, ast.UnaryOp):
            # Unary operations like -x, not y, etc.
            operand = self._ast_node_to_expression(node.operand)
            op_str = self._unaryop_to_str(node.op)
            if operand and op_str:
                return f"{op_str}{operand}"
            return None
        elif isinstance(node, ast.Compare):
            # Comparisons like x < y, a == b, etc.
            left = self._ast_node_to_expression(node.left)
            if not left:
                return None
            parts = [left]
            for op, comparator in zip(node.ops, node.comparators):
                comp_str = self._ast_node_to_expression(comparator)
                op_str = self._cmpop_to_str(op)
                if comp_str and op_str:
                    parts.append(f"{op_str} {comp_str}")
                else:
                    return None
            return " ".join(parts)
        else:
            # For other expression types, return None
            return None

    def _binop_to_str(self, op: ast.operator) -> Optional[str]:
        """Convert binary operator to string."""
        op_map = {
            ast.Add: "+",
            ast.Sub: "-",
            ast.Mult: "*",
            ast.Div: "/",
            ast.FloorDiv: "//",
            ast.Mod: "%",
            ast.Pow: "**",
            ast.LShift: "<<",
            ast.RShift: ">>",
            ast.BitOr: "|",
            ast.BitXor: "^",
            ast.BitAnd: "&",
        }
        return op_map.get(type(op))

    def _unaryop_to_str(self, op: ast.unaryop) -> Optional[str]:
        """Convert unary operator to string."""
        op_map = {
            ast.UAdd: "+",
            ast.USub: "-",
            ast.Not: "not ",
            ast.Invert: "~",
        }
        return op_map.get(type(op))

    def _cmpop_to_str(self, op: ast.cmpop) -> Optional[str]:
        """Convert comparison operator to string."""
        op_map = {
            ast.Eq: "==",
            ast.NotEq: "!=",
            ast.Lt: "<",
            ast.LtE: "<=",
            ast.Gt: ">",
            ast.GtE: ">=",
            ast.Is: "is",
            ast.IsNot: "is not",
            ast.In: "in",
            ast.NotIn: "not in",
        }
        return op_map.get(type(op))

    def _extract_arg_names(
        self, filename: str, line_number: int
    ) -> List[Optional[str]]:
        """
        Extract argument names from a report.log() call using AST parsing.

        Args:
            filename: Path to the source file
            line_number: Line number of the log() call

        Returns:
            List of argument names (or None if extraction fails)
        """
        try:
            with open(filename, "r", encoding="utf-8") as f:
                source_code = f.read()

            # Parse the entire file with AST
            tree = ast.parse(source_code, filename=filename)

            # Walk the AST to find the call site
            class LogCallFinder(ast.NodeVisitor):
                def __init__(self, target_line: int):
                    self.target_line = target_line
                    self.found_call: Optional[ast.Call] = None

                def visit_Call(self, node: ast.Call):
                    # Check if this is a report.log() call on the target line
                    if (
                        node.lineno == self.target_line
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "log"
                    ):
                        # Check if the base is "report" or "_report"
                        if isinstance(node.func.value, ast.Name):
                            if node.func.value.id in ("report", "_report"):
                                self.found_call = node
                        elif isinstance(node.func.value, ast.Attribute):
                            # Handle cases like module.report.log
                            if isinstance(
                                node.func.value.value, ast.Name
                            ) and node.func.value.value.id in ("report", "_report"):
                                self.found_call = node
                    # Continue visiting
                    self.generic_visit(node)

            finder = LogCallFinder(line_number)
            finder.visit(tree)

            if finder.found_call is None:
                return []

            # Extract argument expressions from the AST nodes
            arg_names: List[Optional[str]] = []
            for arg in finder.found_call.args:
                expr = self._ast_node_to_expression(arg)
                arg_names.append(expr)

            return arg_names

        except Exception:
            # If AST parsing fails, return empty list
            return []

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

        # Get function name and class name (if it's a method)
        function_name = caller_frame.function
        class_name = None
        frame = caller_frame.frame
        if "self" in frame.f_locals:
            self_obj = frame.f_locals["self"]
            class_name = type(self_obj).__name__

        # Extract argument names from source code
        arg_names = self._extract_arg_names(caller_frame.filename, caller_frame.lineno)
        # Pad or truncate to match actual number of arguments
        if len(arg_names) < len(args):
            arg_names.extend([None] * (len(args) - len(arg_names)))
        elif len(arg_names) > len(args):
            arg_names = arg_names[: len(args)]

        # Check if any argument is a CallStack instance, otherwise create one
        # Always capture stack trace if auto_stack_trace is enabled
        stack_trace_id: Optional[int] = None
        call_stack_obj: Optional[CallStack] = None

        # First, check if a CallStack was passed in args
        for value in args:
            if isinstance(value, CallStack):
                call_stack_obj = value
                break

        # If no CallStack was passed and auto_stack_trace is enabled, create one
        if call_stack_obj is None and self._config.auto_stack_trace:
            call_stack_obj = call_stack()

        # Capture stack trace if we have a CallStack and auto_stack_trace is enabled
        if call_stack_obj is not None and self._config.auto_stack_trace:
            # Capture stack trace lazily (only captures when this is called)
            trace = call_stack_obj.capture_stack_trace()
            stack_trace_id = id(call_stack_obj)
            # Store trace if not already stored (deduplication by object identity)
            if stack_trace_id not in self._stack_traces:
                self._stack_traces[stack_trace_id] = trace
            # Associate this log index with the stack trace ID
            if stack_trace_id not in self._stack_trace_id_to_log_indices:
                self._stack_trace_id_to_log_indices[stack_trace_id] = []
            self._stack_trace_id_to_log_indices[stack_trace_id].append(self._log_index)

        # Serialize and store the values as a group
        serialized_values = []
        for value in args:
            try:
                # Pickle the value for storage
                pickled = pickle.dumps(value)
                serialized_values.append(pickled)
            except Exception as e:
                # Store error info if pickling fails
                serialized_values.append(f"<PickleError: {str(e)}>")

        # Store the group with metadata including log index for total ordering
        log_group = {
            "values": serialized_values,
            "function_name": function_name,
            "arg_names": arg_names,
            "log_index": self._log_index,
        }
        if class_name is not None:
            log_group["class_name"] = class_name
        if stack_trace_id is not None:
            log_group["stack_trace_id"] = stack_trace_id

        # Increment the global log index
        self._log_index += 1

        # Append the group to the list for this call site
        if call_site not in self._logs:
            self._logs[call_site] = []
        self._logs[call_site].append(log_group)

    def init(self, config: Optional[ReportConfiguration] = None):
        """
        Reset/initialize the report with fresh storage.

        Args:
            config: Optional configuration object. If None, keeps existing config.
        """
        self._logs.clear()
        self._log_index = 0
        self._stack_traces.clear()
        self._stack_trace_id_to_log_indices.clear()
        if config is not None:
            self._config = config

    def get_logs(self) -> Dict[Tuple[str, int], List[Dict[str, Any]]]:
        """
        Get all captured logs.

        Returns:
            Dictionary mapping call sites to lists of log groups.
            Each group is a dict with 'values', 'function_name', and 'arg_names'.
        """
        return self._logs.copy()

    def get_call_sites(self) -> List[Tuple[str, int]]:
        """
        Get list of call sites that have logged data.

        Returns:
            List of (filepath, line_number) tuples
        """
        return list(self._logs.keys())

    def get_stack_trace(self, log_index: int) -> Optional[StackTrace]:
        """
        Get the stack trace associated with a log entry.

        Args:
            log_index: The log index to get the stack trace for

        Returns:
            StackTrace if found, None otherwise
        """
        # Find which stack trace ID this log index belongs to
        for stack_trace_id, log_indices in self._stack_trace_id_to_log_indices.items():
            if log_index in log_indices:
                return self._stack_traces.get(stack_trace_id)
        return None

    def to_json(self) -> Dict[str, Any]:
        """
        Convert report data to JSON-serializable format.

        Returns:
            Dictionary with 'generated_at' timestamp and 'call_sites' key containing
            list of call site data. Each call site has 'filename', 'line', and 'value_groups' keys.
            Each value_group is a list of values from one log() call.
        """
        call_sites = []

        for call_site, log_groups in self._logs.items():
            filename, line_number = call_site

            # Process each group of values from a single log() call
            json_value_groups = []
            for log_group in log_groups:
                json_group = []
                pickled_values = log_group["values"]
                arg_names = log_group.get("arg_names", [])

                for idx, pickled_value in enumerate(pickled_values):
                    value_data = {}

                    # Add argument name if available
                    if idx < len(arg_names) and arg_names[idx] is not None:
                        value_data["name"] = arg_names[idx]

                    # Unpickle and convert value
                    if isinstance(pickled_value, str) and pickled_value.startswith(
                        "<PickleError"
                    ):
                        value_data["value"] = pickled_value
                    elif isinstance(pickled_value, bytes):
                        try:
                            # Unpickle the value
                            unpickled = pickle.loads(pickled_value)
                            # Try to convert to JSON-serializable format
                            value_data["value"] = self._to_json_serializable(unpickled)
                        except Exception as e:
                            # If unpickling fails, store error info
                            value_data["value"] = f"<UnpickleError: {str(e)}>"
                    else:
                        # Not bytes, try to serialize directly
                        value_data["value"] = self._to_json_serializable(pickled_value)

                    json_group.append(value_data)

                value_group_data = {
                    "values": json_group,
                    "function_name": log_group.get("function_name", "<unknown>"),
                    "log_index": log_group.get("log_index", 0),
                }
                if "class_name" in log_group:
                    value_group_data["class_name"] = log_group["class_name"]
                if "stack_trace_id" in log_group:
                    # Convert to string to match stack_traces dictionary keys
                    value_group_data["stack_trace_id"] = str(
                        log_group["stack_trace_id"]
                    )
                json_value_groups.append(value_group_data)

            call_site_data = {
                "filename": filename,
                "line": line_number,
                "function_name": (
                    log_groups[0].get("function_name", "<unknown>")
                    if log_groups
                    else "<unknown>"
                ),
                "value_groups": json_value_groups,
            }
            if log_groups and "class_name" in log_groups[0]:
                call_site_data["class_name"] = log_groups[0]["class_name"]
            call_sites.append(call_site_data)

        # Convert stack traces to JSON-serializable format
        json_stack_traces = {}
        for trace_id, trace in self._stack_traces.items():
            json_frames = []
            for frame in trace.frames:
                json_frames.append(
                    {
                        "filename": frame.filename,
                        "function_name": frame.function_name,
                        "line_number": frame.line_number,
                        "code_context": frame.code_context,
                        "local_variables": frame.local_variables,
                    }
                )
            json_stack_traces[str(trace_id)] = {
                "frames": json_frames,
                "timestamp": trace.timestamp,
            }

        return {
            "generated_at": datetime.now().isoformat(),
            "call_sites": call_sites,
            "stack_traces": json_stack_traces,
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


def init(config: Optional[ReportConfiguration] = None):
    """
    Initialize/reset the global report instance.

    Args:
        config: Optional configuration object. If None, uses default configuration.
    """
    global _report_instance
    _report_instance = Report(config)


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


def generate_json(
    report: Optional[Report] = None, output_path: Optional[str] = None
) -> str:
    """
    Generate JSON report from Report data.

    Args:
        report: Report instance to generate JSON from. If None, uses the global report instance.
        output_path: Optional path to write the JSON file to. If None, returns the JSON as a string.

    Returns:
        The generated JSON as a string.
    """
    if report is None:
        report = get_report()

    # Get JSON data from report
    report_data = report.to_json()
    json_str = json.dumps(report_data, indent=2)

    # Write to file if output_path is provided
    if output_path is not None:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json_str, encoding="utf-8")

    return json_str
