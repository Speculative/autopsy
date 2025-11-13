# Design
`autopsy` consists of a core of classes that store information relevant to
debugging and imperative top-level APIs that create and modify objects of these
classes.

## Call Stack
CallStack provides a set of immutable data structures with a fluent-style API
that enables convenient access to common debugging information that a
programmer might need.

CallStack and its related classes never invoke side effects and never directly
read environment or platform-specific information. Instead, it should be passed
in to them as necessary by the functions implementing the top-level APIs.

## Report
Report is effectively an in-memory, append-only database that accumulates
information passed in to it from the imperative top-level API. It also provides
simple getters that are used to generate human-readable output reports (to the
console as well as to formatted output files).

# Tooling
 - `uv` for dependencies
 - `ruff` for formatting and linting
 - `pytest` for tests