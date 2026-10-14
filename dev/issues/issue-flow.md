---
type: issue
status: backlog
tags: [issues, cli, tui]
relatedTo: [tooling-root/dev/adr/0003-modelo-de-repositorio.md, issues, cli]
kind: task
created: 2026-10-14
---

# Alinhar o fluxo de issues ao ADR 0003

O ADR 0003 do tooling-root define um contrato para os status e usa o `kind`
para decidir se um agente faz o merge sozinho (`defect` e `task`) ou espera o
humano (`enhancement` ou sem `kind`). O r2 diverge em três pontos.

## Plano

- `NEXT_STATUS` em `r2/core/issues.py` leva `in_progress` direto para
  `completed`. No ADR, `advance` passa por `in_review`.
- `r2 issue new` não aceita `--kind`, então um agente cria issues sem `kind`,
  que pelo ADR sempre esperam o humano. Acrescentar `--kind`, e também
  `--priority`, `--milestone` e `--relatedTo`, que o formulário da TUI já
  preenche.
- Os modelos de corpo em `r2/tui/widgets/issue_form.py`: `enhancement` usa
  `Motivation` e `Proposal`, que agora são papel do RFC. Pelo ADR, o corpo de
  uma issue `enhancement` é a spec: `Context`, `Requirements` (`R1`..., cada um
  com critérios de aceitação) e `Out of scope`. Usar os mesmos modelos em
  `r2 issue new --kind`.
- Atualizar `dev/spec/issues.md` e `dev/spec/cli.md`.
