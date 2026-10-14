---
type: issue
status: completed
tags: [issues, plan, tui]
relatedTo: [tooling-root/dev/adr/0003-modelo-de-repositorio.md, issues]
kind: enhancement
created: 2026-10-14
closed: 2026-10-14
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

## Plano

- [x] Contar as checkboxes da descrição em `r2/core/threads.py` (`- [x]`,
  `- [ ]`, com qualquer marcador de lista, fora de blocos de código). O
  `Format` ganha um `progress` opcional, que só as issues definem.
- [x] `r2 issue list` acrescenta `3/7` no fim da linha. O `--json` de `list` e
  `show` traz `"plan": {"done": 3, "total": 7}`, ou `null` sem checkboxes.
- [x] A TUI mostra `3/7` ao lado do título na árvore de issues.
- [x] Testes para a contagem, a CLI e a TUI.
- [x] Atualizar `dev/spec/issues.md` (seção do plano) e `dev/spec/cli.md`.
- [x] Checagem completa verde (`task ci`).

---
by: claude

Escolhas: o progresso vai no fim da linha de `r2 issue list`, para que o
começo `id  status  title` continue igual para quem já lê a saída. No JSON, as
issues sempre trazem a chave `plan` (`null` sem checkboxes) e os ADRs não a
trazem. Na árvore da TUI, o título passa a ser texto puro (antes era lido como
markup do Rich), com o progresso em cinza ao lado.
