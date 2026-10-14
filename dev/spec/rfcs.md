---
type: spec
status: active
tags: [rfc, design, frontmatter, markdown]
relatedTo: [issues, adrs, tooling-root/dev/adr/0003-modelo-de-repositorio.md]
---

# Arquivos de RFC

Os RFCs ficam em `dev/rfc/<slug>.md`, um arquivo por RFC. Um RFC é onde o humano e um agente desenham uma funcionalidade antes de especificá-la (ADR 0003 do tooling-root). O corpo é vivo enquanto o RFC é `draft` e mostra o desenho atual; os comentários guardam a discussão. Quando o humano decide, o RFC congela e lista o que gerou: user stories, ADRs e issues.

O nome do arquivo é um slug, sem número, como nas issues: agentes criam RFCs em paralelo, e um número sequencial colidiria. O slug não muda depois da criação. O id do RFC é o slug.

Um arquivo é Markdown simples com frontmatter em YAML. O r2 lê qualquer arquivo Markdown dessa pasta (leitura tolerante) e sempre escreve o formato abaixo (escrita estrita). As regras comuns com as issues (comentários, ordem de escrita, leitura tolerante) seguem [issues](issues.md), salvo quando esta especificação disser o contrário.

## Frontmatter

`type` e `status` são sempre escritos. Qualquer outra chave é opcional e fica de fora quando tem o valor padrão.

| Chave | Valores | Padrão | Origem |
| --- | --- | --- | --- |
| `type` | `rfc` | obrigatório | base |
| `status` | ver abaixo | obrigatório, `draft` na criação | |
| `tags` | lista de strings | `[]` | base |
| `relatedTo` | lista de slugs de entidades ou caminhos | `[]` | base |
| `created` | data, `YYYY-MM-DD` | preenchido na criação | `dcterms:created` |
| `decided` | data, `YYYY-MM-DD` | nenhum | `dcterms:dateAccepted` |
| `creator` | texto livre | nenhum | `dcterms:creator` |

`decided` guarda a data em que o RFC saiu de `draft`, seja aceito, rejeitado ou retirado. Voltar para `draft` apaga a data.

### Status

- `draft`: aberto. É o único status em que o RFC é editado.
- `accepted`, `rejected`, `withdrawn`: fechados.

`rejected` é a decisão do humano contra a proposta. `withdrawn` é quem propôs desistir dela antes da decisão.

`r2 rfc advance` e o botão da TUI seguem `draft`, `accepted`, `rejected` e de volta a `draft`, como nos ADRs. `withdrawn` sai do menu de status e avança para `draft`.

## Corpo

O corpo começa com um título de nível 1, que traz o título, seguido destas seções, como títulos de nível 2, nesta ordem:

- `Problem`: o que falta e para quem.
- `Proposal`: o desenho atual. Ele muda a cada rodada da discussão, sem guardar o histórico.
- `Alternatives`: as opções descartadas, cada uma com o motivo.
- `Open questions`: as dúvidas que ainda mudam o desenho.
- `Outcome`: vazio até a decisão. Num RFC aceito, lista os caminhos das stories, ADRs e issues que ele gerou. Num RFC rejeitado ou retirado, traz o motivo.

O r2 escreve esses títulos na criação. Na leitura, ele não os exige. Os títulos ficam em inglês, como o código.

Os comentários funcionam como nas issues: uma linha só com `---`, fora de blocos de código, começa um comentário, que pode ser aberto por uma linha `by: <who>`. Eles guardam a troca que levou a uma escolha quando o motivo não cabe no corpo. Os RFCs não têm plano: checkboxes no corpo não contam progresso.

```markdown
---
type: rfc
status: accepted
tags: [layout]
relatedTo: [dev/adr/0003-one-layout.md]
created: 2026-10-07
decided: 2026-10-09
creator: claude
---

# One layout for every repository

## Problem

...

## Proposal

...

## Alternatives

...

## Open questions

## Outcome

- dev/adr/0003-one-layout.md
- dev/issues/align-dev-layout.md

---
by: fabio

Keep the ADRs numbered: they go through me anyway.
```

## Decisão

Só o humano aceita, rejeita ou retira um RFC. Ao aceitar, quem conduz o RFC (a skill `rfc`) cria cada artefato com os comandos que já existem (`r2 adr new`, `r2 issue new`, as stories à mão), lista os caminhos em `Outcome` e só então muda o status. O r2 não tem um comando que gera os artefatos a partir de `Outcome`.

Um RFC decidido não é editado. O r2 não impede a edição: a regra é de quem escreve.

## Leitura tolerante

- Um arquivo sem frontmatter é um RFC com status `draft`.
- Um arquivo sem H1 pega o título do nome do arquivo.
- Chaves e valores desconhecidos são mantidos e mostrados como estão.
- Um frontmatter quebrado é tratado como parte do corpo.
