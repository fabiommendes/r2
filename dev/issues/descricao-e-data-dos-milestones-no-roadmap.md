---
type: issue
status: backlog
tags: [roadmap, milestone]
relatedTo: [roadmap]
kind: enhancement
created: 2026-10-14
creator: claude
---

# Descricao e data dos milestones no ROADMAP

## Context

`r2 roadmap` (`dev/issues/roadmap.md`) ordena os milestones pelo nome e lista
só os títulos das issues. O `ROADMAP.md` antigo do reportlab (no histórico do
git, `git log -- ROADMAP.md`) tinha, por milestone, uma frase com o objetivo
("A claim in a report links to the lines it is about."), e uma seção
"Later, deliberately not now". O arquivo gerado perde as duas coisas.

## Requirements

- R1. Um lugar para a descrição, e talvez a data, de cada milestone, que o
  `r2 roadmap` copia para o `ROADMAP.md`. Candidatos: `dev/milestones.toml`,
  ou uma issue `task` por milestone com `milestone` igual ao próprio nome.
  - Acceptance: a definir pelo humano.
- R2. Decidir se issues sem milestone em `backlog` aparecem numa seção
  "Later", ou continuam fora.

## Out of scope

- Mudar a ordem dos milestones, que segue o nome como versão.
