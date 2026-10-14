---
type: issue
status: backlog
tags: [stories]
relatedTo: [user-stories, stories]
kind: enhancement
created: 2026-10-14
creator: claude
---

# Relatório de cobertura das stories em arquivo

Adiado de `user-stories.md`. Hoje `r2 story check` só imprime a cobertura por papel. O codehood grava `docs/user-stories/coverage.md` e o `--check` dele falha quando o arquivo está desatualizado. Decidir se o r2 grava esse arquivo (e com que formato) ou se a saída impressa basta. Junto: escolher os testes e2e por runner (todos os testes do playwright), e não só por pasta.
