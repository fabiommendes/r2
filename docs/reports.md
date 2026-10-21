# Reports

`r2 web` is a local web service that renders the reports coding agents write,
and links every path a report cites to the lines of code it is about. It needs
the `web` extra: `uv tool install 'r2-assistant[web]'`.

This page is also what agents write against. It is a published contract: agents
running in other repositories, under other harnesses, produce these files and
cannot be updated in lockstep with the daemon.

Two premises shape all of it. There is **no command to run**: an agent writes a
file and the page updates. And a report is **ephemeral**: it is read within minutes, then
forgotten. Anything worth keeping is an ordinary document in the repository,
written because a human asked for it.

## Running the viewer

```bash
cd your/project
r2 web init              # creates .reportlab/, starts the daemon, opens the browser
r2 web skill --install   # teaches your agent the conventions
```

After that, `r2 web open` opens the project. One daemon serves every project on
the machine, on `127.0.0.1` only, and the browser gets its access token from the
URL `r2 web` opens.

| Command          | What it does                                              |
| :--------------- | :-------------------------------------------------------- |
| `r2 web init`    | Set this project up and open it.                          |
| `r2 web open`    | Open this project.                                        |
| `r2 web detach`  | Stop watching this project. Deletes only the config file. |
| `r2 web status`  | Whether the daemon is up, and which projects it serves.   |
| `r2 web stop`    | Shut the daemon down.                                     |
| `r2 web serve`   | Run the daemon in the foreground.                         |
| `r2 web skill`   | Print the conventions, or `--install` them for an agent.  |

`r2 web init` is the only command that writes into your repository, which is why
it is a command you type on purpose rather than something that happens on first
use.

### Finding projects on their own

An agent can create `.reportlab/` in a repository where you never ran
`r2 web init`. Tell the daemon where to look and it picks up attached projects
when it starts, in r2's `~/.config/r2/config.toml`:

```toml
[web.discover]
roots = ["~/git", "~/work"]
depth = 6                     # optional, 6 by default
```

There is no default root. The scan looks for `.reportlab/config.toml`, not
`.reportlab/`, so a folder an agent created stays inert until you attach it.

## Where reports go

```
<repo>/.reportlab/
  config.toml              project settings, optional
  reports/                 reports, nested folders allowed
    auth-review.md
    oauth/session-notes.md
    auth-review.review.json   review marks, written by the UI
  threads/                 reserved, not implemented
  artifacts/               attachments (images, data files)
```

`.reportlab/` gitignores itself, through a `.gitignore` that `r2 web init` writes
inside it. Your own `.gitignore` is never touched, reports never reach a commit, and
nothing here shows up in `git status`.

A team that wants a shared project name commits the config once, with
`git add -f .reportlab/config.toml`. A file git already tracks is unaffected by an
ignore rule, so it stays tracked, and a fresh clone is attached without anyone
running anything.

The filename is the identity. Rewriting the same file updates the same report, so
an agent can write a report at the start of a task and keep it current as work
proceeds; the human watches it fill. Use a short slug, not a timestamp: the
navigator sorts by modification time and shows the age.

## Configuration

`config.toml` is the only file here a human writes, and **its presence is what
attaches the project**.
The daemon watches a project when the file is there and ignores the directory when
it is not, so a `.reportlab/` an agent created on its own is inert until someone
runs `r2 web init`.

Every setting in it is optional. An empty file attaches the project and says
nothing else.

```toml
[rl]
name = "auth service"
```

| Setting    | Type   | Effect                                                     |
| :--------- | :----- | :--------------------------------------------------------- |
| `rl.name`  | string | What the project is called in the UI. Defaults to the directory name. |

The name is a label only. A project's id comes from its directory name and its
path, so renaming it does not change any URL or invalidate anything.

Unknown keys and unknown sections are ignored and left in place, so a newer
r2 can add a setting without an older one refusing the file. A file that is
not valid TOML has its contents ignored but still attaches the project, and `r2 web
status` says what is wrong with it: a typo should not stop reports from arriving.

`r2 web detach` deletes this file and nothing else. `r2 web detach --purge` deletes
`.reportlab/` and the reports in it.

## Frontmatter

Optional. Every field is.

| Field    | Type                             | Default                          |
| :------- | :------------------------------- | :------------------------------- |
| `title`  | string                           | the first heading, else the filename |
| `kind`   | string                           | `note`                            |
| `agent`  | string, or `{name, model, session}` | absent; a bare string is the name |
| `tags`   | string list                      | empty                             |
| `commit` | string                           | absent; provenance only, never used to resolve a ref |

Known kinds, which only affect the icon and the grouping in the navigator:
`review`, `analysis`, `plan`, `summary`, `benchmark`, `note`. An unknown kind is
accepted.

A file with no frontmatter at all is a valid report. That is deliberate: the
cheapest possible thing an agent can do is write Markdown to a path, and nothing
about this format should make it hesitate.

## References

A ref points into the repository, and resolves against the **working tree**:

```
path/to/file.ts             whole file
path/to/file.ts:42          one line
path/to/file.ts:42:7        one line and column
path/to/file.ts:10-40       a line range
```

This is the form ripgrep, compilers and editors print, so a ref can be pasted
straight into an editor or back into a prompt. The older `path/to/file.ts#L10-40` is
still read and is no longer the form to write.

The path is relative to the repository root. No leading slash, no `..`. Lines are
1-based and inclusive. The column is carried but not used yet: the UI highlights
whole lines.

Never paste code into a report when a ref will do. The ref costs almost no tokens,
becomes a link, and reads the file as it is now rather than as it was when you
copied it.

A reference that is not a file on disk right now is rendered as plain text, not as
a broken link. Getting a path wrong costs the link, not the report.

The UI notes when a cited file was modified after the report was written, so the
human knows the lines may have moved. That is a comparison of two modification
times, not a git operation.

## Detected references

Paths written as ordinary prose are linked too, with no syntax at all. Both
locator forms work, including the one compilers and ripgrep print:

```markdown
The failure is in src/auth/session.py:45, and README.md is out of date.
```

Detected: paths with an extension, with a `:42`, `:42:7` or `:10-40` locator, or
the older `#L10-40`, and commit hashes of 7 to 40 hex characters. A detected path
is checked against the working tree and linked only if it exists, so a path that is
wrong renders as plain text rather than as a broken link.

Commit hashes are detected and never linked: the viewer runs no git.

A code span is a reference when it holds nothing but a path, with or without a
locator, as in `` `src/auth/session.py:45` ``, or the file stem of an issue, an
ADR or an RFC of the project, as in `` `issue-flow` ``, which links to
`dev/issues/issue-flow.md`. Any other code span stays code.

A relative path is tried from the folder of the Markdown file that cites it,
then from the repository root; in a report, from the root. An absolute path,
or one starting with `~/`, links only when it points inside the project. The
TUI resolves references the same way.

Directories are not detected: a word pair like `and/or` is indistinguishable from
a path. Write those as an explicit link with an `rl:` target, which degrades to
readable text everywhere else:

```markdown
Rotation happens in [`session.py`](rl:src/auth/session.py:40-58).
```

Detection is a convenience for prose. The `ref` attribute of a block is
structured data and must be a real ref.

## Blocks

Rich content is a fenced block whose language tag starts with `rl:`. Attributes
follow the tag as `key=value`, space separated, values quoted if they contain
spaces.

An unknown `rl:` block renders as a plain code block with a note. Never an error:
an old daemon has to survive a new agent.

### `rl:finding`

One claim. The unit of the review checklist.

````markdown
```rl:finding severity=high ref=src/auth/session.py:40-58
The session token is not rotated on login, which allows session fixation.
```
````

| Attribute  | Required | Values                                              |
| :--------- | :------- | :-------------------------------------------------- |
| `severity` | yes      | `high` \| `medium` \| `low` \| `info`               |
| `ref`      | no       | a ref; omit for a finding about no particular place  |
| `title`    | no       | short label; defaults to the first line of the body  |

One finding per problem. The human ticks them off one at a time, so a finding
containing three problems cannot be ticked.

### `rl:table`

Body is a JSON array of objects with consistent keys. Rendered sortable.

````markdown
```rl:table caption="Latency by endpoint"
[{"endpoint": "/login", "p50": 12, "p99": 340},
 {"endpoint": "/logout", "p50": 4, "p99": 31}]
```
````

## Partial files

The watcher sees files mid-write. A report that ends in the middle of a sentence,
or inside an unterminated fence, renders as far as it goes, with the open block
shown as open. There is no error state for an incomplete report, because for a
report being written live, incomplete is the normal state.

## Review marks

Written by the UI next to the report, as `<name>.review.json`. Deleted with the
report. Agents may read it to see what a human accepted.

```json
{
  "read": "2026-09-30T15:02:00-03:00",
  "findings": {
    "f1": { "state": "accepted", "note": "fixing in this branch" },
    "f2": { "state": "rejected" }
  }
}
```

Finding keys are assigned by document order (`f1`, `f2`, and so on), so editing a
report shifts them. For an ephemeral report that is a small cost, and it is the
reason agents are not asked to invent stable ids.

## URLs

```
/p/<project>/                             the navigator
/p/<project>/r/<path>                     a report, by its path under reports/
/p/<project>/f?path=<file>#L10-40         a file in the working tree
```

A path is a query parameter rather than part of the path, because a report path
and a file path both contain slashes. The line range is the fragment, in
the `#L10-40` form a browser expects, which is the one place that spelling
survives.

## Keeping something

There is no promote, export or archive feature. When a report matters beyond
today, ask the agent to write a document into the repository, wherever that
project keeps documents. The viewer renders Markdown from anywhere in the
repository through the navigator, so nothing is lost by the file living outside
`.reportlab/`.

## Forward compatibility

The reader is lenient by design, because the writer is a program in another
repository that nobody upgrades:

- Every frontmatter field is optional, and unknown fields are preserved.
- Unknown `kind` values render generically.
- Unknown `rl:` blocks render as code blocks with a note.
- A malformed block is reported inline, next to where it appeared, and never
  prevents the rest of the report from rendering.
- A file that is not valid Markdown does not exist. Any text file renders.
