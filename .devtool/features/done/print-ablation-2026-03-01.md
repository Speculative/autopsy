---
id: "print-ablation-2026-03-01"
status: "done"
priority: "medium"
assignee: null
dueDate: null
created: "2026-03-01T19:02:19.730Z"
modified: "2026-03-07T04:01:52.499Z"
completedAt: "2026-03-07T04:01:52.500Z"
labels: []
order: "a4"
---
# print ablation

For our study, we want a version of "print debugging" that's normalized to use the autopsy History view with all of the other features turned off.

This will be tricky and we need to enter plan mode to consider how to do this carefully. The option I'm envisioning:

- Maintain some global state or parameter about mode
- Add an extension command palette command to "Open Logger Viewer"
- Change the existing command palette command to "Open Tracer Viewer"
- Depending on which way it's opened, set the global state
- Using the global state, apply gates on interactions that would show them other features

The features that they should retain access to:

- The history view
- Hovering to see parameter names
- Clicking on code locations to jump back to them

List of features (possibly incomplete) that definitely shouldn't be accessed:

- Clicking log entries to see call stacks
- Jump to log in stream
- The entire view switcher tab bar
- Computed columns
- Test view
- Dashboard view
- The step debugging feature (show code -&gt; jumping to next/previous log)
- The view filter icon
- The HistoryView checkboxes for showing dashboard calls and skipped logs

Since we're hiding even the tab bar, it may be good to introduce a level at the top of App.svelte that switches on the condition and shows basically a completely separate log-only view. We aren't going to be having any more code changes before the study, so maybe the safest option is just to completely copy HistoryView and make a PrintView component for the ablation.

Their programmatic logging interface should look like

```
from logger import print
...
print(my, arguments)
```

We don't even want to capture complete call stacks when we're using this ablation. print(my, arguments) should only capture the argument values and no other variables.

Lastel, we want this code to be easy to rip out later when the study is complete.