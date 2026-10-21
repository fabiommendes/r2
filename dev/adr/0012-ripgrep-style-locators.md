---
type: adr
status: accepted
created: 2026-09-30
decided: 2026-09-30
---

# O locator canônico é o que o ripgrep imprime

> Importado do reportlab, onde era a ADR 0010.

Status: aceito, 2026-09-30

Restringe `0006-markdown-with-typed-blocks.md` e
`0009-markdown-it-and-detected-references.md`, que definiram que uma referência carrega um
intervalo de linhas, mas não definiram qual grafia é a real.

## Contexto

Uma referência precisa de um locator, e havia duas grafias em uso ao mesmo tempo no produto:
`src/a.ts#L10-40`, que a documentação pedia, e `src/a.ts:42`, que a detecção também aceitava
porque os agentes produzem essa forma de qualquer jeito.

Duas grafias para uma mesma coisa custam em três lugares. A documentação precisa explicar as
duas. A skill precisa ensinar uma e tolerar a outra. E cada `formatRef` na UI precisa escolher
uma, o que faz com que a forma que um humano copia da página seja uma escolha que ninguém fez
de propósito.

O critério de desempate é o que acontece com a string depois que ela sai do reportlab. Uma
referência é colada em um editor, em um terminal, em um comando `git` ou de volta em um prompt
para um agente. `path:line` e `path:line:column` são o que compiladores, linters, ripgrep,
grep, ctags e language servers imprimem, e o que VS Code, Vim, Emacs e JetBrains aceitam como
alvo de salto. `#L10-40` é um fragmento de URL do GitHub; nada fora de um navegador o entende.

## Decisão

O locator canônico é o do ripgrep:

```
path:5        uma linha
path:5:10     linha e coluna
path:5-40     um intervalo
```

`formatRef` emite somente essa forma, então é o que a UI mostra e o que um humano copia. A
skill ensina somente essa forma.

`path#L5`, `path#L10-40` e `path#L10-L40` continuam sendo lidos, por `parseRef` e pela detecção,
e não são documentados como opção. Um relatório é escrito por um programa em outro repositório
que ninguém atualiza, então o leitor continua tolerante (`docs/conventions.md`, "Forward
compatibility").

A forma de intervalo `path:5-40` é a única parte disto que nenhuma ferramenta imprime, porque
nenhuma ferramenta precisa nomear um intervalo. Ela é a extensão natural da família, e não uma
quarta grafia.

Linha e coluna são parseadas e carregadas em `Ref.column`. A visão de arquivo destaca linhas
inteiras e ignora a coluna, o que é uma decisão da UI, e não um motivo para descartar o número
no parser.

## Alternativas rejeitadas

**Manter `#L10-40` como canônico.** É a forma que um fragmento de URL exige, e a visão de arquivo
já a usa no próprio endereço. Mas uma referência não é uma URL: é uma string que um agente
escreve e um humano cola em outro lugar.

**Aceitar apenas a forma do ripgrep.** Uma grafia em todo lugar, mas quebra todo relatório escrito
para a versão anterior do contrato sem nenhum ganho. Ler uma forma a mais é um ramo de regex.

**Levar a coluna para o realce.** Um destaque de um caractere é difícil de enxergar e mais difícil
ainda de linkar, e nada no produto pediu isso até agora.

## Consequências

- `docs/conventions.md`, a skill, o README e o glossário mostram uma forma só.
- As URLs do próprio navegador mantêm `#L10-40`, porque um fragmento é um fragmento. As duas formas
  agora têm uma divisão clara: `:` no texto do relatório, `#L` na barra de endereço.
- A detecção ganha mais um ramo em que pode errar, então os testes nomeiam cada forma.
