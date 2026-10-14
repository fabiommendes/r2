---
type: adr
status: accepted
created: 2026-10-13
decided: 2026-10-13
---

# incorporar o reportlab ao r2

O reportlab passa a ser parte do r2: backend em Python com FastAPI, front
SolidJS mantido em `web/` no mesmo repositório.

## Contexto

O reportlab (TypeScript, M1 e M2 prontos) e o r2 cobrem o mesmo escopo. A
duplicação não é só de tipos: detecção de referências (`r2/core/links.py` e
`packages/render` + `packages/scan` no reportlab), threads e leitura de docs
existem nas duas linguagens.

## Opções

- Repositórios separados com tipos em formato neutro (JSON Schema, protobuf):
  sincroniza tipos, mas a lógica continua implementada duas vezes.
- r2 expõe uma API HTTP e o front SolidJS continua: a lógica fica só em
  Python, e os tipos TS são gerados do OpenAPI.
- Portar a UI para Python com htmx ou unpoly: uma linguagem só, mas descarta a
  UI atual, e o M4 (símbolo sob o cursor, outline, findings na margem) é
  interação no cliente.

## Decisão

- Backend em Python, em `r2/web/`, com FastAPI, como extra opcional `web`.
- Front SolidJS em `web/`, no mesmo repositório (monorepo).
- Modelos pydantic são a única fonte de verdade. O front usa
  `openapi-typescript` + `openapi-fetch`, sem zod. Os modelos dos eventos SSE
  entram no OpenAPI como `components`.
- O layout de `.reportlab/` e o frontmatter dos relatórios não mudam na
  migração. Renomear é decisão separada.

## Consequências

- O port de `core`, `render`, `store`, `scan` e `server` (~4-5k linhas TS) vai
  para Python. `markdown-it-py` segue a API do `markdown-it`.
- O highlighting passa para o browser (shiki), fora do backend.
- O wheel empacota o bundle do front. Node só é necessário para desenvolver o
  front.
- O CI regenera os tipos do OpenAPI e falha se houver diff.
