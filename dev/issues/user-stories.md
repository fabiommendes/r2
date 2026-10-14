---
type: issue
status: backlog
tags: [stories, tests, cli, tui]
relatedTo: [tooling-root/dev/adr/0003-modelo-de-repositorio.md, codehood/codehood/docs/user-stories/README.md]
kind: enhancement
created: 2026-10-14
---

# User stories: formato, CRUD e mapeamento para testes e2e

O ADR 0003 do tooling-root põe as user stories no repositório como um contrato
vivo, conferido por ferramenta. O r2 lista as stories, oferece um CRUD e confere
se as stories e os testes e2e estão mapeados nos dois sentidos.

O `codehood` já faz isso com um script próprio (`pnpm run stories`). O README
dele (`codehood/codehood/docs/user-stories/README.md`) é a referência do formato
e serve de fixture de aceitação.

## Formato proposto

Um arquivo por papel em `docs/user-stories/<papel>.md`:

```markdown
---
type: stories
status: active
role: student
---

# Student user stories

<o que o papel é e o que ele pode fazer>

## <seção>

### Log in

    status: implemented
    url: /login

<narrativa: o que o usuário quer, o que faz e com o que termina>
```

- O ID da story é `<papel>: <slug do título>`. Dois títulos com o mesmo slug no
  mesmo arquivo são um erro.
- O bloco indentado é YAML, todo opcional:
  - `status`: `todo` (padrão), `partial`, `implemented`, `deprecated`. Valores
    desconhecidos, como o `web` e `cli` do codehood, são mantidos e contam como
    `partial`.
  - `url`: a página onde a story acontece, quando há uma só.
  - `relatedTo`: issues e ADRs.
- Leitura tolerante e escrita estrita, como em `issues.md`.

## Ligação com os testes

- Um teste e2e cita a story pelo ID:
  - vitest e playwright: o título do teste é o ID (`"student: log in"`);
  - pytest: `@pytest.mark.story("student: log in")`;
  - nextest: a decidir.
- O que conta como teste e2e é configurável: uma pasta (`test/stories/`) ou um
  runner (`playwright`). A descoberta reaproveita a do `r2 coverage`.

## Comandos

`r2 story list | show | new | set | remove | fmt | check`, com as mesmas
convenções de `r2 glossary`.

`r2 story check` informa, e sai com código 1:

- uma story `implemented` ou `partial` sem teste;
- um teste e2e que cita uma story que não existe, ou que não cita nenhuma;
- slugs repetidos num arquivo;
- com `--no-duplicates`, uma story com mais de um teste.

Modos só de leitura, como no codehood: `--missing`, `--covered`, `--stale`. Um
teste de story `todo` gera aviso, não erro.

## Questões abertas

- Gerar um relatório de cobertura em arquivo (o `coverage.md` do codehood) ou
  só imprimir?
- Uma visão na TUI, ao lado de issues e ADRs?
