---
type: spec
status: active
tags: [handoffs, frontmatter, markdown, worktree]
relatedTo: [issues, cli]
---

# Arquivos de handoff

Um handoff guarda o estado de uma sessão interrompida, para que outro agente continue o trabalho sem o contexto da conversa (ADR 0003 do tooling-root). Quem escreve o handoff é a skill `handoff` do repositório `skills`. O r2 lista, mostra, marca como retomado e apaga.

## Pasta

Os handoffs ficam em `dev/handoffs/<slug>.md` do checkout principal: a primeira entrada de `git worktree list`. Vale também quando o comando roda em outra worktree, porque uma worktree nova não vê os arquivos ignorados das outras. Fora de um repositório git, a pasta fica na raiz do projeto ([cli.md](cli.md#glossário), requisito 19).

A pasta fica fora do git: ela tem um `.gitignore` com uma linha, `*`. Quem escreve na pasta cria esse arquivo se ele não existir, seja a skill ao gravar o primeiro handoff, seja o r2 em `take` e `prune`.

O slug é o da issue em andamento ou, sem issue, um slug curto do trabalho. Se o arquivo já existir, a skill acrescenta `-2`, `-3`...

## Formato

```markdown
---
type: handoff
status: open
issue: preview-bug
branch: preview-bug
worktree: /home/fabio/git/r2-preview-bug
created: 2026-10-14T15:30
creator: claude
---

# Corrigir o cursor do preview

## Estado
## Próximo passo
## Arquivos
```

| Chave | Valores | Obrigatória |
| --- | --- | --- |
| `type` | `handoff` | sim |
| `status` | `open` ou `taken` | sim |
| `issue` | slug de uma issue em `dev/issues/` | não |
| `branch` | nome da branch | não |
| `worktree` | caminho absoluto da worktree | não |
| `created` | data e hora local, `YYYY-MM-DDTHH:MM` | sim |
| `creator` | texto livre | não |

O corpo começa com um título de nível 1, o que estava sendo feito, e segue com as seções `Estado`, `Próximo passo` e `Arquivos`, com os títulos na língua de `dev/` do repositório. O r2 não lê as seções e não divide o corpo em comentários: uma linha `---` no corpo é texto.

## Status

- `open`: espera um agente.
- `taken`: um agente retomou o handoff. Ele não volta para `open`.

Retomar um handoff é mudar o `status` para `taken` antes de qualquer outra coisa, para que dois agentes não retomem o mesmo. `r2 handoff take` faz isso sob o lock da pasta e falha quando o handoff não está `open`.

## Escrita

O r2 só muda a linha `status` do frontmatter. O resto do arquivo fica como foi escrito, inclusive a ordem e o estilo das outras chaves. Um frontmatter sem `status` ganha a linha depois de `type`. Um arquivo sem frontmatter ganha um com `type` e `status`.

## Limpeza

`r2 handoff prune` apaga:

- os handoffs `taken`;
- os criados há mais de 7 dias (`--days N` muda o prazo);
- os que têm `issue` de uma issue fechada em `dev/issues/` do checkout principal. Uma issue que não existe não apaga o handoff.

## Leitura tolerante

- Um arquivo sem frontmatter, ou sem `status`, é um handoff `open`.
- Um arquivo sem H1 pega o título do nome do arquivo.
- Um `created` ausente ou que não é data e hora ISO vale a data de modificação do arquivo. Um `created` só com data vale a meia-noite desse dia.
- Chaves desconhecidas são mantidas e mostradas como estão.
