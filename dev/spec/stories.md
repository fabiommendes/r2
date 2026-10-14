---
type: spec
status: active
tags: [stories, tests, e2e, markdown]
relatedTo: [cli, coverage, glossary, user-stories]
---

# User stories

As user stories são o contrato vivo entre o que a aplicação promete e o que os testes e2e conferem (ADR 0003 do tooling-root). O r2 lê e escreve os arquivos de stories, encontra os testes e2e que citam cada story e confere a ligação nos dois sentidos.

O formato vem do `codehood` (`pnpm run stories`). O recorte em `tests/examples/stories/codehood/` é a fixture de aceitação.

## Arquivos

1. Cada papel tem um arquivo em `docs/user-stories/<papel>.md`, relativo à raiz do projeto. Todo `.md` da pasta é um arquivo de stories, menos `README.md` e `coverage.md` (sem diferenciar maiúsculas de minúsculas), a não ser que eles declarem `type: stories`.
2. A raiz do projeto é a pasta mais próxima, a partir da atual e subindo, que tem um `pyproject.toml`, `Cargo.toml` ou `package.json`, como em `r2 coverage`. Sem nenhum, é a raiz do git, ou a pasta atual.

```markdown
---
type: stories
status: active
role: student
---

# Student user stories

O que o papel é e o que ele pode fazer.

## Joining the platform

### Log in

    status: implemented
    url: /login
    relatedTo: [login-bug]

Narrativa: o que o usuário quer, o que faz e com o que termina.
```

3. O frontmatter traz `type: stories`, `status` (padrão `active`) e `role`. As outras chaves são mantidas.
4. O título de nível 1 é o título do arquivo; sem ele, `<Papel> user stories`. A introdução vai até o primeiro título de nível 2 ou 3.
5. Um título de nível 2 abre uma seção, que pode ter uma introdução. Um título de nível 3 abre uma story. Títulos dentro de blocos de código cercados não contam; títulos de nível 4 em diante fazem parte da narrativa.
6. Logo depois do título da story pode vir o bloco de metadados: linhas seguidas, indentadas com 4 espaços ou um tab, que formam um mapa YAML. As chaves são todas opcionais:

   | Chave | Valor |
   | --- | --- |
   | `status` | `todo` (padrão), `partial`, `implemented`, `deprecated` |
   | `url` | a página onde a story acontece, quando há uma só |
   | `relatedTo` | issues e ADRs |

   Chaves desconhecidas são mantidas e escritas depois das conhecidas.
7. Um `status` desconhecido, como o `web` e o `cli` do codehood, é mantido como está e conta como `partial`.
8. O resto da story, até o próximo título de nível 2 ou 3, é a narrativa.

## Identificador

9. O ID de uma story é `<papel>: <slug do título>`, como `student: log-in`. O papel vem do `role` do frontmatter ou, sem ele, do nome do arquivo sem `.md`.
10. O slug tem as palavras do título em minúsculas, só letras ASCII e dígitos, unidas por hífen. Acentos são removidos antes: `Configuração do curso` vira `configuracao-do-curso`.
11. Onde a CLI recebe um ID, ela aceita também o título: `student: Log in`, `student: log in` e `student:log-in` são a mesma story.

## Leitura tolerante e escrita estrita

12. A leitura aceita qualquer Markdown: sem frontmatter, sem título de nível 1, com stories antes da primeira seção. Um bloco indentado que não é um mapa YAML faz parte da narrativa.
13. A escrita produz o formato acima: frontmatter com `type`, `status`, `role` e as outras chaves; o título; a introdução; as seções e stories na ordem do arquivo, separadas por uma linha em branco. O bloco de metadados sempre traz `status` e segue a ordem `status`, `url`, `relatedTo`; valores vazios ficam de fora.
14. Os comandos de escrita recusam, com código de saída 1, um arquivo sem `type: stories` no frontmatter, e apontam para `r2 story fmt`. `fmt` é o único comando que converte um arquivo.

## Testes e2e

15. Os testes e2e ficam nas pastas ou arquivos configurados. A ordem de escolha:
    1. a opção `--tests` de `r2 story check`, repetível;
    2. `tests` em `[config.stories]` no manifesto do projeto (`r2.toml` ou `[tool.r2]` do `pyproject.toml`), uma string ou uma lista;
    3. a primeira pasta que existe entre `test/stories` e `tests/stories`.

    A pasta de stories segue a mesma ordem: `--dir`, `dir` em `[config.stories]` e `docs/user-stories`. Os caminhos do manifesto são relativos à pasta dele.

    ```toml
    [config.stories]
    dir = "docs/user-stories"
    tests = ["test/stories"]
    ```
16. Numa pasta, os arquivos de teste são `*.test.*` e `*.spec.*` de JavaScript e TypeScript, e `test_*.py` e `*_test.py`. Pastas ocultas, `node_modules`, `__pycache__` e `venv` ficam de fora.
17. O r2 lê os arquivos e não roda nenhum runner. Assim, `r2 story check` funciona sem `node_modules` nem ambiente Python instalados.
18. vitest e playwright: cada chamada `test(...)` ou `it(...)`, também com `.only`, `.skip`, `.fixme`, `.fail` ou `.concurrent`, com o título numa string literal, é um teste. Um título da forma `<papel>: <título>` cita essa story, como em `test("student: log in", ...)`. Qualquer outro título não cita nenhuma. `test.describe`, `test.step` e os hooks não são testes.
19. pytest: cada função `test*`, no módulo ou numa classe `Test*`, é um teste. Ele cita uma story com `@pytest.mark.story("student: log in")` (ou `@mark.story`), na função ou na classe. Um teste com vários markers cita várias stories. Um projeto com `--strict-markers` registra o marker `story` na própria configuração do pytest.
20. Todo teste encontrado nas pastas e2e é um teste e2e e precisa citar uma story.

## Verificações

21. `r2 story check` informa os erros abaixo, um por linha, e sai com código 1 quando há algum:
    - uma story `implemented` ou `partial` (inclusive um status desconhecido) sem teste: `student: log-in: has no test (status: implemented)`;
    - um teste que cita uma story que não existe: `test/stories/a.test.ts:12: 'student: sign up' cites no existing story`;
    - um teste que não cita nenhuma story: `tests/stories/test_a.py:8: 'tests/stories/test_a.py::test_other' cites no story`;
    - dois títulos com o mesmo slug no mesmo arquivo: `docs/user-stories/student.md: 'Log-in' and 'Log in' share the id student: log-in`;
    - dois arquivos com o mesmo papel; o segundo, em ordem alfabética, é ignorado;
    - com `--no-duplicates`, uma story com mais de um teste: `student: log-in: has 2 tests: a.test.ts:1, a.test.ts:9`.
22. Um teste de uma story `todo` ou `deprecated` gera um aviso em stderr, não um erro. Sem nenhuma pasta de testes e2e, o `check` avisa e segue, e toda story que precisa de teste vira erro.
23. Depois dos erros, a não ser que a verbosidade seja -2, o `check` imprime a cobertura, uma linha por papel: `student: 20 of 21 stories have a test (20 implemented or partial)`. O r2 não grava um relatório de cobertura em arquivo.
24. Os modos só de leitura listam e saem com 0:
    - `--missing`: as stories que nenhum teste cita, como `id  status  title`;
    - `--covered`: as stories que algum teste cita, no mesmo formato;
    - `--stale`: os testes que não citam nenhuma story ou citam uma que não existe, como `arquivo:linha  título`.

    Só um modo por vez; dois são erro de uso (código 2).

## Aceitação

Rodado numa cópia de `tests/examples/stories/codehood/`:

25. `r2 story check` sai com 1 e informa as três stories `cli` sem teste: `create-the-first-admin`, `reset-a-password-for-someone-locked-out` e `import-a-term-s-calendar-for-an-instructor`, seguidas de `admin: 9 of 16 stories have a test (12 implemented or partial)`, o mesmo número do `coverage.md` do codehood.
26. `--stale` não imprime nada. Depois de `r2 story fmt` e de mudar o título de uma story com teste, `--stale` lista o teste, e `check` informa os dois lados.
27. `r2 story fmt` mantém as stories, as seções e os metadados: `r2 story list` imprime o mesmo antes e depois. Rodar `fmt` duas vezes dá o mesmo arquivo.

## Código

28. `r2.core.stories` é um pacote:

    | Módulo | Contém |
    | --- | --- |
    | `doc.py` | `StoryFile`, `Section`, `Story`, `parse`, `slugify`, `parse_id` |
    | `tests.py` | `StoryTest`, `find_tests`, a leitura dos arquivos de teste |
    | `check.py` | `Layout`, `layout`, `load`, `check`, `Report` |

## Fora desta especificação

- Uma visão de stories na TUI.
- A ligação com testes do nextest.
- Um relatório de cobertura em arquivo, como o `coverage.md` do codehood.
- Escolher os testes e2e por runner (todos os testes do playwright), em vez de por pasta.
