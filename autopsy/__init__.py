from autopsy.report import get_report
from autopsy.call_stack import call_stack

# Export the report singleton
report = get_report()

# Export call_stack
__all__ = ['report', 'call_stack']

