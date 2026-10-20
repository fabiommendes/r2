---
type: issue
status: in_review
tags: [tui, markdown, performance]
relatedTo: [o-r2-termina-quando-o-arquivo-visualizado-apagado]
kind: enhancement
priority: high
created: 2026-10-20
---

# Renderizar o Markdown da TUI por linhas

## Context

O `MarkdownPane` usa o `textual.widgets.Markdown`, que monta um widget por
bloco. Com o `README.md` (22KB, 125 blocos), abrir o documento leva 820ms; com
88KB (500 blocos), 1.860ms. O parse pelo markdown-it é 3% disso (24ms e 70ms):
o tempo vai para montar e fazer o layout dos widgets. O Rich renderiza os
mesmos 88KB em linhas em 214ms.

Além disso, o `MarkdownViewer.go` lê o arquivo sem tratar `OSError`, uma das
causas de o r2 terminar quando o arquivo visualizado é apagado.

## Requirements

- R1. O documento é um único widget que renderiza o Markdown pelo Rich em
  linhas (`Strip`), guardadas por largura, e desenha pela Line API só as
  linhas visíveis.
  - Abrir um documento de 88KB mostra a primeira tela sem esperar o resto; o
    resto é renderizado num worker em thread, em lotes.
  - Mudar a largura renderiza de novo; a mesma largura não renderiza de novo.
- R2. O visual segue o tema do Textual: cores dos títulos pelas variáveis
  `markdown-h*`, o H1 em caixa alta, fences com highlight (tema escuro ou
  claro conforme o tema), tabelas, listas, citações e regras horizontais.
- R3. Links locais abrem o arquivo no próprio painel, inclusive com âncora
  (`doc.md#titulo`) e só âncora (`#titulo`); links `http`, `https` e `mailto`
  abrem no navegador.
- R4. Os comentários das threads (issues, ADRs e RFCs) continuam em cartões
  que recolhem, com os mais antigos recolhidos, como hoje.
- R5. A busca (`/`) continua como hoje: casa o texto mostrado (não o
  Markdown nem os destinos dos links), destaca todas as ocorrências e a
  atual à parte, as setas navegam e rolam até a ocorrência, abre o comentário
  recolhido que a contém, `esc` limpa.
- R6. Um erro ao ler o arquivo (apagado, sem permissão, não UTF-8) mostra uma
  mensagem no painel em vez de derrubar o r2.

## Out of scope

- Índice (table of contents), que hoje já fica escondido.
- Imagens, histórico de navegação (voltar e avançar).
- Uma ocorrência da busca quebrada entre duas linhas pelo wrap não é achada.
- A camada de leitura segura para o resto do r2 (ver
  `o-r2-termina-quando-o-arquivo-visualizado-apagado.md`).
