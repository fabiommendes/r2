---
type: issue
status: in_review
tags: [roadmap, changelog, milestone, cli]
relatedTo: [tooling-root/dev/adr/0003-modelo-de-repositorio.md, issues]
kind: enhancement
created: 2026-10-14
---

# Gerar `ROADMAP.md` e um rascunho do changelog a partir das issues

O ADR 0003 do tooling-root tira o `ROADMAP.md` escrito à mão: o `milestone` das
issues é a única fonte. Repositórios públicos ainda querem o arquivo.

- `r2 roadmap` escreve `ROADMAP.md` com as issues abertas agrupadas por
  milestone. Issues sem milestone ficam fora, ou numa seção "Sem data".
- `r2 roadmap --check` sai com código 1 quando o arquivo não bate com as issues.
  Assim ele pode rodar no lint.
- `r2 changelog --draft MILESTONE` imprime as issues fechadas do milestone,
  agrupadas por `kind`, como ponto de partida para o `CHANGELOG.md`. O texto
  final continua manual.

## Questões abertas

- Onde fica a ordem e a data dos milestones? Ordenar os nomes como versões é o
  mínimo. Um arquivo `dev/milestones.toml` resolve datas, mas é mais um
  arquivo.

## Plano

- [x] `r2/core/roadmap.py`: ordem natural dos milestones, o texto do
  `ROADMAP.md` (issues abertas por milestone) e o rascunho do changelog
  (issues fechadas do milestone por `kind`).
- [x] `r2 roadmap [--check]` e `r2 changelog --draft MILESTONE` em
  `r2/cli/roadmap.py`.
- [x] Testes do módulo e da CLI.
- [x] Escrever `dev/spec/roadmap.md` e atualizar `dev/spec/cli.md` e o
  `README.md`.
- [x] Checagem completa verde (`task ci`).

---
by: claude

Escolhas:

- Ordem dos milestones: o nome dividido em trechos de dígitos e de texto, os
  dígitos comparados como números (`0.9.0` antes de `0.10.0`, `M9` antes de
  `M10`). Sem arquivo de datas. Pré-lançamentos não seguem o semver:
  `1.0.0` vem antes de `1.0.0-rc1`. Um milestone numérico como `1.10`
  precisa de aspas no YAML; a spec registra isso.
- `ROADMAP.md` traz só o título de cada issue, com link para
  `dev/issues/<slug>.md`, na ordem do slug. Sem status, `kind` ou
  prioridade: assim o `--check` não falha a cada `r2 issue advance`, só
  quando uma issue muda de milestone, de título ou fecha. Issues sem
  milestone ficam fora, sem seção "Sem data".
- O arquivo abre com um comentário HTML que diz que ele é gerado e como
  mudá-lo. `r2 roadmap` não reescreve um arquivo que já bate.
- `--check` sai com 1 também quando o arquivo não existe.
- `changelog --draft` usa os títulos do Keep a Changelog, que gitpair e
  reportlab já seguem: `enhancement` em `Added`, `defect` em `Fixed`, e
  `task`, outro `kind` ou nenhum em `Other`. Só entram issues `completed`;
  `wont_fix` e `deprecated` não são mudanças entregues. O cabeçalho é
  `## [MILESTONE]`, sem data. Cada item termina com o slug entre crases,
  para quem reescreve achar a issue.
- Um milestone que nenhuma issue usa é erro com código 1, que lista os
  conhecidos. Issues abertas do milestone saem num aviso em stderr, útil na
  hora do lançamento. `changelog` aceita `--json`; `roadmap` só escreve e o
  ignora.
- A spec ficou em `dev/spec/roadmap.md` (formato), e os comandos numa seção
  nova de `cli.md` (requisitos 51 a 54), como nas outras specs.
- Testado à mão com cópias de `gitpair/dev/issues` e `reportlab/dev/issues`.
  Comparado ao `ROADMAP.md` antigo do reportlab, o arquivo gerado perde a
  frase de objetivo de cada milestone e a seção "Later": ficou para
  `descricao-e-data-dos-milestones-no-roadmap`, em `backlog`.

