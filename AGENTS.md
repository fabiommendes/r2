# r2

Sidekick TUI para sessões do Claude Code no herdr. Leia o `README.md` para o comportamento e `dev/spec/` para os formatos de arquivo.

## Idioma

Nível 2 (aplicativo público), conforme `~/git/tools/tooling-root/dev/adr/0002-idioma-dos-repositorios.md`:

- Em inglês: código, comentários, docstrings, mensagens da CLI e de erro,
  `README.md`, a documentação de usuário em `docs/`, `CHANGELOG.md`,
  `CONTRIBUTING.md`, `ROADMAP.md`, `GLOSSARY.md` e mensagens de commit.
- Em português (pt-BR): este arquivo, `BACKLOG.md`, tudo em `dev/`, as ADRs e
  as issues.

## Visualizador de relatórios (`r2 web`)

Veio do reportlab (ADR 0002). O pacote `r2/core/reports/` tem o formato e a leitura dos relatórios; `r2/web/` tem o daemon FastAPI (extra `web`); `web/` tem o front SolidJS. `docs/reports.md` é a especificação de `.reportlab/`, um contrato publicado: agentes em outros repositórios escrevem nele e não podem ser atualizados junto.

Regras fáceis de quebrar:

- Os modelos pydantic em `r2/core/reports/model.py` e `r2/web/wire.py` são a única fonte dos tipos. O front usa `web/src/api.gen.ts`, gerado do OpenAPI (`pnpm run gen` em `web/`); nunca escreva tipos da API à mão. Campo opcional fica ausente no JSON, nunca `null`.
- O front não detecta referências nem faz parsing de Markdown: o servidor manda o AST (`rendered`), os links das linhas (`links`) e as `resolutions`. Duplicar essa lógica em TypeScript é o que a fusão eliminou.
- `r2/core/reports/render.py` e `candidates.py` não fazem E/S. Uma referência detectada é candidata até o servidor conferir no disco (`resolve_references`); a UI nunca mostra candidata não resolvida como link.
- `html: False` no markdown-it é fronteira de segurança: um relatório é entrada não confiável.
- Todo caminho vindo de requisição HTTP ou de referência passa por `normalize_repo_path` (forma) e `scan.confine` (symlink que escapa). Há uma implementação de cada.
- O daemon escuta só em `127.0.0.1`. A API exige o token; `OriginGuard` confere `Host` e `Origin` em todas as rotas.
- `.reportlab/config.toml` é o que vincula um projeto (ADR 0014). O registro (`$XDG_STATE_HOME/r2/web/projects.json`) sempre faz poda ao carregar.
- O watcher (`r2/web/watch.py`) é todo o caminho de ingestão: tolera arquivo pela metade, arquivo apagado entre o evento e a leitura, e rajadas. Um evento repetido é inofensivo; um evento faltando não.
- Um relatório incompleto renderiza até onde foi; cerca não fechada é bloco aberto, nunca erro.
- O r2 web não executa git: referências resolvem contra a árvore de trabalho (ADR 0011).
