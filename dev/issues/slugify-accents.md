---
type: issue
status: backlog
tags: [issues, rfc, slug]
relatedTo: [issues, rfcs]
kind: defect
created: 2026-10-14
---

# `threads.slugify` descarta letras acentuadas

`r2 issue new "Visão de stories na TUI"` cria `vis-o-de-stories-na-tui.md`. O
esperado é `visao-de-stories-na-tui.md`. Afeta issues e RFCs em português, que
são a maioria (ADR 0002 do tooling-root).

O `r2 story` já remove os acentos antes de cortar as palavras (`Configuração`
vira `configuracao`). O `slugify` das threads deve fazer o mesmo, com a mesma
função.
