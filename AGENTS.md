# Design

`autopsy` consists of a core of classes that store information relevant to
debugging and imperative top-level APIs that create and modify objects of these
classes.

## Call Stack

CallStack provides a fluent-style API that enables convenient access to common
debugging information that a programmer might need. When initialized, it
captures the current stack frames, though these are live references and are
subject to the values changing, we assume that the programmer is generally not
mutating state in between constructing the call stack and querying it. This
allows the querying APIs to be "lazy" insofar as we don't actually capture any
information from the call stack until the user asks for it by calling one of
the querying APIs. We do this because actually capturing an immutable call
stack is expensive.

CallStack and its related classes never invoke side effects and never directly
read environment or platform-specific information. Instead, it should be passed
in to them as necessary by the functions implementing the top-level APIs.

### AutopsyResult Pattern

CallStack's fluent API uses the `AutopsyResult` Result Monad pattern to enable
chaining calls even if a queried value isn't present. All querying methods
(e.g., `current`, `caller`, `frame()`) return `AutopsyResult[T]` instead of
`Optional[T]`. This allows chaining like `call_stack.caller.variable("x")`
without raising exceptions when intermediate steps fail.

`AutopsyResult` provides:

- `is_ok()` and `is_err()` methods to check success/failure
- `.value` property to access the wrapped value (raises if error)
- `.error` property to access error information (raises if success)
- Fluent chaining via `__getattr__` that propagates errors through the chain
- Structured error information via `ErrorInfo` containing message, context, and code location

When a query fails (e.g., no caller available), an `ErrorInfo` object is
created with:

- A human-readable error message
- Contextual information (e.g., available frames, required frames, frame index)
- Code location where the error occurred (filename, line number, function, module)

This pattern will be used for all future CallStack querying classes to ensure
consistent error handling and fluent chaining throughout the API.

## Report

Report is effectively an in-memory, append-only database that accumulates
information passed in to it from the imperative top-level API. It also provides
simple getters that are used to generate human-readable output reports (to the
console as well as to formatted output files).

# Tooling

- `uv` for dependencies and running scripts. Always use `uv run python -m <module>` when running scripts.
- `uvx ruff` for formatting and linting. Always run `uvx ruff format` and `uvx ruff check` after completing work.
- `pytest` for tests. Always run tests when you think a change is complete.
