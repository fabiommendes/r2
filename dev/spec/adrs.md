---
type: spec
status: active
tags: [adr, decisions, frontmatter, markdown, madr]
relatedTo: [issues, adr-view]
---

# Arquivos de ADR

Os registros de decisão de arquitetura (ADRs) ficam em `dev/adr/NNNN-<slug>.md`, um arquivo por decisão. `NNNN` é um número de sequência com zeros à esquerda, que começa em `0001`. Ele é o id do ADR (citado como "ADR-12") e não se repete no frontmatter. Novos ADRs recebem o maior número da pasta mais um.

Um arquivo é Markdown simples com frontmatter em YAML. O r2 lê qualquer arquivo Markdown dessa pasta (leitura tolerante) e sempre escreve o formato abaixo (escrita estrita). As regras comuns com as issues (comentários, ordem de escrita, leitura tolerante) seguem [issues](issues.md), salvo quando esta especificação disser o contrário.

## Frontmatter

`type` e `status` são sempre escritos. Qualquer outra chave é opcional e fica de fora quando tem o valor padrão.

As quatro primeiras chaves são as que o base lê. As outras pegam os nomes do MADR e dos termos do Dublin Core, para que possam ser mapeadas para RDF depois, com um contexto JSON-LD.

| Chave | Valores | Padrão | Origem |
| --- | --- | --- | --- |
| `type` | `adr` | obrigatório | base |
| `status` | ver abaixo | obrigatório, `proposed` na criação | MADR |
| `tags` | lista de strings | `[]` | base |
| `relatedTo` | lista de slugs de entidades ou caminhos | `[]` | base |
| `created` | data, `YYYY-MM-DD` | preenchido na criação | `dcterms:created` |
| `decided` | data, `YYYY-MM-DD` | nenhum | `dcterms:dateAccepted` |
| `creator` | texto livre | nenhum | `dcterms:creator` |
| `deciders` | lista de strings | `[]` | MADR `decision-makers` |
| `supersedes` | lista de nomes de arquivo de ADR (sem extensão) | `[]` | `dcterms:replaces` |
| `supersededBy` | nome de arquivo de ADR (sem extensão) | nenhum | `dcterms:isReplacedBy` |

`decided` guarda a data em que o ADR saiu de `proposed`, seja aceito ou rejeitado.

As referências a ADRs em `supersedes` e `supersededBy` usam o nome do arquivo sem extensão, com o número (`0003-json-config`).

### Status

O ciclo de vida do Nygard e do MADR:

- `proposed`: aberto.
- `accepted`, `rejected`, `deprecated`, `superseded`: fechados.

Ao contrário das issues, os ADRs não usam o ciclo de vida base: uma decisão não é trabalhada. Ela é proposta e depois resolvida.

### Substituição

Substituir uma decisão escreve os dois lados numa só ação:

- o ADR novo lista o antigo em `supersedes`;
- o ADR antigo recebe `status: superseded` e `supersededBy` apontando para o novo.

A redundância é intencional: quem lê o arquivo antigo vê para onde a decisão foi sem nenhuma ferramenta. Quando os dois lados divergem na leitura, o r2 confia em `supersedes` e mostra o ADR antigo como substituído.

## Corpo

O corpo começa com um título de nível 1, que traz o título, seguido das seções do MADR como títulos de nível 2, nesta ordem:

- `Context`: o problema e as forças em jogo.
- `Options`: as opções consideradas, com prós e contras.
- `Decision`: a opção escolhida e o motivo.
- `Consequences`: o que fica mais fácil ou mais difícil.

O r2 escreve esses títulos na criação. Na leitura, ele não os exige.

Os comentários funcionam como nas issues: uma linha só com `---`, fora de blocos de código, começa um comentário, que pode ser aberto por uma linha `by: <who>`. Eles servem para discussão enquanto o ADR está `proposed`.

```markdown
---
type: adr
status: accepted
tags: [config]
created: 2026-10-07
decided: 2026-10-09
deciders: [fabio, claude]
supersedes: [0003-json-config]
---

# Store the configuration as TOML

## Context

...

## Options

...

## Decision

...

## Consequences

...

---
by: claude

TOML keeps comments, which JSON drops on rewrite.
```

## Leitura tolerante

- Um arquivo sem frontmatter é um ADR com status `proposed`.
- Um arquivo sem H1 pega o título do nome do arquivo, sem o número.
- Um nome de arquivo sem prefixo numérico é aceito; o ADR não tem id.
- Chaves e valores desconhecidos são mantidos e mostrados como estão.
- Um frontmatter quebrado é tratado como parte do corpo.

## Fora do escopo

Os ADRs não são sincronizados com as entidades de decisão do base (`base decision log`). O arquivo do ADR é o único registro.
