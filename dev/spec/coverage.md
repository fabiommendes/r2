---
type: spec
status: draft
tags: [coverage, tests, redundancy, python, rust, typescript]
relatedTo: [cli]
---

# Cobertura por teste

`r2 coverage` registra qual código cada teste executa e responde perguntas sobre a suíte de testes a partir desse registro: quais testes não acrescentam nada em relação a uma baseline, qual código só um teste alcança, e o menor conjunto de testes que mantém a cobertura. O uso principal é podar os muitos testes superficiais que agentes de código costumam escrever.

Os exemplos em `tests/examples/roman/` são as fixtures de aceitação: o catálogo no README deles é a saída esperada das análises.

## Conceitos

1. Um **runner** é uma ferramenta de teste que o r2 sabe instrumentar. Um projeto pode ter vários (vitest e playwright no mesmo `package.json`).

   | Runner | Linguagem | Mecanismo | Tipo de span |
   | ------------ | -------- | ------------------------------------------ | --------- |
   | `pytest` | Python | contextos dinâmicos do coverage.py, uma execução | arc |
   | `nextest` | Rust | um `.profraw` por teste, `llvm-cov export` | region |
   | `vitest` | TS | cobertura V8 coletada por teste num arquivo de setup | block |
   | `playwright` | TS | cobertura V8 da página por teste, num fixture | block |

2. Um **span** é o menor pedaço de código que o runner distingue. Todo span pertence a um arquivo de código e a um intervalo de linhas, então qualquer span pode ser reduzido às linhas que ele cobre.
3. Um **id de teste** é o id do próprio runner: o node id do pytest (`tests/test_examples.py::test_from_roman_iv`), o id do nextest (`roman::examples to_roman_rejects_zero`) e `arquivo > título` para vitest e playwright. Casos parametrizados são testes separados.
4. Os **spans ambientes** são os spans que rodam fora de qualquer teste: imports, código de nível de módulo, fixtures de sessão. Toda análise os trata como cobertos por todos os testes, então importar um módulo nunca conta como cobertura que um teste acrescenta.
5. Um **seletor** escolhe testes pelo id. É um glob (`*properties*`) comparado com o id completo; `runner:glob` restringe a um runner (`vitest:*properties*`). Vários seletores se combinam com "ou".
6. A **baseline** é o conjunto de testes escolhido pelos seletores de `--baseline`. Só as análises que comparam com algo precisam dela.
7. Um teste **acrescenta** um span quando cobre o span e nem a baseline nem os spans ambientes cobrem.

## Mapa de cobertura

8. `r2 coverage collect` escreve um mapa de cobertura por runner em `.r2/coverage/<runner>.json`, na raiz do projeto, que é a pasta do projeto detectado. A primeira escrita também cria `.r2/.gitignore` com `*`.
9. Um mapa guarda:
   - `runner`, `span_kind` (`arc`, `region`, `block` ou `line`) e a `version` do formato do r2;
   - `created`, o commit do git e se havia alterações não commitadas;
   - `files`: cada arquivo de código medido, com o hash do conteúdo;
   - `ambient`: os spans ambientes;
   - `tests`: para cada id de teste, seu resultado (`passed`, `failed`, `skipped`) e seus spans.

   Os spans são escritos como `path:line:col-line:col`, com caminhos relativos à raiz do projeto.
10. Um mapa fica **desatualizado** quando um arquivo medido mudou desde que foi escrito. As análises ainda rodam com um mapa desatualizado, mas mostram um aviso com os arquivos alterados.
11. Um teste que falha ainda é registrado, com resultado `failed`. As análises o incluem e o marcam na saída. Um teste pulado não tem spans.

## Comandos

Todos os comandos aceitam `-C` e as opções globais de [cli.md](cli.md).

### collect

12. `r2 coverage collect [--runner NAME]... [SELECTOR]...` roda os testes sob instrumentação e escreve os mapas. Sem `--runner`, roda todo runner detectado; sem seletores, roda todos os testes.
13. A detecção lê os arquivos do projeto que o `r2.core.project` já interpreta:
    - `pytest` nas dependências de um projeto uv;
    - um `Cargo.toml` (o nextest é uma ferramenta, não uma dependência);
    - `vitest` ou `@playwright/test` nas dependências do `package.json`.
14. Antes de rodar, o `collect` verifica as ferramentas externas que cada runner precisa. Se alguma faltar, ele falha com código 1 e lista cada uma com seu comando de instalação. Ele nunca instala nada.

    | Runner | Precisa de |
    | ------------ | ------------------------------------------------------------------------------------------ |
    | `pytest` | `uv`; `pytest-cov` ou `coverage` no projeto, senão roda com `uv run --with coverage` |
    | `nextest` | `cargo`, `cargo-nextest`, `llvm-tools-preview` (`llvm-profdata`, `llvm-cov`) |
    | `vitest` | `npx`, `vitest` em `node_modules` |
    | `playwright` | `npx`, `@playwright/test` em `node_modules`, um navegador Chromium |

15. O `collect` nunca altera os arquivos do projeto. A instrumentação passa por variáveis de ambiente, flags de linha de comando e arquivos em `.r2/coverage/`, como o arquivo de setup do vitest que o r2 passa com `--setupFiles`.
16. Uma falha de teste não faz o `collect` falhar: ele sai com 0 quando escreveu o mapa e imprime uma linha por runner, como `pytest: 12 tests, 1 failed`. Ele sai com 1 quando um runner não conseguiu rodar de jeito nenhum (erro de build, nenhum teste coletado), e mostra as últimas 30 linhas de saída do runner.

    Enquanto um runner trabalha, o `collect` mostra o progresso em stderr: `pytest: running 12 tests`, uma linha `FAILED <id>` por teste que falhou e, em um terminal, uma barra de progresso provisória e um spinner enquanto lê os dados de cobertura. O modo agente e `--json` imprimem só a linha de resumo.

    O `pytest` roda com `-n auto` quando o projeto depende de `pytest-xdist`. Sem ele, o `collect` avisa e imprime o comando que o adiciona. O modo agente e `--json` pulam o aviso.

    Cada runner segura `.r2/coverage/<runner>.lock` enquanto coleta. Um segundo `collect` do mesmo runner no mesmo projeto falha na hora, com código 1, em vez de sobrescrever os arquivos temporários do primeiro.
17. Coletar com seletores substitui os testes registrados que casam com eles e mantém os outros, então um teste pode ser atualizado sem rodar a suíte inteira. Os spans ambientes são substituídos a cada execução.

### Análises

18. As análises leem os mapas e não rodam testes. Elas leem todos os mapas, a não ser que `--runner` seja dado. Um mapa ausente é um erro que aponta para `r2 coverage collect`.
19. Os spans são comparados arquivo por arquivo. Quando dois mapas medem o mesmo arquivo com spans diferentes, esse arquivo é comparado por linhas. Isso só acontece entre runners da mesma linguagem, já que cada linguagem tem seus próprios arquivos de código. `--span line` compara todos os arquivos por linhas.

20. `r2 coverage redundant --baseline SELECTOR... [SELECTOR]...` lista os testes fora da baseline que não acrescentam span. Com seletores, só esses testes são verificados. Cada linha é o id do teste. Com `--json`: uma lista de `{"test", "runner", "outcome", "spans"}`, em que `spans` é a quantidade de spans que o teste cobre.
21. `r2 coverage adds --baseline SELECTOR... [SELECTOR]...` é o oposto: cada teste fora da baseline que acrescenta spans, com a quantidade, ordenado pela quantidade, do maior para o menor. `-v` também lista os spans, agrupados por arquivo como intervalos de linhas.
22. `r2 coverage unique [SELECTOR]...` lista, para cada teste, os spans que nenhum outro teste cobre, como `test: N spans`. Testes sem nenhum desses spans ficam de fora. `-v` lista os spans.
23. `r2 coverage fragile [PATH]...` lista os spans cobertos por exatamente um teste, agrupados por arquivo, com o teste. Com caminhos, só esses arquivos.
24. `r2 coverage minimize [--baseline SELECTOR]... [SELECTOR]...` imprime um conjunto pequeno de testes que cobre todo span que a suíte inteira cobre. Ele é encontrado pela cobertura gulosa de conjuntos: primeiro a baseline e, a cada passo, o teste que acrescenta mais spans. Empates vão para o teste com menos spans e, depois, para o id. A última linha diz `kept 8 of 12 tests`. Com `--json`: `{"kept": [...], "dropped": [...]}`.
25. `r2 coverage show TEST` imprime os spans de um teste, agrupados por arquivo como intervalos de linhas, marcando os que o teste acrescenta quando `--baseline` é dado.

### Mais tarde

Não faz parte desta especificação, mas o mapa foi projetado para isso:

- `overlap`: uma matriz de spans compartilhados entre arquivos de teste.
- `impact DIFF`: os testes que cobrem as linhas que um diff toca.

## Código

26. `r2.core.coverage` é um pacote:

    | Módulo | Contém |
    | ------------- | ------------------------------------------------- |
    | `base.py` | `CoverageMap`, `Span`, `TestId`, `CoverageRunner` |
    | `analysis.py` | as análises como funções puras sobre mapas |
    | `py.py` | `PytestCoverage` |
    | `rs.py` | `NextestCoverage` |
    | `ts.py` | `VitestCoverage`, `PlaywrightCoverage` |

27. `CoverageRunner` é uma classe abstrata. Um runner guarda o projeto em que trabalha (`UvProject`, `CargoProject`, `NpmProject`) e implementa:

    ```python
    class CoverageRunner(ABC):
        name: ClassVar[str]
        span: ClassVar[SpanKind]
        project: Project

        @classmethod
        def detect(cls, project: Project) -> bool: ...
        def missing_tools(self) -> list[MissingTool]: ...  # name + install hint
        def collect(self, selectors: list[str]) -> CoverageMap: ...
    ```

28. As análises não importam nada dos runners e não rodam programas. Por isso, são testadas com mapas montados à mão, sem nenhuma ferramenta instalada.
29. Os runners chamam programas pelo `r2.core.cli_tool.CliTool`, que precisa de:
    - uma chamada que devolve o código de saída, stdout e stderr sem lançar exceção, já que um runner sai com código diferente de zero quando um teste falha;
    - `_env` mesclado sobre o ambiente atual, em vez de substituí-lo;
    - `available()` e uma dica de instalação, para `missing_tools`.
30. O `r2.core.project` ganha `CargoProject` e `NpmProject`, só com o que a cobertura precisa: detecção, raiz e dependências. Os outros métodos de `Project` nesses tipos lançam `NotImplementedError`. `find_projects(path)` devolve todos os projetos de um caminho, já que uma pasta pode ter um `pyproject.toml` e um `package.json`.

## Aceitação

Rodado contra cópias de `tests/examples/roman/`:

31. Para cada um de `python/`, `rust/` e `ts/`, o `collect` escreve um mapa com todos os testes do catálogo, incluindo os 2 testes de propriedade.
32. `redundant --baseline '*properties*'` imprime exatamente os testes que o catálogo marca como "redundant" para aquela linguagem; `adds` imprime os outros. Em `ts/`, os testes do playwright são redundantes em `src/roman.ts`, mas acrescentam spans em `src/main.ts`, então aparecem em `adds`.
33. `minimize --baseline '*properties*'` mantém a baseline e descarta todo teste que `redundant` lista, mais um entre `to_roman_rejects_zero` e `to_roman_rejects_4000`.
34. Rodar `collect` duas vezes num projeto sem mudanças dá os mesmos testes e spans.
35. Com uma ferramenta faltando (por exemplo, `cargo-nextest` fora do `PATH`), o `collect` sai com código 1 e informa o nome da ferramenta e o comando de instalação.

## Pontos em aberto

- Onde a baseline fica, além da linha de comando: uma entrada `[coverage] baseline` na configuração por projeto do r2 pouparia digitar `--baseline` em toda chamada.
- Os mecanismos do vitest e do playwright são os menos comprovados. Um spike confirma os dois antes de os runners de TS serem implementados.
