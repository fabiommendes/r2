---
type: adr
status: accepted
created: 2026-09-30
decided: 2026-09-30
---

# SolidJS para a UI

> Importado do reportlab, onde era a ADR 0008.

Status: aceito, 2026-09-30

## Contexto

A UI é um visualizador de documentos com algumas visões grandes e densas: uma página de
relatório, uma visão de arquivo com linhas destacadas e um diff que pode chegar a milhares
de linhas. O estado chega por um stream SSE e invalida partes da página.

## Decisão

SolidJS com `@solidjs/router`, compilado pelo Vite.

O estado do servidor é tratado com as primitivas do próprio Solid, `createResource` recarregado
a partir de eventos SSE, e não com uma biblioteca de queries. A regra de invalidação deste
app é explícita e estreita: um evento nomeia o projeto e o documento que mudou. Uma camada
de cache seria, na maior parte, indireção sobre uma chamada de `refetch`.

## Alternativas rejeitadas

**React**, que foi a escolha original e foi o primeiro a ser montado. O ecossistema é maior,
mas o trabalho aqui são atualizações granulares sobre listas grandes, que é onde um DOM
virtual ajuda menos e onde a reatividade compilada do Solid ajuda mais. Trocar a página
provisória levou o bundle de produção de 220 kB para 10 kB. Isso é um argumento fraco sozinho
para uma ferramenta localhost, mas é uma boa medida de quanto framework existe entre um
evento e uma atualização do DOM.

**Svelte.** Comparável em mérito. O JSX do Solid mantém o código dos componentes mais próximo
de TypeScript comum, o que importa para um projeto cujos tipos vêm de pacotes compartilhados.

**Nenhum framework.** Uma visão de diff com referências resolvidas, achados na margem e
atualizações ao vivo é estado de UI real. Atualizações de DOM escritas à mão seriam
reimplementadas de forma ruim.

## Consequências

- A reatividade do Solid não é a do React: as props são acessadas, não desestruturadas, e os
  effects rastreiam o que leem. Quem assume idiomas do React escreve bugs que parecem um
  componente que não renderiza.
- Testar componentes exige `@solidjs/testing-library` e o plugin Vite do Solid na configuração
  do vitest. Ainda não foi configurado; ainda não há componentes.
- Virtualizar diffs muito longos é um problema resolvido no ecossistema React, e menos aqui.
  Se virar um problema, é um trabalho autocontido.
