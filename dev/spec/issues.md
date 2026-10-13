---
type: spec
status: active
tags: [issues, frontmatter, markdown, comments, oslc-cm]
relatedTo: [issues-view, issue-form]
---

# Arquivos de issue

As issues ficam em `dev/issues/<slug>.md`, um arquivo por issue. Um arquivo é Markdown simples com frontmatter em YAML. O R2 lê qualquer arquivo Markdown dessa pasta (leitura tolerante) e sempre escreve o formato abaixo (escrita estrita).

## Frontmatter

`type` e `status` são sempre escritos. Qualquer outra chave é opcional e fica de fora quando tem o valor padrão, para que uma issue nova continue curta.

As quatro primeiras chaves são as que o base lê. As outras pegam os nomes do OSLC Change Management 3.0 e dos termos do Dublin Core, para que possam ser mapeadas para RDF depois, com um contexto JSON-LD, sem mexer nos arquivos.

| Chave | Valores | Padrão | Origem |
| --- | --- | --- | --- |
| `type` | `issue` | obrigatório | base |
| `status` | ver abaixo | obrigatório, `backlog` na criação | base |
| `tags` | lista de strings | `[]` | base |
| `relatedTo` | lista de slugs de entidades ou caminhos | `[]` | base |
| `kind` | `defect`, `enhancement`, `task` | nenhum | `oslc_cm:Defect`, `Enhancement`, `Task` |
| `priority` | `low`, `normal`, `high`, `urgent` | `normal` | `oslc_cm:priority` |
| `severity` | `trivial`, `minor`, `normal`, `major`, `critical` | `normal` | `oslc_cm:severity` |
| `milestone` | nome do milestone | nenhum | `oslc_cm:affectsPlanItem` |
| `parent` | slug de outra issue | nenhum | `oslc_cm:parent` |
| `blocks` | lista de slugs de issues | `[]` | |
| `created` | data, `YYYY-MM-DD` | preenchido na criação | `dcterms:created` |
| `creator` | texto livre | nenhum | `dcterms:creator` |
| `closed` | data, `YYYY-MM-DD` | nenhum | `oslc_cm:closeDate` |

`milestone` limita a issue a um milestone. Sem ele, a issue não pertence a nenhum milestone em específico.

### Status

O ciclo de vida do base, mais dois estados finais:

- `backlog`, `todo`, `in_progress`, `blocked`, `deferred`, `in_review`: abertos.
- `completed`, `wont_fix`, `deprecated`: fechados.

### Ordem de escrita

As chaves são escritas na ordem da tabela. Listas usam o estilo de fluxo (`tags: [a, b]`). Chaves que o r2 não conhece são mantidas como estão, depois das conhecidas.

## Corpo

O corpo começa com um título de nível 1, que traz o título, seguido da descrição.

Uma linha que contém só `---`, fora de blocos de código, começa um comentário. Os comentários são lidos de cima para baixo, como um fórum. Um comentário pode começar com uma linha `by: <who>`, que diz quem escreveu; a linha não faz parte do texto. A descrição não tem linha `by:`: o autor dela é o `creator`.

```markdown
---
type: issue
status: todo
kind: defect
created: 2026-10-02
---

# The preview loses the cursor after an edit

Steps to reproduce...

---
by: fabio

It happens only with excerpts.

---
by: claude

Found the cause: `reload()` resets the selection.
```

## Leitura tolerante

- Um arquivo sem frontmatter é uma issue com status `backlog`.
- Um arquivo sem H1 pega o título do nome do arquivo.
- Chaves e valores desconhecidos são mantidos e mostrados como estão.
- Um frontmatter quebrado é tratado como parte do corpo.
