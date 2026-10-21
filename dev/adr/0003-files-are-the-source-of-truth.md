---
type: adr
status: accepted
created: 2026-09-30
decided: 2026-09-30
---

# Arquivos são a fonte da verdade

> Importado do reportlab, onde era a ADR 0001.

Status: aceito, 2026-09-30

> Alterado por `0011-reports-are-ephemeral.md`. A decisão abaixo continua valendo; dois
> detalhes dela não. Não existe `rl report`, porque o agente entrega um relatório
> apenas escrevendo o arquivo, e nada mais. As marcas de revisão ficam em
> `<name>.review.json`, ao lado do relatório, e não em uma pasta `reviews/`.

## Contexto

Agentes precisam entregar relatórios ricos que um humano lê no navegador. O desenho
óbvio é um serviço com uma API HTTP e um banco de dados: o agente envia, o serviço
guarda, o navegador lê. Isso dá feedback imediato de validação e um armazenamento
autoritativo.

Mas também significa que o serviço é obrigatório para o agente funcionar, e que os
relatórios só existem dentro dele.

## Decisão

Um agente escreve um arquivo Markdown em `.reportlab/`, no repositório. O daemon
observa o diretório, faz o parsing do que encontra e guarda os dados derivados em
`.reportlab/index.db`. Nada existe só no índice.

Duas consequências são tratadas como regras, e não como preferências:

- Em caso de divergência de `schema_version`, o índice é apagado e reconstruído. Nunca
  se escreve uma migração.
- Tudo que um humano cria na UI é gravado em um arquivo dentro de `.reportlab/`, e o
  índice apenas espelha esse arquivo. Por isso, o estado de revisão fica em
  `.reportlab/reviews/<reportId>.json`.

## Alternativas rejeitadas

**API HTTP como única porta de entrada.** Exige um daemon em execução, uma porta
conhecida e uma confirmação de permissão do shell a cada escrita, e perde o relatório
se o daemon tiver sumido. Foi mantida como otimização: o `rl` usa o daemon quando ele
está no ar, só para receber de volta uma URL imediata.

**Servidor MCP como interface principal.** Estruturado e descobrível, mas custa contexto
em toda sessão, use-se relatórios ou não. Também limita a ferramenta a clientes que
suportam MCP. Deve ser reavaliado quando existir o canal reverso, pois aí uma chamada
bloqueante é de fato mais natural como ferramenta.

**Banco de dados como armazenamento, e arquivos como exportação.** A exportação fica
sempre atrás, e a propriedade que importa não é ter arquivos, mas ter os arquivos como
origem de tudo o mais.

## Consequências

- Os agentes funcionam com o daemon parado, o que importa para uma ferramenta usada
  todo dia.
- Os relatórios podem ser pesquisados com `grep`, comparados com `diff` e viajar em um
  pull request.
- A validação precisa existir independentemente do servidor, e é por isso que
  `packages/core` não faz E/S.
- As escritas são eventualmente consistentes: o agente não recebe confirmação
  autoritativa de uma escrita no sistema de arquivos. O `rl report` valida localmente
  e imprime a URL que o relatório terá.
