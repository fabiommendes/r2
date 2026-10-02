---
type: spec
status: active
tags: [issues, frontmatter, markdown, comments, oslc-cm]
relatedTo: [issues-view, issue-form]
---

# Issue files

Issues live in `dev/issues/<slug>.md`, one file per issue. A file is plain
Markdown with YAML frontmatter. R2 reads any Markdown file in that folder
(lenient read) and always writes the format below (strict write).

## Frontmatter

`type` and `status` are always written. Every other key is optional and is
left out when it holds its default, so a fresh issue stays short.

The first four keys are the ones base reads. The others borrow their names
from OSLC Change Management 3.0 and Dublin Core terms, so they can be mapped
to RDF later with a JSON-LD context without touching the files.

| Key | Values | Default | Source |
| --- | --- | --- | --- |
| `type` | `issue` | required | base |
| `status` | see below | required, `backlog` on creation | base |
| `tags` | list of strings | `[]` | base |
| `relatedTo` | list of entity slugs or paths | `[]` | base |
| `kind` | `defect`, `enhancement`, `task` | none | `oslc_cm:Defect`, `Enhancement`, `Task` |
| `priority` | `low`, `normal`, `high`, `urgent` | `normal` | `oslc_cm:priority` |
| `severity` | `trivial`, `minor`, `normal`, `major`, `critical` | `normal` | `oslc_cm:severity` |
| `milestone` | milestone name | none | `oslc_cm:affectsPlanItem` |
| `parent` | slug of another issue | none | `oslc_cm:parent` |
| `blocks` | list of issue slugs | `[]` | |
| `created` | date, `YYYY-MM-DD` | filled in on creation | `dcterms:created` |
| `creator` | free text | none | `dcterms:creator` |
| `closed` | date, `YYYY-MM-DD` | none | `oslc_cm:closeDate` |

`milestone` limits the issue to one milestone; without it, the issue belongs
to no milestone in particular.

### Status

The base lifecycle, plus two terminal states:

- `backlog`, `todo`, `in_progress`, `blocked`, `deferred`, `in_review`: open.
- `completed`, `wont_fix`, `deprecated`: closed.

### Writing order

Keys are written in the order of the table. Lists use the flow style
(`tags: [a, b]`). Keys r2 does not know are kept as they are, after the
known ones.

## Body

The body opens with a level 1 heading that holds the title, followed by the
description.

A line holding only `---`, outside fenced code blocks, starts a comment. The
comments read top to bottom, like a forum thread. A comment may start with a
line `by: <who>` that tells who wrote it; the line is not part of its text.
The description has no `by:` line: its author is `creator`.

```markdown
---
type: issue
status: todo
kind: defect
created: 2026-10-02
---

# The preview loses the cursor after an edit

Steps to reproduce...

---
by: fabio

It happens only with excerpts.

---
by: claude

Found the cause: `reload()` resets the selection.
```

## Lenient read

- A file without frontmatter is an issue with status `backlog`.
- A file without an H1 takes its title from the file name.
- Unknown keys and unknown values are kept and shown as they are.
- A broken frontmatter is treated as part of the body.
