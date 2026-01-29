import ast
import atexit
import base64
import gzip
import inspect
import json
import pickle
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional, Tuple

from .call_stack import CallStack, StackTrace, call_stack


@dataclass
class ReportConfiguration:
    """Configuration for Report behavior."""

    auto_stack_trace: bool = True
    live_mode: bool = False
    live_mode_host: str = "localhost"
    live_mode_port: int = 8765


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
        # Stack traces stored by log index (each log has its own unique stack trace)
        self._stack_traces: Dict[int, StackTrace] = {}
        # Dashboard data storage
        # Counts: per call site, value -> list of (stack_trace_id, log_index) tuples
        self._counts: Dict[Tuple[str, int], Dict[Any, List[Tuple[int, int]]]] = {}
        # Counts metadata: per call site, (function_name, class_name)
        self._counts_metadata: Dict[Tuple[str, int], Tuple[str, Optional[str]]] = {}
        # Histograms: per call site, list of (number, stack_trace_id, log_index) tuples
        self._histograms: Dict[Tuple[str, int], List[Tuple[float, int, int]]] = {}
        # Histograms metadata: per call site, (function_name, class_name)
        self._histograms_metadata: Dict[Tuple[str, int], Tuple[str, Optional[str]]] = {}
        # Timeline: global list of events with timestamp, event_name, call_site, stack_trace_id
        self._timeline: List[Dict[str, Any]] = []
        # Happened: per call site, (count, list of (stack_trace_id, log_index) tuples, optional message)
        self._happened: Dict[
            Tuple[str, int], Tuple[int, List[Tuple[int, int]], Optional[str]]
        ] = {}
        # Happened metadata: per call site, (function_name, class_name)
        self._happened_metadata: Dict[Tuple[str, int], Tuple[str, Optional[str]]] = {}
        # Dashboard logs: per call site, list of dashboard invocation logs
        # TODO: Eventually unify dashboard logs with regular log() call sites.
        # Instead of maintaining separate _dashboard_logs storage, we should store dashboard
        # visualization metadata (count/hist/timeline/happened) as additional metadata on
        # call sites in _logs, eliminating the need for separate storage.
        # Format: Dict[call_site, List[DashboardLogGroup]]
        # DashboardLogGroup contains: log_index, dashboard_type, stack_trace_id, function_name, class_name, and type-specific data
        self._dashboard_logs: Dict[Tuple[str, int], List[Dict[str, Any]]] = {}
        # Thread safety
        self._lock = RLock()  # Reentrant lock for nested calls
        self._live_mode_enabled = False
        # Tracking for lazy initialization and auto-write
        self._initialized = False
        self._written = False

    def _ensure_initialized(self):
        """
        Ensure the report is initialized before use.
        Called automatically on first log/count/hist/timeline/happened call.
        """
        if not self._initialized:
            # Initialize with default config if not already initialized
            self._initialized = True

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

    def _find_log_call_ast(self, filename: str, line_number: int) -> Optional[ast.Call]:
        """
        Find the AST node for a report.log() or autopsy.log() call at the given line.

        Args:
            filename: Path to the source file
            line_number: Line number of the log() call

        Returns:
            AST Call node if found, None otherwise
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
                    # Check if this is a log() call on the target line
                    if (
                        node.lineno == self.target_line
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "log"
                    ):
                        # Check if the attribute before .log() is "report", "_report", or "autopsy"
                        # This handles: report.log(), autopsy.log(), self.report.log(), module.report.log(), etc.
                        if isinstance(node.func.value, ast.Name):
                            # Handle: report.log(), _report.log(), or autopsy.log()
                            if node.func.value.id in ("report", "_report", "autopsy"):
                                self.found_call = node
                        elif isinstance(node.func.value, ast.Attribute):
                            # Handle: self.report.log(), module.report.log(), etc.
                            # Check if the attribute name is "report" or "_report"
                            if node.func.value.attr in ("report", "_report"):
                                self.found_call = node
                    # Continue visiting
                    self.generic_visit(node)

            finder = LogCallFinder(line_number)
            finder.visit(tree)

            return finder.found_call

        except Exception:
            # If AST parsing fails, return None
            return None

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
        call_node = self._find_log_call_ast(filename, line_number)
        if call_node is None:
            return []

        # Extract argument expressions from the AST nodes
        arg_names: List[Optional[str]] = []
        for arg in call_node.args:
            expr = self._ast_node_to_expression(arg)
            arg_names.append(expr)

        return arg_names

    def _infer_name_from_first_arg(
        self, filename: str, line_number: int, first_arg_value: Any
    ) -> Optional[str]:
        """
        Infer a name from the first argument if it's a string literal.

        Args:
            filename: Path to the source file
            line_number: Line number of the log() call
            first_arg_value: The actual value of the first argument

        Returns:
            The string literal value if the first argument is a constant string literal,
            None otherwise
        """
        call_node = self._find_log_call_ast(filename, line_number)
        if call_node is None or len(call_node.args) == 0:
            return None

        first_arg_node = call_node.args[0]

        # Check if it's a string literal constant
        if isinstance(first_arg_node, ast.Constant):
            if isinstance(first_arg_value, str):
                # It's a string literal - return the value
                return first_arg_value

        return None

    def log(self, *args, name: Optional[str] = None):
        """
        Capture values at the current call site.

        Args:
            *args: Variable number of values to capture
            name: Optional name for this log entry. If not provided and the first
                  argument is a string literal, it will be inferred as the name.
        """
        self._ensure_initialized()
        with self._lock:
            # Get the call site (file path and line number) from the caller's frame
            stack = inspect.stack()
            # Skip frames from autopsy module itself
            caller_frame = None
            for frame_info in stack[1:]:  # Skip current frame
                # Skip any frame from within the autopsy package
                if not frame_info.filename.endswith(("autopsy/report.py", "autopsy/__init__.py")):
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

            # Infer name from first argument if not provided and first arg is a string literal constant
            inferred_name: Optional[str] = None
            args_to_store = list(args)
            arg_names_to_store: List[Optional[str]] = []

            if name is None and len(args) > 0:
                inferred_name = self._infer_name_from_first_arg(
                    caller_frame.filename, caller_frame.lineno, args[0]
                )
                if inferred_name is not None:
                    # Exclude the first argument from storage
                    args_to_store = list(args[1:])
                    # Extract arg names excluding the first one
                    all_arg_names = self._extract_arg_names(
                        caller_frame.filename, caller_frame.lineno
                    )
                    arg_names_to_store = all_arg_names[1:] if len(all_arg_names) > 1 else []
                else:
                    # No inference, use all args
                    arg_names_to_store = self._extract_arg_names(
                        caller_frame.filename, caller_frame.lineno
                    )
            else:
                # Name provided explicitly, use all args
                arg_names_to_store = self._extract_arg_names(
                    caller_frame.filename, caller_frame.lineno
                )

            # Use inferred name if available, otherwise use explicit name
            log_name = inferred_name if inferred_name is not None else name

            # Pad or truncate arg_names to match actual number of arguments to store
            if len(arg_names_to_store) < len(args_to_store):
                arg_names_to_store.extend(
                    [None] * (len(args_to_store) - len(arg_names_to_store))
                )
            elif len(arg_names_to_store) > len(args_to_store):
                arg_names_to_store = arg_names_to_store[: len(args_to_store)]

            # Check if any argument is a CallStack instance, otherwise create one
            # Always capture stack trace if auto_stack_trace is enabled
            stack_trace_id: Optional[int] = None
            call_stack_obj: Optional[CallStack] = None

            # First, check if a CallStack was passed in args_to_store
            for value in args_to_store:
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
                # Use the current log index as the stack trace ID
                stack_trace_id = self._log_index
                # Store the trace
                self._stack_traces[stack_trace_id] = trace

            # Serialize and store the values as a group
            serialized_values = []
            for value in args_to_store:
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
                "arg_names": arg_names_to_store,
                "log_index": self._log_index,
            }
            if class_name is not None:
                log_group["class_name"] = class_name
            if stack_trace_id is not None:
                log_group["stack_trace_id"] = stack_trace_id
            if log_name is not None:
                log_group["name"] = log_name

            # Increment the global log index
            self._log_index += 1

            # Append the group to the list for this call site
            if call_site not in self._logs:
                self._logs[call_site] = []
            self._logs[call_site].append(log_group)

            # Broadcast update in live mode
            if self._live_mode_enabled:
                self._broadcast_log_update(call_site, log_group, stack_trace_id)

    def _get_call_site_and_stack_trace(
        self,
    ) -> Tuple[Tuple[str, int], Optional[int], str, Optional[str]]:
        """
        Helper method to get call site and capture stack trace for dashboard methods.

        Returns:
            Tuple of (call_site, stack_trace_id, function_name, class_name) where:
            - call_site is (filename, line_number)
            - stack_trace_id is None if stack trace capture is disabled or failed
            - function_name is the name of the function containing the call
            - class_name is the class name if it's a method, None otherwise
        """
        # Get the call site (file path and line number) from the caller's frame
        stack = inspect.stack()
        # Skip frames from autopsy module itself
        caller_frame = None
        for frame_info in stack[1:]:  # Skip current frame
            # Skip any frame from within the autopsy package
            if not frame_info.filename.endswith(("autopsy/report.py", "autopsy/__init__.py")):
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

        # Note: Stack trace will be captured by the caller using the log_index
        # We return None here and let the caller capture it with the proper log_index
        stack_trace_id: Optional[int] = None

        return call_site, stack_trace_id, function_name, class_name

    def count(self, value: Any):
        """
        Collect a value and count how many times this call site was called with that value.

        Args:
            value: The value to count occurrences of
        """
        self._ensure_initialized()
        with self._lock:
            call_site, _, function_name, class_name = (
                self._get_call_site_and_stack_trace()
            )

            # Assign log index for this invocation
            log_index = self._log_index
            self._log_index += 1

            # Capture stack trace if auto_stack_trace is enabled
            stack_trace_id: Optional[int] = None
            if self._config.auto_stack_trace:
                call_stack_obj = call_stack()
                trace = call_stack_obj.capture_stack_trace()
                # Use the log index as the stack trace ID
                stack_trace_id = log_index
                # Store the trace
                self._stack_traces[stack_trace_id] = trace

            # Store dashboard log entry
            if call_site not in self._dashboard_logs:
                self._dashboard_logs[call_site] = []

            dashboard_log = {
                "log_index": log_index,
                "dashboard_type": "count",
                "function_name": function_name,
                "value": value,
            }
            if class_name is not None:
                dashboard_log["class_name"] = class_name
            if stack_trace_id is not None:
                dashboard_log["stack_trace_id"] = stack_trace_id

            self._dashboard_logs[call_site].append(dashboard_log)

            # Broadcast update in live mode
            if self._live_mode_enabled:
                self._broadcast_dashboard_update(call_site, dashboard_log)

            if call_site not in self._counts:
                self._counts[call_site] = {}
                self._counts_metadata[call_site] = (function_name, class_name)

            # For unhashable types, use JSON string representation as key
            # This matches how we serialize in to_json()
            try:
                # Try to use value directly as dict key (works for hashable types)
                hash(value)  # Test if hashable
                value_key = value
            except TypeError:
                # For unhashable types, use JSON string representation
                json_value = self._to_json_serializable(value)
                value_key = json.dumps(json_value, sort_keys=True)

            if value_key not in self._counts[call_site]:
                self._counts[call_site][value_key] = []

            # Append even if stack_trace_id is None (will be -1 or None in that case)
            self._counts[call_site][value_key].append(
                (stack_trace_id if stack_trace_id is not None else -1, log_index)
            )

    def hist(self, num: float):
        """
        Collect a number from each invocation to produce a histogram.

        Args:
            num: The number to add to the histogram
        """
        self._ensure_initialized()
        with self._lock:
            call_site, _, function_name, class_name = (
                self._get_call_site_and_stack_trace()
            )

            # Assign log index for this invocation
            log_index = self._log_index
            self._log_index += 1

            # Capture stack trace if auto_stack_trace is enabled
            stack_trace_id: Optional[int] = None
            if self._config.auto_stack_trace:
                call_stack_obj = call_stack()
                trace = call_stack_obj.capture_stack_trace()
                # Use the log index as the stack trace ID
                stack_trace_id = log_index
                # Store the trace
                self._stack_traces[stack_trace_id] = trace

            # Store dashboard log entry
            if call_site not in self._dashboard_logs:
                self._dashboard_logs[call_site] = []

            dashboard_log = {
                "log_index": log_index,
                "dashboard_type": "hist",
                "function_name": function_name,
                "value": num,
            }
            if class_name is not None:
                dashboard_log["class_name"] = class_name
            if stack_trace_id is not None:
                dashboard_log["stack_trace_id"] = stack_trace_id

            self._dashboard_logs[call_site].append(dashboard_log)

            # Broadcast update in live mode
            if self._live_mode_enabled:
                self._broadcast_dashboard_update(call_site, dashboard_log)

            if call_site not in self._histograms:
                self._histograms[call_site] = []
                self._histograms_metadata[call_site] = (function_name, class_name)

            self._histograms[call_site].append(
                (num, stack_trace_id if stack_trace_id is not None else -1, log_index)
            )

    def timeline(self, event_name: str):
        """
        Record an event with a timestamp for timeline visualization.

        Args:
            event_name: Name of the event to record
        """
        self._ensure_initialized()
        with self._lock:
            import time

            call_site, _, function_name, class_name = (
                self._get_call_site_and_stack_trace()
            )

            # Assign log index for this invocation
            log_index = self._log_index
            self._log_index += 1

            # Capture stack trace if auto_stack_trace is enabled
            stack_trace_id: Optional[int] = None
            if self._config.auto_stack_trace:
                call_stack_obj = call_stack()
                trace = call_stack_obj.capture_stack_trace()
                # Use the log index as the stack trace ID
                stack_trace_id = log_index
                # Store the trace
                self._stack_traces[stack_trace_id] = trace

            # Store dashboard log entry
            if call_site not in self._dashboard_logs:
                self._dashboard_logs[call_site] = []

            timestamp = time.time()
            dashboard_log = {
                "log_index": log_index,
                "dashboard_type": "timeline",
                "function_name": function_name,
                "event_name": event_name,
                "timestamp": timestamp,
            }
            if class_name is not None:
                dashboard_log["class_name"] = class_name
            if stack_trace_id is not None:
                dashboard_log["stack_trace_id"] = stack_trace_id

            self._dashboard_logs[call_site].append(dashboard_log)

            # Broadcast update in live mode
            if self._live_mode_enabled:
                self._broadcast_dashboard_update(call_site, dashboard_log)

            event = {
                "timestamp": timestamp,
                "event_name": event_name,
                "call_site": call_site,
                "stack_trace_id": stack_trace_id,
                "log_index": log_index,
                "function_name": function_name,
                "class_name": class_name,
            }
            self._timeline.append(event)

    def happened(self, message: Optional[str] = None):
        """
        Record that this call site was invoked. Simply counts invocations.

        Args:
            message: Optional message to associate with this call site
        """
        self._ensure_initialized()
        with self._lock:
            call_site, _, function_name, class_name = (
                self._get_call_site_and_stack_trace()
            )

            # Assign log index for this invocation
            log_index = self._log_index
            self._log_index += 1

            # Capture stack trace if auto_stack_trace is enabled
            stack_trace_id: Optional[int] = None
            if self._config.auto_stack_trace:
                call_stack_obj = call_stack()
                trace = call_stack_obj.capture_stack_trace()
                # Use the log index as the stack trace ID
                stack_trace_id = log_index
                # Store the trace
                self._stack_traces[stack_trace_id] = trace

            # Store dashboard log entry
            if call_site not in self._dashboard_logs:
                self._dashboard_logs[call_site] = []

            dashboard_log = {
                "log_index": log_index,
                "dashboard_type": "happened",
                "function_name": function_name,
            }
            if class_name is not None:
                dashboard_log["class_name"] = class_name
            if stack_trace_id is not None:
                dashboard_log["stack_trace_id"] = stack_trace_id
            if message is not None:
                dashboard_log["message"] = message

            self._dashboard_logs[call_site].append(dashboard_log)

            # Broadcast update in live mode
            if self._live_mode_enabled:
                self._broadcast_dashboard_update(call_site, dashboard_log)

            if call_site not in self._happened:
                self._happened[call_site] = (0, [], message)
                self._happened_metadata[call_site] = (function_name, class_name)

            count, stack_trace_ids, stored_message = self._happened[call_site]
            # Update message if provided (use first non-None message)
            if stored_message is None and message is not None:
                stored_message = message

            if stack_trace_id is not None:
                stack_trace_ids.append((stack_trace_id, log_index))

            self._happened[call_site] = (count + 1, stack_trace_ids, stored_message)

    def init(self, config: Optional[ReportConfiguration] = None, clear: bool = False, warn: bool = True):
        """
        Initialize the report with a new configuration.

        Args:
            config: Optional configuration object. If None, uses default configuration.
            clear: If True, clears all existing data. If False (default), preserves existing data.
            warn: If True (default), warns to stderr when re-initializing with data.
                  If False, suppresses warnings (useful for tests).
        """
        with self._lock:
            # Check if there's any data that will be affected
            has_data = (self._logs or self._dashboard_logs or self._timeline or
                       self._happened or self._counts or self._histograms)

            if warn and self._initialized and has_data:
                if clear:
                    # Warn if clearing data
                    print(
                        "Warning: Report.init() clearing existing data.",
                        file=sys.stderr
                    )
                else:
                    # Warn if re-initializing with data (but not clearing)
                    print(
                        "Warning: Report.init() called on initialized report with existing data.",
                        file=sys.stderr
                    )

            if clear:
                # Clear all data
                self._logs.clear()
                self._log_index = 0
                self._stack_traces.clear()
                self._counts.clear()
                self._counts_metadata.clear()
                self._histograms.clear()
                self._histograms_metadata.clear()
                self._timeline.clear()
                self._happened.clear()
                self._happened_metadata.clear()
                self._dashboard_logs.clear()
                # Reset written flag since we cleared data
                self._written = False

            # Mark as initialized
            self._initialized = True

            # Update config
            if config is not None:
                self._config = config
            elif not self._initialized:
                # Only reset to default if not initialized yet
                self._config = ReportConfiguration()

            # Start live server if enabled
            if self._config.live_mode and not self._live_mode_enabled:
                self._live_mode_enabled = True
                try:
                    from autopsy import live_server
                    live_server.start_server(
                        self._config.live_mode_host,
                        self._config.live_mode_port
                    )
                except Exception as e:
                    print(f"Warning: Failed to start live server: {type(e).__name__}: {e}")
                    print("Install dependencies with: uv pip install -e '.[live]'")
                    self._live_mode_enabled = False

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
        # Stack trace ID is the same as log index
        return self._stack_traces.get(log_index)

    def to_json(self) -> Dict[str, Any]:
        """
        Convert report data to JSON-serializable format.

        Returns:
            Dictionary with 'generated_at' timestamp and 'call_sites' key containing
            list of call site data. Each call site has 'filename', 'line', and 'value_groups' keys.
            Each value_group is a list of values from one log() call.
        """
        with self._lock:
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
                    if "name" in log_group:
                        value_group_data["name"] = log_group["name"]
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

            # Add dashboard call sites to call_sites list
            for call_site, dashboard_logs in self._dashboard_logs.items():
                filename, line_number = call_site

                # Process each dashboard log entry
                json_value_groups = []
                for dashboard_log in dashboard_logs:
                    dashboard_type = dashboard_log.get("dashboard_type", "unknown")

                    # Create value group based on dashboard type
                    value_group_data = {
                        "log_index": dashboard_log.get("log_index", 0),
                        "function_name": dashboard_log.get("function_name", "<unknown>"),
                        "dashboard_type": dashboard_type,
                    }
                    if "class_name" in dashboard_log:
                        value_group_data["class_name"] = dashboard_log["class_name"]
                    if "stack_trace_id" in dashboard_log:
                        value_group_data["stack_trace_id"] = str(
                            dashboard_log["stack_trace_id"]
                        )

                    # Add type-specific data
                    if dashboard_type == "count":
                        value_group_data["value"] = self._to_json_serializable(
                            dashboard_log.get("value")
                        )
                    elif dashboard_type == "hist":
                        value_group_data["value"] = dashboard_log.get("value")
                    elif dashboard_type == "timeline":
                        value_group_data["event_name"] = dashboard_log.get("event_name")
                        value_group_data["timestamp"] = dashboard_log.get("timestamp")
                    elif dashboard_type == "happened":
                        if "message" in dashboard_log:
                            value_group_data["message"] = dashboard_log["message"]

                    json_value_groups.append(value_group_data)

                call_site_data = {
                    "filename": filename,
                    "line": line_number,
                    "function_name": (
                        dashboard_logs[0].get("function_name", "<unknown>")
                        if dashboard_logs
                        else "<unknown>"
                    ),
                    "value_groups": json_value_groups,
                    "is_dashboard": True,
                }
                if dashboard_logs and "class_name" in dashboard_logs[0]:
                    call_site_data["class_name"] = dashboard_logs[0]["class_name"]
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

            # Serialize dashboard data
            dashboard_data = {}

            # Serialize counts
            json_counts = []
            for call_site, value_counts in self._counts.items():
                filename, line_number = call_site
                # Get function name from stored metadata
                function_name, class_name = self._counts_metadata.get(
                    call_site, ("<unknown>", None)
                )

                # Convert value_counts to JSON-serializable format
                json_value_counts = {}
                for value_key, stack_trace_data in value_counts.items():
                    # stack_trace_data is now a list of (stack_trace_id, log_index) tuples
                    # Filter out -1 sentinel values (used when stack traces are disabled)
                    stack_trace_ids = [str(st_id) for st_id, _ in stack_trace_data if st_id != -1]
                    log_indices = [log_idx for _, log_idx in stack_trace_data]

                    # value_key might already be a JSON string (for unhashable types)
                    # or it might be the original value (for hashable types)
                    # Check if it's already a valid JSON string by trying to parse it
                    if isinstance(value_key, str):
                        try:
                            # Try to parse as JSON - if it succeeds, it's already a JSON string
                            json.loads(value_key)
                            # Already a JSON string, use it directly
                            json_value_counts[value_key] = {
                                "count": len(stack_trace_data),
                                "stack_trace_ids": stack_trace_ids,
                                "log_indices": log_indices,
                            }
                            continue
                        except (json.JSONDecodeError, ValueError):
                            # Not a JSON string, treat as regular string value
                            pass

                    # Convert value to JSON-serializable format
                    json_value = self._to_json_serializable(value_key)
                    json_value_counts[json.dumps(json_value, sort_keys=True)] = {
                        "count": len(stack_trace_data),
                        "stack_trace_ids": stack_trace_ids,
                        "log_indices": log_indices,
                    }

                count_entry = {
                    "call_site": {
                        "filename": filename,
                        "line": line_number,
                        "function_name": function_name,
                    },
                    "value_counts": json_value_counts,
                }
                if class_name is not None:
                    count_entry["call_site"]["class_name"] = class_name
                json_counts.append(count_entry)

            # Serialize histograms
            json_histograms = []
            for call_site, values in self._histograms.items():
                filename, line_number = call_site
                # Get function name from stored metadata
                function_name, class_name = self._histograms_metadata.get(
                    call_site, ("<unknown>", None)
                )

                json_values = []
                for num, stack_trace_id, log_index in values:
                    json_values.append(
                        {
                            "value": num,
                            "stack_trace_id": (
                                str(stack_trace_id) if stack_trace_id != -1 else None
                            ),
                            "log_index": log_index,
                        }
                    )

                hist_entry = {
                    "call_site": {
                        "filename": filename,
                        "line": line_number,
                        "function_name": function_name,
                    },
                    "values": json_values,
                }
                if class_name is not None:
                    hist_entry["call_site"]["class_name"] = class_name
                json_histograms.append(hist_entry)

            # Serialize timeline (sort by timestamp)
            json_timeline = []
            sorted_timeline = sorted(self._timeline, key=lambda x: x["timestamp"])
            for event in sorted_timeline:
                call_site = event["call_site"]
                filename, line_number = call_site
                # Get function name from stored metadata in event
                function_name = event.get("function_name", "<unknown>")
                class_name = event.get("class_name")

                timeline_entry = {
                    "timestamp": event["timestamp"],
                    "event_name": event["event_name"],
                    "call_site": {
                        "filename": filename,
                        "line": line_number,
                        "function_name": function_name,
                    },
                    "stack_trace_id": (
                        str(event["stack_trace_id"])
                        if event["stack_trace_id"] is not None
                        else None
                    ),
                    "log_index": event.get("log_index"),
                }
                if class_name is not None:
                    timeline_entry["call_site"]["class_name"] = class_name
                json_timeline.append(timeline_entry)

            # Serialize happened
            json_happened = []
            for call_site, (count, stack_trace_data, message) in self._happened.items():
                filename, line_number = call_site
                # Get function name from stored metadata
                function_name, class_name = self._happened_metadata.get(
                    call_site, ("<unknown>", None)
                )
                # stack_trace_data is now a list of (stack_trace_id, log_index) tuples
                # Filter out -1 sentinel values (used when stack traces are disabled)
                stack_trace_ids = [str(st_id) for st_id, _ in stack_trace_data if st_id != -1]
                log_indices = [log_idx for _, log_idx in stack_trace_data]

                happened_entry = {
                    "call_site": {
                        "filename": filename,
                        "line": line_number,
                        "function_name": function_name,
                    },
                    "count": count,
                    "stack_trace_ids": stack_trace_ids,
                    "log_indices": log_indices,
                }
                if class_name is not None:
                    happened_entry["call_site"]["class_name"] = class_name
                if message is not None:
                    happened_entry["message"] = message
                json_happened.append(happened_entry)

            # Only include dashboard if there's any data
            if json_counts or json_histograms or json_timeline or json_happened:
                dashboard_data = {
                    "counts": json_counts,
                    "histograms": json_histograms,
                    "timeline": json_timeline,
                    "happened": json_happened,
                }

            result = {
                "generated_at": datetime.now().isoformat(),
                "call_sites": call_sites,
                "stack_traces": json_stack_traces,
            }

            if dashboard_data:
                result["dashboard"] = dashboard_data

            return result

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

    def _broadcast_log_update(
        self, call_site: Tuple[str, int], log_group: dict, stack_trace_id: Optional[int]
    ):
        """Broadcast a log update to all WebSocket clients."""
        if not self._live_mode_enabled:
            return

        try:
            from autopsy import live_server

            filename, line = call_site

            # Prepare value group for JSON serialization - must match to_json format
            pickled_values = log_group.get("values", [])
            arg_names = log_group.get("arg_names", [])
            json_values = []

            # Build values array matching the snapshot format
            for idx, pickled_value in enumerate(pickled_values):
                value_data = {}

                # Add argument name if available
                if idx < len(arg_names) and arg_names[idx] is not None:
                    value_data["name"] = arg_names[idx]

                # Deserialize and convert value
                if isinstance(pickled_value, str) and pickled_value.startswith("<PickleError:"):
                    value_data["value"] = pickled_value
                elif isinstance(pickled_value, bytes):
                    try:
                        unpickled = pickle.loads(pickled_value)
                        value_data["value"] = self._to_json_serializable(unpickled)
                    except Exception as e:
                        value_data["value"] = f"<UnpickleError: {str(e)}>"
                else:
                    value_data["value"] = self._to_json_serializable(pickled_value)

                json_values.append(value_data)

            # Build value_group matching the snapshot format
            value_group = {
                "values": json_values,
                "function_name": log_group.get("function_name", "<unknown>"),
                "log_index": log_group.get("log_index", 0),
            }

            if "class_name" in log_group:
                value_group["class_name"] = log_group["class_name"]
            if "stack_trace_id" in log_group:
                value_group["stack_trace_id"] = str(log_group["stack_trace_id"])
            if "name" in log_group:
                value_group["name"] = log_group["name"]

            # Prepare incremental update
            update = {
                "type": "log",
                "call_site": {
                    "filename": filename,
                    "line": line,
                    "function_name": log_group.get("function_name"),
                    "class_name": log_group.get("class_name"),
                },
                "value_group": value_group,
            }

            # Add stack trace if present
            if stack_trace_id is not None and stack_trace_id in self._stack_traces:
                stack_trace = self._stack_traces[stack_trace_id]
                update["stack_trace"] = {
                    str(stack_trace_id): {
                        "frames": [
                            {
                                "filename": frame.filename,
                                "line_number": frame.line_number,
                                "function_name": frame.function_name,
                                "code_context": frame.code_context,
                                "local_variables": frame.local_variables,
                            }
                            for frame in stack_trace.frames
                        ],
                        "timestamp": stack_trace.timestamp,
                    }
                }

            # Queue broadcast
            live_server.queue_broadcast(update)
        except Exception as e:
            # Silently fail if broadcast fails
            print(f"Warning: Failed to broadcast log update: {e}")

    def _broadcast_dashboard_update(
        self, call_site: Tuple[str, int], dashboard_log: dict
    ):
        """Broadcast a dashboard update (count/hist/timeline/happened) to all WebSocket clients."""
        if not self._live_mode_enabled:
            return

        try:
            from autopsy import live_server

            filename, line = call_site
            dashboard_type = dashboard_log.get("dashboard_type", "unknown")

            # Build value_group matching the snapshot format for dashboard items
            value_group_data = {
                "log_index": dashboard_log.get("log_index", 0),
                "function_name": dashboard_log.get("function_name", "<unknown>"),
                "dashboard_type": dashboard_type,
            }

            if "class_name" in dashboard_log:
                value_group_data["class_name"] = dashboard_log["class_name"]
            if "stack_trace_id" in dashboard_log:
                value_group_data["stack_trace_id"] = str(dashboard_log["stack_trace_id"])

            # Add type-specific data
            if dashboard_type == "count":
                value_group_data["value"] = self._to_json_serializable(
                    dashboard_log.get("value")
                )
            elif dashboard_type == "hist":
                value_group_data["value"] = dashboard_log.get("value")
            elif dashboard_type == "timeline":
                value_group_data["event_name"] = dashboard_log.get("event_name")
                value_group_data["timestamp"] = dashboard_log.get("timestamp")
            elif dashboard_type == "happened":
                if "message" in dashboard_log:
                    value_group_data["message"] = dashboard_log["message"]

            # Prepare incremental update
            update = {
                "type": dashboard_type,
                "call_site": {
                    "filename": filename,
                    "line": line,
                    "function_name": dashboard_log.get("function_name"),
                    "class_name": dashboard_log.get("class_name"),
                },
                "value_group": value_group_data,
            }

            # Add stack trace if present
            stack_trace_id = dashboard_log.get("stack_trace_id")
            if stack_trace_id is not None and stack_trace_id in self._stack_traces:
                stack_trace = self._stack_traces[stack_trace_id]
                update["stack_trace"] = {
                    str(stack_trace_id): {
                        "frames": [
                            {
                                "filename": frame.filename,
                                "line_number": frame.line_number,
                                "function_name": frame.function_name,
                                "code_context": frame.code_context,
                                "local_variables": frame.local_variables,
                            }
                            for frame in stack_trace.frames
                        ],
                        "timestamp": stack_trace.timestamp,
                    }
                }

            # Queue broadcast
            live_server.queue_broadcast(update)
        except Exception as e:
            # Silently fail if broadcast fails
            print(f"Warning: Failed to broadcast dashboard update: {e}")


# Global singleton instance
_report_instance = Report()


def get_report() -> Report:
    """Get the global report instance."""
    return _report_instance


def init(config: Optional[ReportConfiguration] = None, clear: bool = False, warn: bool = True):
    """
    Initialize the global report instance.

    Args:
        config: Optional configuration object. If None, uses default configuration.
        clear: If True, clears all existing data. If False (default), preserves existing data.
        warn: If True (default), warns to stderr when re-initializing with data.
              If False, suppresses warnings (useful for tests).
    """
    _report_instance.init(config, clear=clear, warn=warn)


# Global flag to control atexit behavior
_atexit_enabled = True


def set_atexit_enabled(enabled: bool):
    """
    Enable or disable the automatic report writing on exit.

    Args:
        enabled: If True, enables automatic HTML report generation on exit.
                 If False, disables it (useful for tests).
    """
    global _atexit_enabled
    _atexit_enabled = enabled


def _atexit_handler():
    """
    Automatically write out HTML report if:
    1. The report was initialized (had at least one log call)
    2. The report was not already written to a file
    3. We're not in live mode
    4. Atexit is enabled (not disabled for tests)
    """
    if not _atexit_enabled:
        # Disabled (e.g., for tests)
        return

    if not _report_instance._initialized:
        # Report was never used, nothing to do
        return

    if _report_instance._written:
        # Report was already written, nothing to do
        return

    if _report_instance._config.live_mode:
        # In live mode, don't auto-write
        return

    # Check if there's any data to write
    if (not _report_instance._logs and
        not _report_instance._dashboard_logs and
        not _report_instance._timeline and
        not _report_instance._happened):
        # No data collected, nothing to write
        return

    # Auto-generate HTML report with default filename
    output_path = "autopsy_report.html"
    try:
        generate_html(_report_instance, output_path)
        print(f"\n→ Autopsy report automatically saved to {output_path}", file=sys.stderr)
    except Exception as e:
        print(f"\nWarning: Failed to auto-generate autopsy report: {e}", file=sys.stderr)


# Register atexit handler
atexit.register(_atexit_handler)


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

    # Compress JSON data with gzip and encode as base64
    json_bytes = json_str.encode("utf-8")
    compressed_bytes = gzip.compress(json_bytes, compresslevel=9)
    compressed_base64 = base64.b64encode(compressed_bytes).decode("ascii")

    # Inject compressed JSON into the template
    # Find and replace the content of the <script id="autopsy-data"> tag
    # Change type to indicate compression
    pattern = r'(<script id="autopsy-data" type="application/json">)(.*?)(</script>)'
    replacement = (
        r'<script id="autopsy-data" type="application/json" data-compressed="gzip">'
        + compressed_base64
        + r"</script>"
    )
    html_content = re.sub(pattern, replacement, template_content, flags=re.DOTALL)

    # Write to file if output_path is provided
    if output_path is not None:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(html_content, encoding="utf-8")
        # Mark report as written
        report._written = True

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
        # Mark report as written
        report._written = True

    return json_str
