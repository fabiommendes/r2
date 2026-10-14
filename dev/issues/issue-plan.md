---
type: issue
status: backlog
tags: [issues, plan, tui]
relatedTo: [tooling-root/dev/adr/0003-modelo-de-repositorio.md, issues]
kind: enhancement
created: 2026-10-14
---

# Mostrar o progresso do plano de uma issue

Pelo ADR 0003 do tooling-root, o agente que pega uma issue escreve uma seção
`## Plano` com checkboxes. Ele marca cada item no commit que o fecha, e outro
agente retoma dali.

- `r2 issue list` e a TUI mostram o progresso: `3/7`.
- O `--json` de `list` e `show` acrescenta `"plan": {"done": 3, "total": 7}`.
- A contagem usa todas as checkboxes da descrição, sem os comentários. Assim o
  título da seção pode seguir a língua do repositório (`## Plano` ou
  `## Plan`). Uma descrição sem checkboxes não tem progresso.
- Atualizar `issues.md` com a seção.
