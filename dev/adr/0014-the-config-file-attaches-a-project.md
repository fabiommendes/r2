---
type: adr
status: accepted
created: 2026-09-30
decided: 2026-09-30
---

# `.reportlab/config.toml` é o que vincula um projeto

> Importado do reportlab, onde era a ADR 0012.

Status: aceito, 2026-09-30

Alterado em 2026-09-30: a exceção descrita abaixo, que deixava `config.toml` passar pelo
`.reportlab/.gitignore`, foi removida. Ela deixava `.reportlab/` sem rastreamento no
`git status` de todo usuário que não commitava o arquivo, o que é ruído em um fluxo de trabalho
que a ferramenta não tem motivo para tocar. Compartilhar a configuração é um `git add -f` único:
o git continua rastreando um arquivo que já rastreia, então o efeito em um clone é o mesmo.

Restringe `0004-single-multi-project-daemon.md`, que colocou a lista de projetos em um registro
da máquina sem dizer a que o registro responde.

## Contexto

O registro em `~/.config/reportlab/projects.json` era o único registro de que um projeto existia.
Dois problemas vieram disso.

Nada jamais saía dele. Um diretório que foi movido era ignorado em memória e continuava no
arquivo; um projeto que o usuário não queria mais não tinha como sair.

E ele não sobrevivia à descoberta. Quando o daemon varre raízes configuradas em busca de projetos
que não registrou por conta própria, um projeto precisa de uma marca dentro do repositório dizendo
se ele é desejado. Caso contrário, uma remoção do registro é desfeita pela varredura seguinte, e o
único jeito de a remoção valer é apagar os arquivos do usuário.

Já existia uma marca candidata: os agentes criam `.reportlab/reports/` por conta própria, porque
escrever um relatório é uma escrita de arquivo e nada mais. Então a presença de `.reportlab/`
prova apenas que um agente passou por ali, e não que um humano quer o projeto observado.

## Decisão

`.reportlab/config.toml` vincula um projeto. O daemon observa um projeto quando esse arquivo existe,
e não observa quando ele não existe.

- `rl init` o cria, com todas as configurações comentadas. A presença é o ponto.
- `rl detach` o apaga e deixa o diretório, os relatórios e o índice intactos. `rl detach --purge`
  remove `.reportlab/` por completo, e informa quantos relatórios foram junto.
- O registro passa a ser um cache de onde estão os projetos vinculados, que é a regra que o registro
  0001 já estabelece para tudo o que é derivado: uma entrada cujo diretório sumiu, ou cuja config
  sumiu, é descartada quando o daemon inicia.
- Uma config que não pode ser parseada continua vinculando o projeto. Um erro de digitação não é
  motivo para parar de observar, e `rl status` diz o que há de errado nela.
- O arquivo de ignore dentro de `.reportlab/` deixa `config.toml` de fora, para que um time possa
  commitá-lo e um clone fique vinculado sem que ninguém precise rodar nada.

## Alternativas rejeitadas

**Uma lista de negação na configuração da máquina.** `rl detach` grava o caminho em uma lista que
a descoberta consulta. Funciona, mas coloca o fato de que um projeto não é desejado em outro lugar
que não o próprio projeto, então fica invisível no repositório e se perde quando a máquina muda.

**`rl detach` apagar `.reportlab/`.** Também faz a remoção valer, ao apagar relatórios que o usuário
não pediu para perder. Relatórios são descartáveis por projeto, o que é um argumento para não temer
a exclusão, e não um argumento para fazê-la sem perguntar. Para isso existe `--purge`.

**O próprio `.reportlab/` como marca.** Nenhum arquivo novo, e a marca é criada por qualquer agente
que escreva um relatório, que é exatamente o caso que a descoberta existe para pegar e exatamente o
caso que um humano ainda não aprovou.

**Um arquivo marcador vazio, `.reportlab/.enabled`.** Honesto por ser um flag, mas aí o arquivo de
configurações precisa morar em outro lugar, e são dois arquivos onde um basta.

## Consequências

- Apagar um arquivo desativa um projeto, o que é uma boa propriedade para algo que um humano faz à mão
  em um repositório que está arrumando.
- Um projeto configurado antes deste registro não tem config e será removido do registro no próximo
  início do daemon. `rl init` o vincula de novo. Nada é liberado, então nenhuma migração é escrita.
- `rl` em um projeto desvinculado recusa a execução e aponta para `rl init`, em vez de religar algo
  que um humano desligou.
