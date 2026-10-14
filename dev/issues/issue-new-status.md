---
type: issue
status: backlog
tags: [issues, cli]
relatedTo: [cli, rfcs]
kind: task
created: 2026-10-14
---

# `r2 issue new --status` e o fluxo de status no README

- Um RFC aceito gera issues já em `todo` (ADR 0003 do tooling-root). Hoje isso
  exige `r2 issue new` e depois `r2 issue status X todo`. Acrescentar
  `--status` ao `new`.
- O `README.md` ainda descreve o fluxo de issues como `in progress → completed`,
  sem `in_review`.
