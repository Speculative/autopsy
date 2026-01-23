from autopsy.report import (
    Report,
    ReportConfiguration,
    generate_html,
    generate_json,
    get_report,
    init,
    set_atexit_enabled,
)
from autopsy.call_stack import call_stack

# Export the report singleton
report = get_report()

# Expose all public Report methods as module-level functions
# These will use the global singleton report instance
def log(*args, **kwargs):
    """Capture values at the current call site using the global report."""
    return report.log(*args, **kwargs)

def count(value):
    """Collect a value and count occurrences using the global report."""
    return report.count(value)

def hist(num):
    """Collect a number for histogram using the global report."""
    return report.hist(num)

def timeline(event_name):
    """Record a timeline event using the global report."""
    return report.timeline(event_name)

def happened(message=None):
    """Record that this call site was invoked using the global report."""
    return report.happened(message)

# Export call_stack
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
]
