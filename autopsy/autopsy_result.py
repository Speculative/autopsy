import inspect
import os
from dataclasses import dataclass
from typing import Any, Dict, Generic, List, Optional, TypeVar

T = TypeVar("T")
U = TypeVar("U")


@dataclass
class Location:
    """Code location information."""

    filename: str
    lineno: int
    function: str
    module: str

    def __repr__(self) -> str:
        return (
            f"Location({self.filename}:{self.lineno} in {self.module}.{self.function})"
        )


def _capture_error_location(
    autopsy_module_path: str, stack: List[inspect.FrameInfo]
) -> Location:
    """
    Capture the code location where an error occurred, excluding autopsy frames.

    Args:
        autopsy_module_path: Path to the autopsy module directory
        stack: List of FrameInfo objects from inspect.stack()

    Returns:
        Location object with filename, lineno, function, and module information
    """
    # Find the first non-autopsy frame
    for frame_info in stack:
        frame_path = os.path.abspath(frame_info.filename)
        is_autopsy_package = frame_path.startswith(autopsy_module_path)

        if not is_autopsy_package:
            frame = frame_info.frame
            module = frame.f_globals.get("__name__", "<unknown>")
            return Location(
                filename=frame_info.filename,
                lineno=frame_info.lineno,
                function=frame_info.function,
                module=module,
            )

    # Fallback if we can't find a non-autopsy frame
    if stack:
        frame_info = stack[0]
        frame = frame_info.frame
        module = frame.f_globals.get("__name__", "<unknown>")
        return Location(
            filename=frame_info.filename,
            lineno=frame_info.lineno,
            function=frame_info.function,
            module=module,
        )

    return Location(
        filename="<unknown>",
        lineno=0,
        function="<unknown>",
        module="<unknown>",
    )


class ErrorInfo:
    """Structured error information with message, context, and location."""

    def __init__(self, message: str, context: Dict[str, Any], location: Location):
        """
        Initialize error information.

        Args:
            message: Human-readable error message
            context: Additional context (e.g., frame_index, available_frames, etc.)
            location: Code location where error occurred
        """
        self.message = message
        self.context = context
        self.location = location

    def __repr__(self) -> str:
        loc_str = f"{self.location.filename}:{self.location.lineno}"
        return (
            f"ErrorInfo({self.message!r}, context={self.context}, location={loc_str})"
        )


class _AttributeProxy:
    """
    Proxy object that wraps attribute access to support fluent chaining.

    When an AutopsyResult has an error, accessing attributes returns proxies
    that propagate the error instead of accessing the underlying attribute.
    """

    def __init__(self, result: "AutopsyResult[Any]", attr_name: str):
        self._result = result
        self._attr_name = attr_name

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """
        Call the method, propagating errors if present.

        If the result is an error, returns an AutopsyResult wrapping the error.
        If the result is ok, calls the method and wraps the result in AutopsyResult.

        Note: This wraps non-AutopsyResult return values in AutopsyResult.ok().
        If the method already returns AutopsyResult, it's returned as-is (errors propagate).
        """
        if self._result.is_err():
            # Propagate the error - return the same error result
            # We need to return it as AutopsyResult[Any] since we don't know the return type
            return self._result

        attr = getattr(self._result.value, self._attr_name)
        if not callable(attr):
            raise AttributeError(
                f"'{type(self._result.value).__name__}.{self._attr_name}' is not callable"
            )

        # Call the method
        result_value = attr(*args, **kwargs)

        # If it already returns an AutopsyResult, return it as-is (errors propagate)
        if isinstance(result_value, AutopsyResult):
            return result_value

        # Otherwise, wrap it in AutopsyResult.ok()
        # This allows chaining: call_stack.caller.variable("x") works
        # When Variable is refactored to AutopsyResult[Variable], this will still work
        return AutopsyResult.ok(result_value)

    def __getattr__(self, name: str) -> Any:
        """
        Support chaining on properties.

        If the underlying result is an error, propagate it by returning a new proxy.
        Otherwise, access the property on the wrapped value.
        """
        if self._result.is_err():
            # Return a new proxy that will propagate the error
            return _AttributeProxy(self._result, name)

        # Access the attribute on the wrapped value
        attr = getattr(self._result.value, self._attr_name)

        # If it's a property that returns AutopsyResult, access the nested property
        if isinstance(attr, AutopsyResult):
            nested_attr = getattr(attr, name, None)
            if nested_attr is not None:
                return nested_attr
            # If not found, return a proxy for chaining
            return _AttributeProxy(attr, name)

        # If the attribute itself is callable, return a proxy
        if callable(attr):
            return _AttributeProxy(self._result, name)

        # Otherwise, try to access the nested attribute
        nested_attr = getattr(attr, name, None)
        if nested_attr is not None:
            return nested_attr

        raise AttributeError(
            f"'{type(self._result.value).__name__}.{self._attr_name}' has no attribute '{name}'"
        )


class AutopsyResult(Generic[T]):
    """
    Result Monad pattern for Autopsy operations.

    Enables fluent-style chaining even when intermediate operations fail,
    without raising exceptions.
    """

    __match_args__ = ("_value", "_error")

    def __init__(self, value: Optional[T] = None, error: Optional[ErrorInfo] = None):
        """
        Initialize an AutopsyResult.

        Args:
            value: The success value (if ok)
            error: The error information (if err)

        Note: Use ok() or err() class methods instead of calling this directly.
        """
        if value is not None and error is not None:
            raise ValueError("Cannot have both value and error")
        if value is None and error is None:
            raise ValueError("Must have either value or error")

        self._value: Optional[T] = value
        self._error: Optional[ErrorInfo] = error

    @classmethod
    def ok(cls, value: T) -> "AutopsyResult[T]":
        """Create a successful result."""
        return cls(value=value, error=None)

    @classmethod
    def err(cls, error: ErrorInfo) -> "AutopsyResult[T]":
        """Create an error result."""
        return cls(value=None, error=error)

    def is_ok(self) -> bool:
        """Check if this is a successful result."""
        return self._error is None

    def is_err(self) -> bool:
        """Check if this is an error result."""
        return self._error is not None

    @property
    def value(self) -> T:
        """Get the value, raising an error if this is an error result."""
        if self._error is not None:
            raise ValueError(
                f"Cannot access value of error result: {self._error.message}"
            )
        assert self._value is not None
        return self._value

    @property
    def error(self) -> ErrorInfo:
        """Get the error information, raising an error if this is a success result."""
        if self._error is None:
            raise ValueError("Cannot access error of success result")
        return self._error

    def __getattr__(self, name: str) -> Any:
        """
        Support fluent-style chaining by forwarding attribute access to the wrapped value.

        If this is an error result, returns a proxy that propagates the error.
        If this is a success result, forwards the attribute access to the value.

        Note: This enables chaining like `result.caller.variable("x")` even when
        intermediate steps fail. However, type inference may be limited for chained
        attribute accesses - type checkers will see this as returning `Any`.

        For better type inference, consider accessing `.value` explicitly:
        `result.value.variable("x")` instead of `result.variable("x")`.
        """
        if self.is_err():
            # Return a proxy that will propagate the error when called or accessed
            return _AttributeProxy(self, name)

        # Check if the attribute is a property descriptor first
        value_type = type(self._value)
        if hasattr(value_type, name):
            class_attr = getattr(value_type, name)
            # If it's a property descriptor, access it directly (don't wrap)
            if isinstance(class_attr, property):
                return getattr(self._value, name)

        # Forward to the wrapped value
        attr = getattr(self._value, name)

        # If it's a method (callable but not a property), wrap it in a proxy
        if callable(attr):
            return _AttributeProxy(self, name)

        # For properties/attributes:
        # - If it returns an AutopsyResult, return it as-is (errors will propagate naturally)
        # - Otherwise, return it directly
        if isinstance(attr, AutopsyResult):
            return attr

        return attr

    def __repr__(self) -> str:
        if self.is_ok():
            return f"AutopsyResult.ok({self._value!r})"
        return f"AutopsyResult.err({self._error!r})"
