"""
Simplified print-style logging for study ablation condition.
Wraps autopsy's report.log() with stack trace capture disabled.

Usage:
    from logger import print
    print(my, arguments)

This module is designed to be easy to remove after the study is complete.
"""

from autopsy.report import get_report

_report = get_report()


def log(*args):
    """Print-style logging that captures argument values only (no call stacks)."""
    _report._ensure_initialized()
    old = _report._config.auto_stack_trace
    _report._config.auto_stack_trace = False
    try:
        _report.log(*args)
    finally:
        _report._config.auto_stack_trace = old
