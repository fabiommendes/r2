---
type: adr
status: superseded
created: 2026-09-30
decided: 2026-09-30
supersededBy: 0002-incorporar-reportlab
---

# TypeScript, com uma costura para Rust

> Importado do reportlab, onde era a ADR 0003.

Status: aceito, 2026-09-30

## Contexto

A ferramenta é, sobretudo, um problema de UI: renderizar documentos, diffs e código
com realce de sintaxe, e navegar entre eles. Há também uma parte genuinamente limitada
pela CPU, que é o parsing e a varredura de um repositório.

## Decisão

TypeScript de ponta a ponta. `packages/scan` é escrito de forma que partes dele possam,
mais tarde, ser substituídas por um helper em Rust, nativo ou WebAssembly. A escolha
será feita quando surgir um gargalo concreto.

A costura só se sustenta se a API de `scan` continuar grossa e de dados para dados:
um arquivo inteiro ou um repositório inteiro por chamada. Uma API tagarela, com uma
chamada por nó, não cruza a fronteira entre linguagens sem devolver tudo o que a
fronteira deveria evitar.

Candidatos prováveis, por retorno: extração de símbolos de todo o repositório, divisão
de hunks em diffs muito grandes, vazão do realce de sintaxe. Não são candidatos: o
watcher, onde o `chokidar` basta, e a parte de git, onde iniciar o `git` é rápido e
correto.

Dois parsers são usados de propósito. `shiki` para cores, porque a cobertura das
gramáticas TextMate supera qualquer conjunto de queries do tree-sitter. `tree-sitter`
para estrutura, outlines e intervalos. Usar um dos dois para as duas tarefas dá
resultado ruim em uma delas.

Para as gramáticas, `web-tree-sitter` (WebAssembly) em vez de bindings nativos: um
`.wasm` por gramática, em vez de um build com node-gyp por linguagem. A diferença entre
o `npm install` funcionar ou não está aí.

## Alternativas rejeitadas

**Python.** Combina com as outras ferramentas do autor, mas o ecossistema de renderização
para Markdown, diffs e realce de sintaxe é bem mais fraco, em um projeto que é
sobretudo renderização.

**Rust ou Go para o núcleo.** Um único binário distribuível e varredura rápida, ao custo
de uma iteração lenta sobre algo que é essencialmente um protótipo de UX.

## Consequências

- É necessário Node 24 ou mais novo, o que traz o `node:sqlite` embutido e nenhuma
  dependência nativa para compilar.
- As gramáticas em WebAssembly são mais lentas que as nativas. Isso é aceitável para
  outlines por arquivo, e descarta o parsing de repositórios inteiros até existir um
  helper.
- `scan` precisa resistir à tentação de expor funções convenientes e granulares.
