---
type: adr
status: accepted
created: 2026-09-30
decided: 2026-09-30
---

# Relatórios são Markdown com blocos tipados

> Importado do reportlab, onde era a ADR 0004.

Status: aceito, 2026-09-30

## Contexto

Os relatórios precisam ser ricos o bastante para achados, tabelas e diffs, e baratos o
bastante para que um agente escreva um sem cerimônia. Agentes produzem bom Markdown e
JSON medíocre, e produzem demais de qualquer um dos dois quando o formato convida a isso.

## Decisão

Um relatório é Markdown com frontmatter YAML. Conteúdo estruturado é um bloco cercado
cuja tag de linguagem começa com `rl:`, com atributos `chave=valor` depois da tag.

Duas propriedades são o ponto central:

- **Degradação elegante.** Sem o reportlab, o arquivo continua sendo um documento legível
  em um terminal, em um pull request ou no `git log`. O navegador só o melhora.
- **Referência, não cópia.** O código entra em um relatório como uma referência, por
  exemplo `src/auth/session.py#L40-58`, resolvida no momento da renderização. O relatório
  continua pequeno, nunca carrega código desatualizado, e cada afirmação vira um link
  para o repositório.

`packages/render` produz uma AST tipada do documento, e não uma string HTML. A UI monta
componentes interativos para esses blocos, e um relatório é entrada não confiável.

## Alternativas rejeitadas

**Documentos em JSON ou YAML.** Amigáveis para máquinas, ilegíveis sem a ferramenta, e
agentes escrevem prosa pior dentro de campos de string.

**HTML escrito pelo agente.** Flexibilidade máxima, sem degradação, e uma superfície de
injeção em uma página que guarda um token para o repositório inteiro.

**MDX ou uma sintaxe própria.** Exige uma cadeia de ferramentas específica só para ler o
arquivo, o que anula a primeira propriedade.

## Consequências

- O vocabulário de blocos é um contrato publicado e precisa continuar pequeno.
- O leitor precisa ser tolerante: blocos desconhecidos e campos de frontmatter
  desconhecidos degradam em vez de falhar, porque quem escreve está em outro repositório
  e ninguém o atualiza.
- HTML bruto no corpo de um relatório é removido, e não sanitizado e mantido.
