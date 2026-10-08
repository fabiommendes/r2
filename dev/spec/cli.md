---
type: spec
status: active
tags: [cli, agent-mode, glossary]
relatedTo: [glossary, issues, adrs]
---

# Command line

The `r2` command serves two kinds of users: humans at a terminal and coding
agents running shell commands. Both use the same commands; a global mode
changes how r2 talks back, never what a command does.

## Modes

1. Human mode is the default. Agent mode is on with `--agent` or when the
   environment sets `R2_AGENT` to `1`, `true`, `yes` or `on`.
2. In agent mode r2 never prompts. A command that would prompt fails with
   exit code 1 and says which argument to pass instead.
3. Agent mode changes the default verbosity (see Verbosity) and nothing
   else. Output format is chosen separately, with `--json`.

## Global options

4. Global options belong to the root `r2` command:

   | Option | Meaning |
   | --- | --- |
   | `--agent` | agent mode |
   | `-v`, `--verbose` | raise the verbosity by one, repeatable |
   | `-q`, `--quiet` | lower the verbosity by one, repeatable |
   | `-y`, `--yes` | pre-approve destructive commands |
   | `--json` | JSON output for commands that read data |
   | `-C <dir>` | run as if r2 started in dir, like `git -C` |

5. Global options are accepted anywhere before `--`: `r2 -q glossary list`
   and `r2 glossary list -q` are the same. The exceptions:
   - a project or plugin command forwards its arguments to another
     program, so only options before the command name are global (`r2 -q
     test -v` runs the tests quietly and passes `-v` to the test runner);
   - `-C` is only read before the command name, as in git.
6. Options that only make sense for one command group stay on it, like the
   `-f/--file` of `r2 glossary`.

## Verbosity

7. Verbosity is a number: the mode default (0 for humans, -1 for agents)
   plus the count of `-v` minus the count of `-q`. So `-qv` is the mode
   default, and `-vv` is two levels above it.
8. Levels:

   | Level | Name | Output |
   | --- | --- | --- |
   | -2 | silent | errors only |
   | -1 | summary | one line per result; a failing program shows its last lines |
   | 0 | normal | the full output |
   | 1 | verbose | also the programs r2 runs, and where |
   | 2 | debug | also debug logs |

9. Each command clamps the verbosity to the levels it supports. Plugins
   read it from `r2.core.mode.mode.verbosity`.
10. A project command declared with `output = "summary"` runs with its
    output captured below level 0: on success it prints `ok: <name>`; on
    failure it prints `failed: <name> (exit N)` and, at level -1, the last
    30 lines of output.

## Output and errors

11. Results go to stdout, one record per line, with no line wrapping.
12. Errors and warnings go to stderr, as `error: <message>` and
    `warning: <message>`.
13. Exit codes: 0 on success; 1 when the command fails for a reason of the
    domain (term not found, duplicate term, problems found by a check); 2
    for usage errors (unknown option, missing argument).
14. With `--json`, a command that reads data prints one JSON document to
    stdout. Commands that only write ignore `--json`.

## Files

15. Every file r2 writes is replaced atomically: the new text goes to a
    temporary file in the same folder, which then replaces the target. A
    reader sees the old file or the new one, never a half written one. The
    file keeps its permissions, and a symlink keeps pointing to the same
    file.
16. A change that reads a file, edits it and writes it back holds an
    exclusive lock on the file's folder for the whole cycle, so two r2
    processes never overwrite each other's changes. The TUI applies its
    changes to the file as it is on disk when saving, not to the copy it
    displays.
17. Creating a file (a new issue or ADR) holds the same lock while it picks
    the file name, and never overwrites an existing file.
18. Locks are advisory `flock` locks on the folder itself; r2 leaves no
    lock files behind. Windows is not supported.

## Glossary

The format is in [glossary.md](glossary.md).

19. Every glossary command takes `-f/--file`. The default is `GLOSSARY.md`
    at the project root: the closest folder, from the current one up, that
    holds `.git`, or the current folder if none does.
20. Reading commands accept any Markdown file. Writing commands refuse,
    with exit code 1, a file whose frontmatter lacks `type: glossary`, and
    point to `r2 glossary fmt`. `fmt` is the only command that converts a
    file to the strict format.

### Reading

21. `r2 glossary list [--tag TAG]` prints each term as `Name: summary`,
    where the summary is the first sentence of the definition. `--tag`
    keeps the terms with that tag, ignoring case.
22. `r2 glossary show TERM` prints the term's section as it is written in
    the file. An unknown term is an error.
23. `r2 glossary find WORDS` prints the terms that match WORDS, the way the
    TUI filter does: every word must start a word of the name, the
    definition or a field. When a word matches an `avoid` entry, the line
    reads `<avoided> -> Name`, telling which term to use instead. No match
    is not an error.
24. `r2 glossary check` reports, one per line, without changing the file:
    the checks in [glossary.md](glossary.md#checks), plus a file without
    `type: glossary` in its frontmatter. It exits 1 when it reports
    anything.
25. With `--json`:
    - `list` and `find` print a list of terms;
    - `show` prints one term;
    - `check` prints a list of `{"term": ..., "problem": ...}`, where
      `term` is null for problems of the whole file.

    A term is `{"name": ..., "definition": ..., "fields": {...}}`, with the
    fields as written. `find` adds `"avoided": [...]`, the avoided words
    that matched.

### Writing

26. `r2 glossary add "Name: definition"` adds a term. Without a
    definition, human mode prompts for it.
27. `add` takes the fields as options:
    - `--tag`, `--avoid`, `--related`, `--code`: repeatable, and each value
      may hold several comma separated entries;
    - `--field key=value`: any other field, such as a language (`--field
      pt=termo`); repeatable.
28. `r2 glossary set TERM` changes an existing term. It takes the options
    of `add`, plus `--definition TEXT` and `--unset KEY` (repeatable). A
    field option replaces the whole field; `--unset` removes it.
29. `r2 glossary remove TERM` removes a term.
30. `r2 glossary fmt` rewrites the file in the strict format, terms sorted.
31. Term names match ignoring case. Adding a term that exists, or changing
    or removing one that does not, is an error that leaves the file as it
    was.
32. Each write prints one line saying what changed, unless the verbosity
    is -2.
