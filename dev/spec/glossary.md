---
type: spec
status: active
tags: [glossary, ubiquitous-language, skos, markdown]
relatedTo: [issues, adrs]
---

# Glossary file

A project keeps its glossary in `GLOSSARY.md`, at the project root. It holds
the project's ubiquitous language: one term per concept, the words to avoid
for it, and where it lives in the code. Humans, agents and the `r2 glossary`
commands read and write the same file.

R2 reads any Markdown file at that path (lenient read) and always writes the
format below (strict write).

## Layout

```markdown
---
type: glossary
status: active
---

# Glossary

Introduction, any Markdown.

---

## Issue

A unit of work kept as a Markdown file in `dev/issues`, with a status and
a thread of comments.

- tags: process
- avoid: ticket, bug, task
- related: Comment, Thread
- code: `r2.core.issues.Issue`
- pt: tarefa

## Thread

...
```

- The frontmatter follows base: `type: glossary` and `status` are written;
  other keys are kept as they are.
- A level 1 heading holds the title, `Glossary` by default.
- The introduction runs up to a line holding only `---`.
- Each term is a level 2 heading followed by its definition, in any Markdown
  except level 2 headings.
- Terms are sorted alphabetically, ignoring case.

## Fields

A term may end with a list of fields. The list counts as fields only when it
is the last block of the term and every item has the form `- key: value`,
with a lowercase key. Any other list is part of the definition.

| Key | Value | Source |
| --- | --- | --- |
| `tags` | comma separated words that group terms | |
| `avoid` | comma separated words not to use for this concept | TBX `deprecatedTerm` |
| `related` | comma separated names of other terms | `skos:related` |
| `code` | identifiers or paths in the code that implement the term | |
| language code (`pt`, `es`, ...) | the term in that language | `skos:prefLabel` with a language tag |

The term name is in the language of the code. A language field holds the
name used in conversation or docs in another language; its key is an ISO
639-1 code.

Fields are written in the order of the table, language codes sorted, then
unknown keys as they are. Empty fields are left out.

`related` entries match term names ignoring case. Entries that match no term
are kept.

### Grouping

The glossary is flat: terms are not nested under headings. `tags` groups
them, and a term may have several tags. Concept hierarchies (a Defect is a
kind of Issue) are written in the definition.

## Checks

`r2 glossary check` reports, without changing the file:

- two terms with the same name;
- an `avoid` word that is the name of another term;
- a `related` entry that matches no term.

## Lenient read

- A file without frontmatter is read the same way.
- Without an H1, the title is `Glossary`.
- Without a `---` line, the introduction is the text before the first level
  2 heading.
- Unknown field keys are kept and written back.
- A term without a definition is kept, with an empty one.

## Future: polysemy

A word that means different things in different contexts may later be
written as one term per context, with the context in parentheses:
`## Account (Billing)` and `## Account (Auth)`. Until then, parentheses are
part of the term name.
