---
id: "fix-test-view-dropdown-2026-02-27"
status: "todo"
priority: "medium"
assignee: null
dueDate: null
created: "2026-02-27T23:20:38.194Z"
modified: "2026-02-27T23:20:38.194Z"
completedAt: null
labels: []
order: "a1"
---
# Fix test view dropdown

When there are multiple tests in the test view, the ... dropdown ends up occluded because it can't overflow the boundary of the test it belongs to, when it should be a dropdown that overlays the test and is allowed to pop out.