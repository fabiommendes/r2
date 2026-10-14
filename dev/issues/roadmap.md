---
type: issue
status: backlog
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
