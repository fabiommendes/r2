---
type: adr
status: accepted
created: 2026-09-30
decided: 2026-09-30
---

# markdown-it, e referências detectadas em prosa

> Importado do reportlab, onde era a ADR 0007.

Status: aceito, 2026-09-30

Estende `0006-markdown-with-typed-blocks.md`, que definiu o formato, mas não o parser.

## Contexto

Duas necessidades pesam na escolha do parser.

A primeira são as cercas `rl:`, que qualquer parser de Markdown trata, já que uma cerca
com uma string de informação incomum continua sendo uma cerca.

A segunda é mais difícil e mais valiosa. Agentes escrevem caminhos em prosa o tempo todo,
e os escrevem na forma que as ferramentas deles imprimiram: `src/a.ts:42`, vindo de um
compilador ou do ripgrep, e `src/a.ts` dentro de uma frase. Pedir a um agente que envolva
cada um deles em sintaxe explícita de link é uma regra que ele seguirá oitenta por cento
das vezes, e os vinte por cento restantes são exatamente as menções incidentais mais úteis
para clicar. Detectá-las vale mais do que instruí-las.

## Decisão

`markdown-it`, consumido como fluxo de tokens em vez de pelo renderizador HTML, com dois
plugins:

- uma regra de bloco para as cercas `rl:`;
- uma regra do core, executada depois do parsing inline, que divide os tokens de texto
  nas referências detectadas.

`html: false` em `MARKDOWN_IT_OPTIONS` é uma fronteira de segurança, e não uma preferência:
HTML bruto em um relatório é escapado pelo parser e nunca chega a um token, o que aplica a
regra de remoção na origem, e não depois.

A detecção é **em duas fases**, e a divisão é o ponto central:

1. `render` encontra os candidatos. É puro e não faz E/S, então não tem como saber se
   `src/a.ts` existe. Ele emite um nó inline `candidate`.
2. O servidor resolve cada candidato único contra a árvore de trabalho, por meio de `scan`.
   Os candidatos resolvidos viram links; os não resolvidos são renderizados como texto simples.

Como a segunda fase é o filtro de verdade, a primeira pode ser generosa. Um falso positivo
custa uma consulta na árvore, e não um link quebrado na página. O que é detectado hoje:
caminhos com extensão, nas duas formas de locator `:42` e `#L10-40`, hashes de commit e
ids de relatório.

## Alternativas rejeitadas

**remark e unified**, a primeira escolha deste projeto. Têm um modelo de árvore melhor e um
ecossistema maior, mas adicionar sintaxe inline nova exige escrever uma extensão do
micromark, que é uma máquina de estados sobre bytes. Os rulers inline e do core do
markdown-it fazem o mesmo trabalho em poucas linhas, e a detecção inline é o requisito
que mais importa aqui.

**Renderizar HTML a partir do markdown-it com regras de renderização próprias.** É a saída
natural do parser, mas abre mão dos componentes interativos e reabre a superfície de
injeção que `html: false` e a AST tipada fecham.

**Exigir sintaxe explícita de link para toda referência.** Nenhum código de detecção, nenhum
falso positivo, e joga o ônus para o agente, que é onde a conformidade vai morrer.

**Resolver os candidatos dentro do parser.** Uma fase em vez de duas, ao custo de acesso ao
sistema de arquivos em `render`, que é o invariante que todo o layout de pacotes existe
para manter.

## Consequências

- As páginas de relatório dependem de uma consulta ao sistema de arquivos para decidir o que
  é link. Um candidato não resolvido é um resultado normal, e não um erro.
- Os padrões de detecção são uma fonte de surpresas, então têm testes para o que não podem
  casar: URLs, endereços de e-mail, números de versão, inteiros simples.
- Agentes podem escrever caminhos do jeito que escrevem naturalmente. A skill ainda ensina
  referências explícitas para os achados, onde a referência é dado estruturado, e não prosa.
- Diretórios sem extensão não são detectados nesta versão. `and/or` parece exatamente um
  caminho, e a consulta na árvore resolveria `src/auth` corretamente, mas a lista de
  candidatos ficaria cheia de ruído.
