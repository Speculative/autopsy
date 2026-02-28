---
name: do-item
description: Execute a kanban board item end-to-end. Mark the item as in-progress, work on completing its requirements, then mark it as done. Takes a @mentioned kanban item file as an argument.
---

# Do Item

Execute a single kanban board item from start to completion. This skill handles the full lifecycle: reading the item, marking it in-progress, fulfilling its requirements, and marking it done.

## Usage

```
/do-item @feature-file.md
```

The argument should be a @mentioned kanban item file from `.devtool/features/`.

## Workflow

1. **Read the item**: Read the @mentioned file to understand its requirements
2. **Mark in-progress**: Update status to `in-progress` and `modified` timestamp
3. **Execute the work**: Implement/complete whatever the item describes
4. **Mark done**: Update status to `done`, set `completedAt`, and move to `done/` subfolder

## Kanban File Format

Kanban items are markdown files with YAML frontmatter:

```markdown
---
id: "my-feature-2026-02-20"
status: "backlog"
priority: "medium"
assignee: null
dueDate: null
created: "2026-02-20T10:00:00.000Z"
modified: "2026-02-20T10:00:00.000Z"
completedAt: null
labels: []
order: "a0"
---

# My Feature

Description and acceptance criteria here.
```

**Field serialization rules:**
- String fields: always `"double-quoted"`
- Nullable fields (`assignee`, `dueDate`, `completedAt`): bare `null` when unset
- Labels: inline array `["bug", "ui"]` or `[]`
- Field order: `id`, `status`, `priority`, `assignee`, `dueDate`, `created`, `modified`, `completedAt`, `labels`, `order`

**Valid status values:**
- `backlog` | `todo` | `in-progress` | `review` | `done`

## Features Directory

Default: `.devtool/features/` relative to workspace root.

- Active features (backlog, todo, in-progress, review): `{featuresDir}/{id}.md`
- Completed features (done): `{featuresDir}/done/{id}.md`

## Updating Status

### To In-Progress

1. Update `status` to `"in-progress"`
2. Update `modified` to current ISO timestamp
3. Keep file in `.devtool/features/` (root level)
4. Preserve exact serialization format

### To Done

1. Update `status` to `"done"`
2. Update `modified` to current ISO timestamp
3. Set `completedAt` to current ISO timestamp
4. **Move file** from `.devtool/features/{id}.md` to `.devtool/features/done/{id}.md`
5. Preserve exact serialization format

## Important Notes

- Never change `id` or `created` fields
- Always update `modified` when making any changes
- Preserve the exact frontmatter field order and serialization format
- The item description and acceptance criteria guide what work needs to be done
