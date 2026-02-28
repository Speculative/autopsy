---
id: "stream-table-doesnt-resize-when-hiding-columns-2026-02-27"
status: "done"
priority: "medium"
assignee: null
dueDate: null
created: "2026-02-28T02:42:23.927Z"
modified: "2026-02-28T03:05:00.000Z"
completedAt: "2026-02-28T03:05:00.000Z"
labels: []
order: "a3"
---
# Stream table doesn't resize when hiding columns

Check if we have e2e tests asserting that the table is always at least the width of the available space. Add cases for adding columns, removing columns, opening the call stack panel, resizing the window to be bigger/smaller

Then, fix the bug by making sure that hiding columns causes the table to resize to fill the available space