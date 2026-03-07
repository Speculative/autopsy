---
id: "de-identify-autopsyprint-ablation-2026-03-01"
status: "done"
priority: "medium"
assignee: null
dueDate: null
created: "2026-03-01T21:52:05.743Z"
modified: "2026-03-07T04:01:56.759Z"
completedAt: "2026-03-07T04:01:56.759Z"
labels: []
order: "a5"
---
# De-identify autopsy/print ablation

For our study, to avoid demand characteristics where participants can tell which tool is the one we developed (and therefore which one we want to see do well), we should "anonymize" autopsy by giving it a more generic name.

We'll call autopsy "tracer". We should call the print ablation "logger". Breakpoints can still be breakpoints (but the user will never see anything related to this).

We do not need to change our metrics instrumentation. We only need to change user-facing surfaces.

We need to change any references to autopsy in the web app (I don't think there should be many), the VS Code extension (as far as I'm aware, the command palette, the tab name, the CodeLens), and the reporting library (it should be `import tracer` and `import logger`). The command palette commands should be called "Open Tracer Viewer" and "Open Logger Viewer"

We should make this change easy to revert or, failing a clean revert, at least easy to rip out later when we're done with the study.