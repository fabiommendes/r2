---
type: adr
status: accepted
created: 2026-10-07
decided: 2026-10-07
---

# use python

Use python as the implementation language.

## Context

We need to move fast and use a language with a mature ecosystem.

## Options

- Use Python: mature ecosystem, fast development, widely adopted.
- Rust: performance, higher implementation complexity.
- Go: middle of the road.

## Decision

We choose Python.

## Consequences

The tool will run slightly slower than the other options, but not significantly
enough that it will be perceived in most use cases.
