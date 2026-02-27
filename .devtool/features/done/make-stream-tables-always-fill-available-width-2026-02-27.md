---
id: "make-stream-tables-always-fill-available-width-2026-02-27"
status: "done"
priority: "medium"
assignee: null
dueDate: null
created: "2026-02-27T23:14:22.862Z"
modified: "2026-02-28T00:35:00.000Z"
completedAt: "2026-02-28T00:35:00.000Z"
labels: []
order: "a0"
---
# Make stream tables always fill available width

Currently, the tables in the stream view only determine automatic sizing once when the tab loads. This means that if the available width changes, the table becomes an inappropriate size. This could be when the window resizes, or when the call stack panel is opened.

## Implementation

Implemented responsive table width handling using ResizeObserver:

1. Added `containerWidths` state to track container dimensions
2. Added a ResizeObserver effect that:
   - Watches all table containers for size changes
   - Only triggers recalculation when width changes significantly (>10px threshold to avoid jitter)
   - Skips recalculation when user is manually resizing columns
3. Modified the existing column width initialization effect to recalculate whenever widths are cleared
4. Tables now automatically adjust their column widths when:
   - Window is resized
   - Call stack panel is opened/closed
   - Any container dimension changes

All existing e2e tests pass successfully.