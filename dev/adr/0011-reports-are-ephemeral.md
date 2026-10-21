---
type: adr
status: accepted
created: 2026-09-30
decided: 2026-09-30
supersedes: [0007-refs-pinned-to-a-commit]
---

# Relatórios são efêmeros

> Importado do reportlab, onde era a ADR 0009.

Status: aceito, 2026-09-30

Substitui `0007-refs-pinned-to-a-commit.md`.

## Contexto

O desenho até aqui assumia que um relatório é um artefato que vale a pena guardar: fixado
ao commit em que foi escrito, detectado como desatualizado semanas depois, versionado junto
com o código e viajando em um pull request. Cada uma dessas premissas trazia uma máquina
própria. A fixação exigia parte de git na CLI. Um relatório sobre trabalho não commitado
exigia um modo para árvore suja ou snapshots de blobs gravados no banco de objetos do
usuário. Persistir o estado de revisão exigia um ciclo de vida próprio.

A premissa estava errada. A maioria dos relatórios é lida uma vez, em minutos depois de
escrita, por um humano sentado ao lado do agente que a escreveu. Eles são a saída de uma
sessão de trabalho, e não o registro dela.

## Decisão

**Um relatório é um rascunho descartável.** O `rl` é um visualizador.

- O agente escreve um arquivo Markdown em uma pasta previsível. Não há comando a executar
  nem handshake. O watcher percebe um arquivo novo ou alterado, e a página é atualizada.
- Um relatório pode ser reescrito no lugar enquanto o trabalho avança. O humano vê o
  conteúdo se completar. Um arquivo incompleto renderiza o que tem; uma cerca sem fechamento
  renderiza como bloco aberto, nunca como erro.
- As referências são resolvidas contra a **árvore de trabalho**. Não há commit fixado, leitura
  de blob histórico, snapshot de blob nem parte de git na CLI. O relatório trata do código
  como ele está agora, porque é lido agora.
- A desatualização se reduz a uma comparação, sem envolver git: o arquivo citado é mais novo
  que o relatório. Mostrada como nota, não como erro.
- `.reportlab/` é ignorado pelo git por inteiro. Relatórios nunca chegam a um commit ou a um
  pull request.
- **Persistir é um pedido explícito.** Quando algo vale a pena guardar, o humano pede ao agente,
  e o agente escreve um documento comum no repositório, onde documentos devem ficar. O
  reportlab renderiza esses documentos também, pelo navegador, mas não é dono deles e não tem
  funcionalidade de "promover".

Esse último ponto é o que torna o resto barato: a fronteira entre descartável e permanente é
uma fronteira de diretório que já existe, decidida por um humano em uma frase, e não um ciclo
de vida que a ferramenta precise modelar.

## Alternativas rejeitadas

**Manter o arquivo, com fixação e detecção de desatualização.** Correto para o relatório que
é lido três semanas depois, mas esse relatório é raro o bastante para que pagar por ele em
todos os outros seja uma troca ruim. O custo ficava concentrado no pior lugar: o caso mais
comum é um agente relatando trabalho que ainda não foi commitado, exatamente onde um commit
fixado aponta para código que ainda não existe.

**Snapshots de blobs com `git hash-object -w`.** Elegante, mas grava objetos no repositório do
usuário para resolver um problema que só existe se os relatórios forem guardados.

**Uma política de retenção na ferramenta.** Apagar arquivos do usuário por temporizador para
impor uma premissa que o usuário já aceitou. O navegador ordenado por data obtém o mesmo
efeito sem apagar nada.

## Consequências

- A CLI encolhe. Ela inicia o daemon, abre o navegador e instala a skill. Não escreve
  relatórios, então `rl report`, `rl link` e a questão de como um agente passa o corpo
  desaparecem.
- O watcher é todo o caminho de ingestão, o que o torna o componente cuja falha é total. Ele
  recebe os testes que o trabalho com git receberia.
- O stream de eventos fica redundante. Um relatório atualizado ao vivo é um canal de progresso
  melhor do que um segundo, mais fraco, então `events.jsonl` sai desta versão.
- Os handoffs também saem de `.reportlab/`. Um handoff existe para ser lido por uma sessão
  posterior, o que define algo persistente, então ele é um documento comum no repositório.
- As marcas de revisão ficam em um arquivo sidecar ao lado do relatório e morrem com ele, o que
  mantém o índice como um cache puro, sem exceção (`0003-files-are-the-source-of-truth.md`).
- Nada acumula valor com o tempo. Não há consultas entre relatórios que valham a pena, nem
  visões de tendência, nem motivo para busca em texto completo sobre um arquivo.
