---
type: issue
status: in_progress
tags: [rfc, threads, cli, tui]
relatedTo: [tooling-root/dev/adr/0003-modelo-de-repositorio.md, adrs]
kind: enhancement
created: 2026-10-14
---

# RFCs em `dev/rfc/`

O ADR 0003 do tooling-root separa o desenho de uma funcionalidade (RFC) da
decisão (ADR). O RFC é onde o humano e um agente discutem. O ADR só registra o
que já foi decidido.

## Formato proposto

`dev/rfc/<slug>.md`, sem número, com as mesmas regras de comentário, ordem de
escrita e leitura tolerante de `issues.md`.

| Chave | Valores | Padrão |
| --- | --- | --- |
| `type` | `rfc` | obrigatório |
| `status` | `draft`, `accepted`, `rejected`, `withdrawn` | `draft` na criação |
| `tags`, `relatedTo` | como nas issues | `[]` |
| `created`, `decided`, `creator` | como nos ADRs | |

Corpo, com os títulos que o r2 escreve na criação:

- `Problem`: o que falta e para quem.
- `Proposal`: o desenho. Vivo enquanto o RFC é `draft`.
- `Alternatives`
- `Open questions`
- `Outcome`: preenchido quando o RFC é decidido. Lista as stories, ADRs e
  issues que ele gerou.

`draft` é o único status aberto. Um RFC decidido não é editado.

## Comandos

`r2 rfc`, com os mesmos comandos de `r2 issue`. A TUI mostra os RFCs como mostra
issues e ADRs.

## Questões abertas

- Um comando `accept` que cria os ADRs e as issues listados em `Outcome`, ou o
  agente cria cada um com `r2 adr new` e `r2 issue new`?

## Plano

- [x] `r2/core/rfcs.py`: o formato do RFC sobre `r2/core/threads.py`, com os
  status, as chaves, as seções da criação e a data `decided`. O slug livre de
  `issues.new_path` passa para `threads`, para issues e RFCs usarem o mesmo.
- [x] `r2 rfc` em `r2/cli/threads.py`: os comandos comuns e um `new` com
  `--body`, `--tag`, `--relatedTo` e `--by`.
- [x] A TUI ganha a aba RFCs, com o filtro, os comentários e os botões das
  outras threads, e resolve slugs de RFC em `relatedTo`.
- [x] Testes do formato, da CLI e da TUI.
- [ ] Escrever `dev/spec/rfcs.md` e atualizar `dev/spec/cli.md`,
  `dev/spec/issues.md` e o `README.md`.
- [ ] Checagem completa verde (`task ci`).
