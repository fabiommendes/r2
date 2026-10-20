---
type: issue
status: in_review
tags: [tui, file]
kind: defect
priority: high
severity: major
created: 2026-10-14
---

# O r2 termina quando o arquivo visualizado é apagado

O r2 quebra tentando ler um arquivo que não existe se ele for apagado por um processo externo.

Todos os processos de leitura de arquivo devem ser protegidos com um try/except ou outro mecanismo de
conferencia se o arquivo ainda está vivo e a aplicação deve falhar de forma graciosa.


## Steps to reproduce

Apague o arquivo que o r2 visualiza externamente, pule entre projetos ou abas e veja o defeito aparecer.

## How to fix

Criar um ADR para definir como vamos abstrair a leitura de arquivos e passar toda leitura por
essa interface segura ao invés de deixar exposto à exceções não tratadas.

---
by: Fábio Macêdo Mendes

Causa: até 598e0da o DocumentViewer usava o MarkdownViewer do Textual, cujo go() chama Markdown.load sem tratar OSError; selecionar no tree a folha de um arquivo já apagado derrubava o app. A reescrita do Markdown passou a ler por read_document, que mostra "Cannot read ...". As demais leituras do TUI já tratavam OSError, então a ADR de uma camada central de leitura ficou desnecessária. Teste de regressão: test_a_doc_deleted_behind_the_tree_shows_why_it_cannot_be_read. Também tratei a corrida entre stat e open em events.tail.
