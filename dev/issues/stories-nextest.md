---
type: issue
status: backlog
tags: [stories, tests]
relatedTo: [user-stories, stories, coverage]
kind: enhancement
created: 2026-10-14
creator: claude
---

# Ligação de user stories com testes do nextest

Adiado de `user-stories.md`. Decidir como um teste Rust cita uma story (nome do teste, atributo, comentário) e ler isso em `r2/core/stories/tests.py`, sem rodar o `cargo nextest` (ou com `cargo nextest list`, se a leitura estática não bastar).
