---
type: spec
status: active
tags: [glossary, ubiquitous-language, skos, markdown]
relatedTo: [issues, adrs]
---

# Arquivo de glossário

O projeto guarda o glossário em `GLOSSARY.md`, na raiz do projeto. Ele registra a linguagem ubíqua do projeto: um termo por conceito, as palavras a evitar para cada um e onde ele está no código. Pessoas, agentes e os comandos `r2 glossary` leem e escrevem o mesmo arquivo.

O r2 lê qualquer arquivo Markdown nesse caminho (leitura tolerante) e sempre escreve o formato abaixo (escrita estrita).

## Estrutura

```markdown
---
type: glossary
status: active
---

# Glossary

Introduction, any Markdown.

---

## Issue

A unit of work kept as a Markdown file in `dev/issues`, with a status and
a thread of comments.

- tags: process
- avoid: ticket, bug, task
- related: Comment, Thread
- code: `r2.core.issues.Issue`
- pt: tarefa

## Thread

...
```

- O frontmatter segue a base: `type: glossary` e `status` são escritos; as outras chaves são mantidas como estão.
- Um título de nível 1 traz o título, `Glossary` por padrão.
- A introdução vai até uma linha que contém só `---`.
- Cada termo é um título de nível 2, seguido da definição, em qualquer Markdown exceto títulos de nível 2.
- Os termos são ordenados em ordem alfabética, sem diferenciar maiúsculas de minúsculas.

## Campos

Um termo pode terminar com uma lista de campos. A lista só conta como campos quando é o último bloco do termo e todo item tem a forma `- chave: valor`, com chave em minúsculas. Qualquer outra lista faz parte da definição.

| Chave | Valor | Origem |
| --- | --- | --- |
| `tags` | palavras separadas por vírgula que agrupam termos | |
| `avoid` | palavras separadas por vírgula que não devem ser usadas para este conceito | TBX `deprecatedTerm` |
| `related` | nomes separados por vírgula de outros termos | `skos:related` |
| `code` | identificadores ou caminhos no código que implementam o termo | |
| código de idioma (`pt`, `es`, ...) | o termo nesse idioma | `skos:prefLabel` com uma tag de idioma |

O nome do termo fica no idioma do código. Um campo de idioma guarda o nome usado em conversas ou na documentação em outro idioma; a chave é um código ISO 639-1.

Os campos são escritos na ordem da tabela, com os códigos de idioma em ordem alfabética, e depois as chaves desconhecidas, como estão. Campos vazios ficam de fora.

As entradas de `related` batem com os nomes dos termos sem diferenciar maiúsculas de minúsculas. Entradas que não batem com nenhum termo são mantidas.

### Agrupamento

O glossário é plano: os termos não ficam aninhados sob títulos. `tags` agrupa os termos, e um termo pode ter várias tags. Hierarquias de conceitos (um Defect é um tipo de Issue) ficam na definição.

## Verificações

`r2 glossary check` informa os problemas abaixo, sem alterar o arquivo:

- dois termos com o mesmo nome;
- uma palavra de `avoid` que é o nome de outro termo;
- uma entrada de `related` que não bate com nenhum termo.

## Leitura tolerante

- Um arquivo sem frontmatter é lido da mesma forma.
- Sem um H1, o título é `Glossary`.
- Sem uma linha `---`, a introdução é o texto antes do primeiro título de nível 2.
- Chaves de campo desconhecidas são mantidas e gravadas de volta.
- Um termo sem definição é mantido, com a definição vazia.

## Futuro: polissemia

Uma palavra que tem significados diferentes em contextos diferentes pode ser escrita, no futuro, como um termo por contexto, com o contexto entre parênteses: `## Account (Billing)` e `## Account (Auth)`. Até lá, os parênteses fazem parte do nome do termo.
