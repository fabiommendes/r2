---
type: adr
status: accepted
created: 2026-09-30
decided: 2026-09-30
---

# Não é uma UI de git

> Importado do reportlab, onde era a ADR 0006.

Status: aceito, 2026-09-30

## Contexto

Quando existe uma UI web local capaz de ler um repositório, tudo parece adjacente: log de
commits, blame, staging, gestão de branches, busca no projeto inteiro. Cada um é algumas
horas de trabalho, e cada um já tem várias implementações melhores.

## Decisão

O reportlab implementa só o que serve para revisar a entrega de um agente:

- um navegador sobre a pasta de relatórios, do mais novo para o mais antigo, mostrando
  o que ainda não foi lido;
- uma página de relatório em que toda afirmação aponta para o código, atualizada ao vivo
  enquanto o agente reescreve o arquivo;
- uma visão de arquivo da árvore de trabalho, com os achados do relatório que o cita na
  margem;
- um painel de orientação por arquivo: outline, e usos do símbolo sob o cursor;
- uma varredura: os achados de um relatório como uma lista de verificação.

Nem existe diff. Revisar o que mudou é a única coisa que o `lazygit` e uma forja fazem
melhor, e o registro 0009 removeu o último motivo que o reportlab tinha para duplicar isso.

Explicitamente não implementado: staging, commit, branches, rebase, log de commits, blame,
navegação de histórico, edição e busca no projeto inteiro como página de destino. A busca
existe sobre os relatórios, e sobre o repositório apenas a serviço de uma pergunta feita
a partir de uma visão de arquivo.

## Alternativas rejeitadas

**Um navegador geral de repositório, com relatórios como uma funcionalidade.** Compete com
o `lazygit`, com forjas e com editores no terreno deles, e o trabalho que diferencia a
ferramenta fica sem espaço por causa do volume de funcionalidades básicas.

## Consequências

- Os usuários mantêm as ferramentas que já usam, e recorrem ao reportlab para uma coisa só.
- Toda sugestão de funcionalidade é medida por uma pergunta: isso ajuda um humano a se
  orientar dentro da entrega de um agente? A maioria das respostas é não. Desde o registro
  0009, a pergunta tem uma segunda parte: isso ainda faz sentido se o relatório for
  apagado amanhã?
- A UI precisa de bons links para o editor e para a forja, já que ela deliberadamente
  para antes deles.
