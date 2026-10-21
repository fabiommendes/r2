---
type: adr
status: accepted
created: 2026-09-30
decided: 2026-09-30
---

# Um daemon para todos os projetos

> Importado do reportlab, onde era a ADR 0002.

Status: aceito, 2026-09-30

## Contexto

Um desenvolvedor roda agentes em vários repositórios ao mesmo tempo. Os relatórios
chegam de todos eles.

## Decisão

Um único daemon atende todos os projetos registrados.

- Registro em `~/.config/reportlab/projects.json`. Um projeto é registrado na primeira
  vez que o `rl` roda dentro dele.
- Estado de execução em `~/.local/state/reportlab/daemon.json`: pid, porta e bearer
  token, gravados sob um arquivo de lock. Porta 7717 quando estiver livre, qualquer
  porta livre caso contrário.
- O `rl` lê esse arquivo e inicia um daemon destacado quando ele não existe.
- A UI tem um seletor de projetos. Os watchers começam sob demanda por projeto e param
  após um período de inatividade.

## Alternativas rejeitadas

**Um daemon por repositório**, com a porta derivada de um hash do caminho. É mais simples
de implementar e mais isolado, mas significa vários processos, várias portas e várias
abas do navegador, e o usuário precisa controlar qual é qual.

**Sem daemon: um site estático regenerado a cada escrita.** Simples de um jeito atraente,
mas descarta as atualizações ao vivo, o canal reverso e qualquer visão que precise ler
o repositório no momento da requisição.

## Consequências

- Nenhum comando pede uma porta ao usuário.
- O daemon guarda caminhos de muitos repositórios, o que torna o confinamento de
  caminhos por projeto um requisito de segurança, e não um detalhe.
- O ciclo de vida dos watchers vira trabalho real: os handles do inotify são finitos, e
  um monorepo consome muitos.
- Uma falha derruba todos os projetos ao mesmo tempo.
