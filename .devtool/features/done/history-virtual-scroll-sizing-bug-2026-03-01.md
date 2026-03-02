---
id: "history-virtual-scroll-sizing-bug-2026-03-01"
status: "done"
priority: "medium"
assignee: null
dueDate: null
created: "2026-03-01T18:35:00.175Z"
modified: "2026-03-01T21:30:00.000Z"
completedAt: "2026-03-01T21:30:00.000Z"
labels: []
order: "a3"
---
# History virtual scroll sizing bug

We have an issue with the virtualized History view where expanding objects causes list item heights to change (expected and good), but then scrolling causes items to be the wrong heights or out of place (big gaps between consecutive items).

First, write an e2e test to reproduce this bug (make the e2e test also assert things about scrolling the virtualized list showing the right elements, being able to see all elements, no elements being cut off).

Then, fix the bug.
