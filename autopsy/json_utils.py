"""Shared JSON serialization utilities."""

import math
from typing import Union


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
