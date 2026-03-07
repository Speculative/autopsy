"""
Study alias: 'tracer' is the de-identified name for autopsy.
This module re-exports everything from autopsy so that
`from tracer import report` works identically to `from autopsy import report`.

Remove this package after the study is complete.
"""

from autopsy import (
    Report,
    ReportConfiguration,
    call_stack,
    count,
    generate_html,
    generate_json,
    get_report,
    happened,
    hist,
    init,
    log,
    report,
    set_atexit_enabled,
    timeline,
)

__all__ = [
    "report",
    "call_stack",
    "log",
    "count",
    "hist",
    "timeline",
    "happened",
    "init",
    "generate_html",
    "generate_json",
    "Report",
    "ReportConfiguration",
    "get_report",
    "set_atexit_enabled",
    "pytest",
]
