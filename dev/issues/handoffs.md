---
type: issue
status: in_review
tags: [handoffs, cli]
relatedTo: [tooling-root/dev/adr/0003-modelo-de-repositorio.md, skills/dev/issues/adr-0003.md]
kind: enhancement
created: 2026-10-14
---

# Handoffs em `dev/handoffs/`

Hoje a skill de handoff grava em `/tmp`. O ADR 0003 do tooling-root move os
handoffs para `dev/handoffs/`, que fica no `.gitignore`. O r2 lista os handoffs,
marca um handoff como retomado e apaga os velhos. Quem escreve o handoff é a
skill, no `skills`.

## Formato proposto

`dev/handoffs/<slug>.md`:

```markdown
---
type: handoff
status: open
issue: <slug da issue>
branch: <branch>
worktree: <caminho>
created: 2026-10-14T15:30
creator: claude
---

# <o que estava sendo feito>

## Estado
## Próximo passo
## Arquivos
```

- `status`: `open` ou `taken`.
- `issue`, `branch` e `worktree` são opcionais.

## Comportamento

- A pasta é sempre a do checkout principal (a primeira linha de
  `git worktree list`), mesmo quando o comando roda numa worktree. Uma worktree
  nova não enxerga os arquivos ignorados de outra.
- O primeiro handoff cria `dev/handoffs/.gitignore` com `*`, como o
  `.r2/.gitignore` do `r2 coverage`.
- `r2 handoff list | show | take | prune`.
- `take` marca o handoff como `taken`, para que dois agentes não retomem o
  mesmo.
- `prune` apaga os handoffs `taken`, os criados há mais de 7 dias e os de issues
  fechadas. `--days N` muda o prazo.

## Plano

- [x] Ler e editar handoffs em `r2/core/handoffs.py`: leitura tolerante do
  formato, troca só da linha `status` ao marcar `taken`, critérios do `prune`.
  A pasta é a do checkout principal (`git worktree list`), com volta para a
  raiz do projeto fora do git.
- [x] `r2 handoff list | show | take | prune` em `r2/cli/handoffs.py`. `take`
  sem id pega o `open` mais recente. Os comandos que escrevem criam o
  `.gitignore` da pasta.
- [x] Testes do módulo e da CLI, inclusive numa worktree.
- [x] Escrever `dev/spec/handoffs.md` e atualizar `dev/spec/cli.md` e o
  `README.md`.
- [x] Checagem completa verde (`task ci`).

---
by: claude

Escolhas:

- O r2 não cria handoffs: quem grava é a skill. Por isso o `.gitignore` da
  pasta é criado pela skill no primeiro handoff e pelo r2 em `take` e `prune`,
  os comandos que escrevem. `list` e `show` não escrevem nada.
- `take` imprime o handoff depois de marcá-lo, para que o agente retome com um
  comando só. Sem id, ele pega o `open` mais recente, como a skill.
- Ao marcar `taken`, o r2 troca só a linha `status` e deixa o resto do arquivo
  como a skill escreveu.
- `prune` não pede confirmação (os handoffs são efêmeros) e só apaga pelo
  `issue` quando a issue existe e está fechada.
- Um `created` ausente ou inválido vale a data de modificação do arquivo.
- Fora de um repositório git, a pasta fica na raiz do projeto, como nos outros
  comandos.
