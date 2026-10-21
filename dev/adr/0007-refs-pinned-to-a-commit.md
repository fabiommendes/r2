---
type: adr
status: superseded
created: 2026-09-30
decided: 2026-09-30
supersededBy: 0011-reports-are-ephemeral
---

# Referências são resolvidas contra o commit do relatório

> Importado do reportlab, onde era a ADR 0005.

Status: substituído por `0011-reports-are-ephemeral.md`, 2026-09-30

> Mantido pelo raciocínio, que ainda explica por que resolver contra um alvo em movimento
> é uma falha silenciosa. O registro 0009 elimina o problema em vez de resolvê-lo: um
> relatório é lido minutos depois de escrito, então a árvore de trabalho é o alvo certo,
> e nada precisa ser fixado.

## Contexto

Um relatório cita `src/auth/session.py#L40-58`. O repositório continua andando. Uma
semana depois, esses números de linha apontam para outra coisa, ou para nada.

## Decisão

Um relatório registra `git.commit` no frontmatter, e toda referência nele é resolvida
contra esse commit. A referência git aparece na URL, para que um link seja reproduzível:

```
/p/<project>/f/<ref>/<path>#L10-40
```

`<ref>` é um hash de commit, um nome de branch ou `work` para a árvore de trabalho. A UI
compara o conteúdo fixado com a versão atual e marca a referência como desatualizada,
com um link para as linhas atuais.

## Alternativas rejeitadas

**Resolver contra o `HEAD`.** Um campo a menos e nenhuma parte de git. Todo relatório
fica enganoso em poucos dias, e a falha é silenciosa: as linhas são renderizadas
normalmente, só que são as linhas erradas.

**Copiar o código citado para dentro do relatório.** Sempre correto sobre o passado,
nunca sobre o presente, e deixa os relatórios grandes e caros de escrever.

**Ancorar no conteúdo em vez de números de linha.** Sobrevive a reformatações, exige
correspondência aproximada e falha exatamente no caso interessante, em que o código
mudou. A detecção de desatualização cobre esse caso de forma honesta.

## Consequências

- `git.commit` é fortemente recomendado em todo relatório. Sem ele, as referências são
  resolvidas contra a árvore de trabalho e só estão corretas se forem lidas logo.
- Ler blobs históricos arbitrários é uma operação central, e não um extra.
- Desatualização é um estado de primeira classe da UI, e não um erro.
