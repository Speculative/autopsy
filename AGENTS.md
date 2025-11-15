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

CallStack's fluent API should allow chaining calls even if a queried value
isn't present, e.g. `call_stack.caller().variables()` should not raise an
exception and instead collect a message representing where the missing value was
so that this can be surfaced to the user in the report.

## Report

Report is effectively an in-memory, append-only database that accumulates
information passed in to it from the imperative top-level API. It also provides
simple getters that are used to generate human-readable output reports (to the
console as well as to formatted output files).

# Tooling

- `uv` for dependencies and running scripts. Always use `uv run python -m <module>` when running scripts.
- `ruff` for formatting and linting
- `pytest` for tests
