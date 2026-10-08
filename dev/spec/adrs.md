---
type: spec
status: active
tags: [adr, decisions, frontmatter, markdown, madr]
relatedTo: [issues, adr-view]
---

# ADR files

Architecture decision records live in `dev/adr/NNNN-<slug>.md`, one file per
decision. `NNNN` is a zero-padded sequence number that starts at `0001`; it
is the ADR's id (cited as "ADR-12") and is not repeated in the frontmatter.
New ADRs take the highest number in the folder plus one.

A file is plain Markdown with YAML frontmatter. R2 reads any Markdown file in
that folder (lenient read) and always writes the format below (strict write).
The rules shared with issues (comments, writing order, lenient read) follow
[issues](issues.md) unless this spec says otherwise.

## Frontmatter

`type` and `status` are always written. Every other key is optional and is
left out when it holds its default.

The first four keys are the ones base reads. The others borrow their names
from MADR and Dublin Core terms, so they can be mapped to RDF later with a
JSON-LD context.

| Key | Values | Default | Source |
| --- | --- | --- | --- |
| `type` | `adr` | required | base |
| `status` | see below | required, `proposed` on creation | MADR |
| `tags` | list of strings | `[]` | base |
| `relatedTo` | list of entity slugs or paths | `[]` | base |
| `created` | date, `YYYY-MM-DD` | filled in on creation | `dcterms:created` |
| `decided` | date, `YYYY-MM-DD` | none | `dcterms:dateAccepted` |
| `creator` | free text | none | `dcterms:creator` |
| `deciders` | list of strings | `[]` | MADR `decision-makers` |
| `supersedes` | list of ADR file stems | `[]` | `dcterms:replaces` |
| `supersededBy` | ADR file stem | none | `dcterms:isReplacedBy` |

`decided` holds the date the ADR left `proposed`, whether it was accepted or
rejected.

ADR references in `supersedes` and `supersededBy` use the file stem, number
included (`0003-json-config`).

### Status

The Nygard and MADR lifecycle:

- `proposed`: open.
- `accepted`, `rejected`, `deprecated`, `superseded`: closed.

Unlike issues, ADRs do not use the base lifecycle: a decision is not worked
on, it is proposed and then settled.

### Superseding

Superseding writes both sides in one action:

- the new ADR lists the old one in `supersedes`;
- the old ADR gets `status: superseded` and `supersededBy` pointing to the new
  one.

The redundancy is deliberate: a reader of the old file sees where the decision
went without any tool. When the two sides disagree on read, r2 trusts
`supersedes` and shows the old ADR as superseded.

## Body

The body opens with a level 1 heading that holds the title, followed by the
MADR sections as level 2 headings, in this order:

- `Context`: the problem and the forces at play.
- `Options`: the options considered, with pros and cons.
- `Decision`: the chosen option and why.
- `Consequences`: what gets easier or harder.

R2 writes these headings on creation. It does not enforce them on read.

Comments work as in issues: a line holding only `---`, outside fenced code
blocks, starts a comment, optionally opened by a `by: <who>` line. They are
meant for discussion while the ADR is `proposed`.

```markdown
---
type: adr
status: accepted
tags: [config]
created: 2026-10-07
decided: 2026-10-09
deciders: [fabio, claude]
supersedes: [0003-json-config]
---

# Store the configuration as TOML

## Context

...

## Options

...

## Decision

...

## Consequences

...

---
by: claude

TOML keeps comments, which JSON drops on rewrite.
```

## Lenient read

- A file without frontmatter is an ADR with status `proposed`.
- A file without an H1 takes its title from the file name, minus the number.
- A file name without a number prefix is accepted; the ADR has no id.
- Unknown keys and unknown values are kept and shown as they are.
- A broken frontmatter is treated as part of the body.

## Out of scope

ADRs are not synced with base decision entities (`base decision log`). The
ADR file is the only record.
