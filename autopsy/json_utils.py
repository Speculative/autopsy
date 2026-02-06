"""Shared JSON serialization utilities.

Provides a single, canonical function for converting Python values to
JSON-safe representations. Both report.py and call_stack.py delegate
to this module so that concerns like float('inf') handling live in
exactly one place.
"""

import json
import math
from typing import Any, Union


def sanitize_float(value: float) -> Union[float, str]:
    """Convert non-finite float values to JSON-safe string representations.

    Standard JSON does not support Infinity, -Infinity, or NaN. This function
    converts those to string representations while passing through normal
    float values unchanged.

    Args:
        value: A float value to sanitize.

    Returns:
        The original float if finite, or a string ("Infinity", "-Infinity",
        "NaN") if not.
    """
    if math.isinf(value):
        return "Infinity" if value > 0 else "-Infinity"
    elif math.isnan(value):
        return "NaN"
    return value


def to_json_serializable(value: Any) -> Any:
    """Convert a Python value to a JSON-serializable representation.

    Handles special float values (inf, -inf, NaN), recursively processes
    compound types (lists, tuples, dicts), and falls back to a string
    representation for anything else that json.dumps cannot handle.

    Args:
        value: Value to convert.

    Returns:
        A JSON-serializable representation of the value.
    """
    if isinstance(value, float):
        return sanitize_float(value)

    if isinstance(value, (list, tuple)):
        return [to_json_serializable(item) for item in value]
    elif isinstance(value, dict):
        return {str(k): to_json_serializable(v) for k, v in value.items()}

    if isinstance(value, (int, str, bool, type(None))):
        return value

    # For other types, test whether json.dumps can handle them directly.
    try:
        json.dumps(value, allow_nan=False)
        return value
    except (TypeError, ValueError, OverflowError):
        try:
            return f"<{type(value).__name__}: {repr(value)}>"
        except Exception:
            return f"<{type(value).__name__}: (unable to represent)>"
