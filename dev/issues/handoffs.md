---
type: issue
status: backlog
tags: [handoffs, cli]
relatedTo: [tooling-root/dev/adr/0003-modelo-de-repositorio.md, skills/dev/issues/adr-0003.md]
kind: enhancement
created: 2026-10-14
---

# Handoffs em `dev/handoffs/`

Hoje a skill de handoff grava em `/tmp`. O ADR 0003 do tooling-root move os
handoffs para `dev/handoffs/`, que fica no `.gitignore`. O r2 lista os handoffs,
marca um handoff como retomado e apaga os velhos. Quem escreve o handoff é a
skill, no `skills`.

## Formato proposto

`dev/handoffs/<slug>.md`:

```markdown
---
type: handoff
status: open
issue: <slug da issue>
branch: <branch>
worktree: <caminho>
created: 2026-10-14T15:30
creator: claude
---

# <o que estava sendo feito>

## Estado
## Próximo passo
## Arquivos
```

- `status`: `open` ou `taken`.
- `issue`, `branch` e `worktree` são opcionais.

## Comportamento

- A pasta é sempre a do checkout principal (a primeira linha de
  `git worktree list`), mesmo quando o comando roda numa worktree. Uma worktree
  nova não enxerga os arquivos ignorados de outra.
- O primeiro handoff cria `dev/handoffs/.gitignore` com `*`, como o
  `.r2/.gitignore` do `r2 coverage`.
- `r2 handoff list | show | take | prune`.
- `take` marca o handoff como `taken`, para que dois agentes não retomem o
  mesmo.
- `prune` apaga os handoffs `taken`, os criados há mais de 7 dias e os de issues
  fechadas. `--days N` muda o prazo.
