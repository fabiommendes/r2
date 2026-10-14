---
type: issue
status: in_review
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

## Plano

- [x] `r2/core/stories/`: leitura tolerante e escrita estrita dos arquivos
  de stories, ID `<papel>: <slug>`, configuração da pasta de stories e das
  pastas de teste e2e (`[config.stories]` no manifesto do projeto).
- [x] Descoberta estática dos testes e2e: título em vitest/playwright, marker
  `story` no pytest. Sem rodar o runner.
- [x] `check`: stories `implemented`/`partial` sem teste, testes que citam
  story inexistente ou nenhuma, slugs repetidos, `--no-duplicates`, aviso para
  teste de story `todo`; modos `--missing`, `--covered`, `--stale`; resumo da
  cobertura impresso.
- [x] `r2 story list | show | new | set | remove | fmt | check` em
  `r2/cli/stories.py`.
- [x] Fixture de aceitação com um recorte do codehood em `tests/examples/`, e
  testes do formato, da descoberta e da CLI.
- [x] Escrever `dev/spec/stories.md` e atualizar `dev/spec/cli.md` e o
  `README.md`.
- [x] Issues em `backlog` para o trabalho adiado (TUI, nextest, arquivo de
  cobertura).
- [x] Checagem completa verde (`task ci`).

---
by: claude

Escolhas:

- O código fica no pacote `r2/core/stories/` (`doc.py`, `tests.py`,
  `check.py`) e a CLI em `r2/cli/stories.py`. A spec está em
  `dev/spec/stories.md`, com os comandos no `dev/spec/cli.md` (requisitos 45 a
  50).
- O slug remove acentos antes (`Configuração` vira `configuracao`). Nos títulos
  ASCII do codehood, o resultado é o mesmo do script dele.
- A descoberta dos testes é estática: o r2 lê os arquivos e não roda nenhum
  runner, nem as listagens (`playwright test --list`, `pytest --collect-only`).
  Assim o `check` roda sem `node_modules` e sem o ambiente do projeto. O custo:
  títulos montados em tempo de execução (template com `${}`, `test.each`) e
  markers com valor não literal não são vistos.
- Os testes e2e são escolhidos por pasta: `--tests`, depois `tests` em
  `[config.stories]` do manifesto do projeto (`r2.toml` ou `[tool.r2]`),
  depois `test/stories` ou `tests/stories`. Todo teste nessas pastas precisa
  citar uma story. Escolher por runner ficou para a issue
  `stories-coverage-file`.
- A raiz do projeto é a de `r2 coverage` (pasta com `pyproject.toml`,
  `Cargo.toml` ou `package.json`), não a do git: no codehood, o app fica em
  `codehood/codehood`.
- Um status desconhecido conta como `partial` e precisa de teste. `deprecated`
  é tratado como `todo`: não precisa de teste, e um teste dele gera aviso.
- Dois arquivos com o mesmo `role` são erro, e o segundo é ignorado.
- `fmt` sempre escreve `status`, também `todo`. O codehood fica com um bloco a
  mais em cada story sem status.
- `--missing`, `--covered` e `--stale` são opções de `check`, como no codehood.
  A cobertura é impressa por papel no fim do `check`; não há `coverage.md`.
- `set --section` move a story para o fim da seção; não há como escolher a
  posição.

No codehood real (só leitura), `r2 story check` sai com 1 e informa 9 stories
`cli` sem teste (3 de admin, 6 de instructor). A cobertura bate com o
`coverage.md` dele: admin 9 de 16, instructor 16 de 27, student 20 de 21.
`--stale` não lista nada.

Trabalho adiado, em `backlog`: `stories-tui`, `stories-nextest` e
`stories-coverage-file`.

Achado fora do escopo: `r2 issue new` com título acentuado gera slugs como
`vis-o-de-...` (`threads.slugify` descarta as letras acentuadas). Renomeei os
arquivos à mão.
