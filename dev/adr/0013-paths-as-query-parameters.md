---
type: adr
status: accepted
created: 2026-09-30
decided: 2026-09-30
---

# Caminhos trafegam como query parameters

> Importado do reportlab, onde era a ADR 0011.

Status: aceito, 2026-09-30

## Contexto

Dois tipos de caminho são endereçados o tempo todo: um caminho de relatório, dentro de
`.reportlab/reports/`, e um caminho de arquivo na árvore de trabalho. Os dois contêm barras.

A primeira versão os colocava no caminho da URL: `GET /api/p/<id>/report/<path>` e, no
navegador, uma rota planejada `/p/<id>/r/<report>/f/<file>`. Três problemas surgiram disso,
em ordem de quanto custaram.

A rota contextual do navegador não pode ser roteada. Os dois segmentos são caminhos de
tamanho variável, e nenhum roteador consegue dizer onde termina o caminho do relatório e
onde começa o caminho do arquivo. Isso não é uma limitação de um roteador específico; a URL
é ambígua.

O servidor precisava recuperar o caminho cortando um prefixo conhecido de `c.req.path` e
decodificando à mão, porque um wildcard do framework entrega o segmento bruto, e as regras de
decodificação de um wildcard com vários segmentos são o tipo de coisa que fica sutilmente
errada por um ano.

E codificar em percent uma barra dentro de um segmento de caminho é o único caso em que
`decodeURIComponent` aplicado ao caminho inteiro e aplicado a cada segmento dá resultados
diferentes, que é exatamente o formato de um bug de path traversal.

## Decisão

Todo caminho é um query parameter, na API e no navegador:

```
GET /api/p/<id>/report?path=<report>
GET /api/p/<id>/file?path=<file>
PUT /api/p/<id>/marks?path=<report>
/p/<id>/f?path=<file>#L10-40
```

Uma etapa de codificação em cada direção, um único lugar de onde o valor vem e uma tabela de
rotas sem wildcards.

O intervalo de linhas fica no fragmento, porque um fragmento é aquilo para onde o navegador
rola e o que um humano espera poder editar à mão.

O relatório de onde um arquivo foi aberto não fica na URL. É estado de componente na SPA: a
página sabe de onde o leitor veio sem colocar isso no endereço, e um link de arquivo colado
funciona sem essa informação.

## Alternativas rejeitadas

**Codificar em percent o caminho do relatório em um único segmento**:
`/p/<id>/r/reviews%2Fauth/f/<file>`. Mantém a hierarquia visível na barra de endereço, ao custo
de torná-la ilegível, e não elimina a decodificação manual.

**Wildcards com uma regra de decodificação documentada.** Mais barato de escrever do que de manter
correto. As rotas que importam aqui servem o conteúdo do repositório do usuário.

## Consequências

- `safeReportPath` e `normalizeRepoPath` são os únicos validadores, e rodam sobre um valor que
  chegou como uma string só.
- As rotas do M1 mudaram de formato. Nada depende delas além deste repositório: a API não é um
  contrato publicado, diferente de `.reportlab/`.
- Uma visão de arquivo não tem contexto de relatório na URL, então tudo que precisa desse contexto,
  como mostrar os achados de um relatório na margem, trabalha a partir do estado, e não do endereço.
