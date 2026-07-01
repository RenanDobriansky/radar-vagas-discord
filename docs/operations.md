# Operacoes do Estado do Radar

## Objetivo

Este documento registra a decisao operacional para persistir `data/seen_jobs.json` sem misturar commits de estado com commits de codigo.

## Schema do historico

- versao atual: `3`
- arquivo operacional: `data/seen_jobs.json`
- branch dedicada para estado: `radar-state`

O schema atual reduz redundancia e dados desnecessarios:

- mantem `provider_job_id`, `normalized_url_hash` e `fingerprint` para deduplicacao;
- mantem `status`, `attempts`, `last_error_code`, `last_error_message`, `next_retry_at`, `first_seen_at`, `last_seen_at` e `notified_at` para auditoria e retries;
- mantem apenas um `job_snapshot` minimo para reprocessamento;
- nao persiste descricao completa da vaga;
- nao persiste salario;
- nao persiste URL normalizada em texto;
- mantem a URL original apenas dentro do snapshot minimo porque ela ainda e necessaria para a notificacao de vagas pendentes ou em retry.

## Opcoes avaliadas

### 1. Commitar estado no `main`

Vantagens:

- implementacao simples;
- nenhuma estrutura extra no workflow.

Desvantagens:

- mistura alteracoes operacionais com historico de codigo;
- gera ruido em revisoes e diffs;
- aumenta chance de conflito com desenvolvimento normal.

### 2. Cache ou artifact do GitHub Actions

Vantagens:

- evita commits operacionais no repositorio.

Desvantagens:

- nao e fonte de verdade adequada para estado cumulativo;
- cache pode expirar ou ser sobrescrito;
- artifacts nao sao praticos como armazenamento persistente do historico.

### 3. Branch dedicada `radar-state`

Vantagens:

- separa estado operacional do codigo;
- continua simples e compativel com GitHub Actions;
- permite auditoria do historico quando necessario;
- evita disparo de CI no fluxo principal quando o estado muda.

Desvantagens:

- exige passo extra de fetch, merge e push no workflow.

## Decisao adotada

Foi adotada a branch dedicada `radar-state`.

Motivos:

- e a alternativa mais simples que separa estado de codigo sem introduzir infraestrutura externa;
- continua facil de operar com GitHub Actions;
- reduz ruido no `main`;
- permite merge deterministico do estado quando houver divergencia entre a execucao atual e a branch remota.

## Estrategia de concorrencia e merge

O workflow produtivo segue este fluxo:

1. faz checkout do codigo da branch normal;
2. restaura `data/seen_jobs.json` a partir de `origin/radar-state`, se a branch existir;
3. executa o radar com esse estado restaurado;
4. abre uma worktree temporaria da branch `radar-state`;
5. faz merge deterministico entre o estado local e o remoto;
6. commita apenas `data/seen_jobs.json` na branch `radar-state`;
7. usa `[skip ci]` na mensagem de commit.

Regras de merge:

- status finais vencem status intermediarios;
- o registro com `last_seen_at` mais recente vence em conflitos equivalentes;
- `first_seen_at` usa o menor valor;
- `last_seen_at` usa o maior valor;
- `notified_at` usa o maior valor disponivel;
- `attempts` usa o maior valor;
- `next_retry_at` usa o maior valor disponivel quando o status continua em retry;
- erros sao limpos quando o status merged nao esta mais em retry nem dead letter.

## Backups e migracao

- arquivos invalidos geram backup antes da recuperacao;
- migracoes de schema geram backup antes da primeira gravacao;
- versao `1` e migrada para `3`;
- versao `2` e migrada para `3`.

## Validacao manual

```powershell
ruff check .
pytest
pytest --cov=src/radar_vagas --cov-report=term-missing
python -m radar_vagas --dry-run --verbose
```

## Observacoes

- `data/seen_jobs.json` deve permanecer fora dos commits locais de desenvolvimento;
- a branch `radar-state` deve existir apenas para estado operacional;
- a CI ignora `push` nessa branch para nao rodar testes por mudancas de estado.
