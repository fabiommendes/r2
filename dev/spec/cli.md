---
type: spec
status: active
tags: [cli, agent-mode, glossary, issues, adrs]
relatedTo: [glossary, issues, adrs]
---

# Linha de comando

O comando `r2` atende dois tipos de usuário: pessoas num terminal e agentes de código que rodam comandos de shell. Os dois usam os mesmos comandos. Um modo global muda como o r2 responde, nunca o que um comando faz.

## Modos

1. O modo humano é o padrão. O modo agente fica ligado com `--agent` ou quando o ambiente define `R2_AGENT` como `1`, `true`, `yes` ou `on`.
2. No modo agente, o r2 nunca pergunta. Um comando que pediria confirmação falha com código de saída 1 e informa qual argumento passar.
3. O modo agente muda o nível padrão de verbosidade (veja Verbosidade) e imprime texto puro: sem cores ou estilos, com a ajuda e os erros de uso do Click em vez das caixas do Rich, e com tracebacks padrão. Isso vale para todos os comandos, plugins incluídos, sem código nos comandos. O formato de saída é escolhido à parte, com `--json`.
3a. No modo agente, o r2 define `NO_COLOR=1` no ambiente, a não ser que ele já esteja definido. Assim, os programas que o r2 roda e os consoles que os plugins criam por conta própria também imprimem texto puro.
3b. Plugins imprimem por `plugin.console` e `plugin.err`, que sempre devolvem os consoles atuais do r2, e leem `plugin.mode`.

## Opções globais

4. As opções globais pertencem ao comando raiz `r2`:

   | Opção | Significado |
   | --- | --- |
   | `--agent` | modo agente |
   | `-v`, `--verbose` | aumenta a verbosidade em um, repetível |
   | `-q`, `--quiet` | diminui a verbosidade em um, repetível |
   | `-y`, `--yes` | aprova previamente os comandos destrutivos |
   | `--json` | saída em JSON para comandos que leem dados |
   | `-C <dir>` | roda como se o r2 tivesse começado em dir, como `git -C` |

5. As opções globais são aceitas em qualquer lugar antes de `--`: `r2 -q glossary list` e `r2 glossary list -q` são a mesma coisa. As exceções:
   - um comando de projeto ou de plugin repassa seus argumentos a outro programa, então só as opções antes do nome do comando são globais (`r2 -q test -v` roda os testes com pouca saída e passa `-v` ao runner de testes);
   - `-C` só é lido antes do nome do comando, como no git.
6. As opções que só fazem sentido para um grupo de comandos ficam nesse grupo, como o `-f/--file` de `r2 glossary`.

## Verbosidade

7. A verbosidade é um número: o padrão do modo (0 para humanos, -1 para agentes) mais a quantidade de `-v` menos a quantidade de `-q`. Assim, `-qv` dá o padrão do modo, e `-vv` fica dois níveis acima dele.
8. Níveis:

   | Nível | Nome | Saída |
   | -2 | silencioso | só erros |
   | -1 | resumo | uma linha por resultado; um programa que falha mostra as últimas linhas |
   | 0 | normal | a saída completa |
   | 1 | detalhado | também os programas que o r2 roda, e onde |
   | 2 | depuração | também os logs de depuração |

9. Cada comando limita a verbosidade aos níveis que ele suporta. Os plugins a leem em `r2.core.mode.mode.verbosity`.
10. Um comando de projeto declarado com `output = "summary"` roda com a saída capturada abaixo do nível 0: em caso de sucesso, imprime `ok: <name>`; em caso de falha, imprime `failed: <name> (exit N)` e, no nível -1, as últimas 30 linhas da saída.

## Saída e erros

11. Os resultados vão para stdout, um registro por linha, sem quebra de linha.
12. Erros e avisos vão para stderr, como `error: <message>` e `warning: <message>`.
13. Códigos de saída: 0 em caso de sucesso; 1 quando o comando falha por um motivo do domínio (termo não encontrado, termo duplicado, problemas encontrados por uma verificação); 2 para erros de uso (opção desconhecida, argumento faltando).
13a. Um grupo de comandos chamado sem subcomando (`r2 coverage`, ou `r2` só com opções globais) imprime a ajuda em stdout em vez de um erro, e ainda sai com código 2. `r2` sem nenhum argumento abre a TUI.
14. Com `--json`, um comando que lê dados imprime um documento JSON em stdout. Comandos que só escrevem ignoram `--json`.

## Arquivos

15. Todo arquivo que o r2 escreve é substituído de forma atômica: o texto novo vai para um arquivo temporário na mesma pasta, que então substitui o alvo. Quem lê vê o arquivo antigo ou o novo, nunca um arquivo pela metade. O arquivo mantém as permissões, e um link simbólico continua apontando para o mesmo arquivo.
16. Uma alteração que lê um arquivo, edita e grava de volta segura um lock exclusivo na pasta do arquivo durante todo o ciclo, para que dois processos do r2 nunca sobrescrevam as mudanças um do outro. A TUI aplica suas mudanças ao arquivo como está no disco ao salvar, e não à cópia que ela mostra.
17. Criar um arquivo (uma nova issue ou ADR) segura o mesmo lock enquanto escolhe o nome do arquivo, e nunca sobrescreve um arquivo existente.
18. Os locks são locks `flock` consultivos sobre a própria pasta; o r2 não deixa arquivos de lock. Windows não é suportado.

## Glossário

O formato está em [glossary.md](glossary.md).

19. Todo comando de glossário aceita `-f/--file`. O padrão é `GLOSSARY.md` na raiz do projeto: a pasta mais próxima, a partir da atual e subindo, que tem `.git`, ou a pasta atual se nenhuma tiver.
20. Os comandos de leitura aceitam qualquer arquivo Markdown. Os comandos de escrita recusam, com código de saída 1, um arquivo cujo frontmatter não tem `type: glossary`, e apontam para `r2 glossary fmt`. `fmt` é o único comando que converte um arquivo para o formato estrito.

### Leitura

21. `r2 glossary list [--tag TAG]` imprime cada termo como `Nome: resumo`, onde o resumo é a primeira frase da definição. `--tag` mantém os termos com aquela tag, sem diferenciar maiúsculas de minúsculas.
22. `r2 glossary show TERM` imprime a seção do termo como ela está escrita no arquivo. Um termo desconhecido é um erro.
23. `r2 glossary find WORDS` imprime os termos que batem com WORDS, do mesmo jeito que o filtro da TUI: cada palavra precisa começar uma palavra do nome, da definição ou de um campo. Quando uma palavra bate com uma entrada `avoid`, a linha fica `<avoided> -> Nome`, indicando qual termo usar no lugar. Não encontrar nada não é erro.
24. `r2 glossary check` informa, uma por linha, sem alterar o arquivo: as verificações em [glossary.md](glossary.md#verificações), mais um arquivo sem `type: glossary` no frontmatter. Ele sai com código 1 quando informa algo.
25. Com `--json`:
    - `list` e `find` imprimem uma lista de termos;
    - `show` imprime um termo;
    - `check` imprime uma lista de `{"term": ..., "problem": ...}`, em que `term` é null para problemas do arquivo inteiro.

    Um termo é `{"name": ..., "definition": ..., "fields": {...}}`, com os campos como estão escritos. `find` acrescenta `"avoided": [...]`, com as palavras evitadas que bateram.

### Escrita

26. `r2 glossary add "Name: definition"` adiciona um termo. Sem definição, o modo humano pede a definição.
27. `add` recebe os campos como opções:
    - `--tag`, `--avoid`, `--related`, `--code`: repetíveis, e cada valor pode trazer várias entradas separadas por vírgula;
    - `--field key=value`: qualquer outro campo, como um idioma (`--field pt=termo`); repetível.
28. `r2 glossary set TERM` altera um termo existente. Ele recebe as opções de `add`, mais `--definition TEXT` e `--unset KEY` (repetível). Uma opção de campo substitui o campo inteiro; `--unset` remove o campo.
29. `r2 glossary remove TERM` remove um termo.
30. `r2 glossary fmt` reescreve o arquivo no formato estrito, com os termos ordenados.
31. Nomes de termos batem sem diferenciar maiúsculas de minúsculas. Adicionar um termo que já existe, ou alterar ou remover um que não existe, é um erro que deixa o arquivo como estava.
32. Cada escrita imprime uma linha dizendo o que mudou, a não ser que a verbosidade seja -2.

## Issues e ADRs

Os formatos estão em [issues.md](issues.md) e [adrs.md](adrs.md). `r2 issue` trabalha em `dev/issues` e `r2 adr` em `dev/adr`, ambos na raiz do projeto, com os mesmos comandos.

33. Uma thread é identificada pelo seu id: o nome do arquivo sem `.md`, um prefixo único dele ou, para arquivos numerados, o número (`r2 adr show 3`). Nenhum resultado, ou vários, é um erro que lista os candidatos.
34. Argumentos que recebem texto em Markdown leem da entrada padrão quando recebem `-`.
35. O autor de uma thread ou comentário é `--by NAME`; sem ele, a variável `R2_AUTHOR`; sem ela, o `user.name` do git. A TUI usa o mesmo padrão.
36. Comandos:

    | Comando | Faz |
    | --- | --- |
    | `new TITLE [--body TEXT] [--tag T] [--by NAME]` | cria uma thread e imprime o caminho dela |
    | `new TITLE ... [--kind K] [--priority P] [--milestone M] [--relatedTo R]` | só issues: também preenche essas chaves |
    | `list [--status S] [--tag T] [--all]` | `id  status  title`, threads abertas por padrão |
    | `show ID` | imprime o arquivo |
    | `comment ID TEXT [--by NAME]` | adiciona um comentário no fim |
    | `status ID STATUS` | move para um status |
    | `advance ID` | move para o próximo status do fluxo |
    | `supersede NEW OLD` | só ADRs: NEW substitui OLD |

37. `new` escolhe o nome do arquivo sob o lock da pasta (requisito 17): issues recebem um slug livre, e ADRs, o próximo número.
37a. `r2 issue new` aceita as chaves que o formulário da TUI preenche: `--kind` e `--priority` só aceitam os valores de [issues.md](issues.md#frontmatter), e um valor desconhecido é erro de uso (código 2); `--relatedTo`, como `--tag`, é repetível e aceita entradas separadas por vírgula. Valores padrão ficam fora do frontmatter.
37b. Com `--kind` e sem `--body`, o corpo da issue é o modelo do `kind` ([issues.md](issues.md#modelos-de-corpo)), o mesmo que a TUI usa. Sem `--kind`, o corpo fica vazio.
37c. `advance` segue o fluxo de [issues.md](issues.md#status): uma issue `in_progress` vai para `in_review`, e só depois para `completed`.
38. Com `--json`, `list` imprime uma lista de `{"id", "path", "title", "status", "meta"}`, e `show` acrescenta `"description"` e `"comments"` (`{"by", "text"}`).
