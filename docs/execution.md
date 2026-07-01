# Execucao Local e GitHub Actions

## Objetivo

Este documento centraliza como executar, validar e operar o Radar de Vagas localmente e no GitHub Actions.

## Execucao local

### Requisitos

- Python 3.12 ou superior
- Git
- acesso de rede para consultar providers e enviar webhook quando a execucao nao for `dry-run`

### Setup no Windows

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

### Arquivos de configuracao

- `.env`
- `config/profile.yaml`
- `config/candidate_profile.local.yaml`

Exemplo minimo de `.env`:

```dotenv
DISCORD_WEBHOOK_URL=
JOOBLE_API_KEY=
CANDIDATE_EMAIL=
CANDIDATE_PHONE=
CANDIDATE_PROFILE_PATH=config/candidate_profile.local.yaml
LOG_LEVEL=INFO
ENVIRONMENT=development
```

### Comandos principais

Validacao:

```powershell
ruff check .
pytest
pytest --cov=src/radar_vagas --cov-report=term-missing
```

Dry-run com preservacao dos DOCX:

```powershell
python -m radar_vagas --dry-run --save-resumes --verbose
```

Execucao normal:

```powershell
python -m radar_vagas --verbose
```

Geracao de curriculo por fixture:

```powershell
python -m radar_vagas --generate-resume tests/fixtures/jobs/bi_job.json
```

Teste do webhook:

```powershell
python -m radar_vagas --test-discord
```

## Dry-run

No modo `dry-run`:

- nao envia mensagens para o Discord;
- nao persiste alteracoes em `data/seen_jobs.json`;
- ainda executa filtros, scoring e geracao local quando aplicavel;
- pode manter DOCX apenas se `--save-resumes` for usado.

## GitHub Actions

### Workflows

- `.github/workflows/ci.yml`
- `.github/workflows/radar.yml`

### CI

Responsabilidades:

- instalar dependencias;
- executar `ruff check .`;
- executar `pytest`;
- validar o repositorio sem usar secrets produtivos.

Permissoes:

- `contents: read`

### Radar

Responsabilidades:

- executar o radar por `workflow_dispatch` ou agenda;
- restaurar e atualizar o estado operacional;
- gerar curriculos temporarios;
- enviar notificacoes;
- limpar arquivos sensiveis ao final.

Permissoes:

- nivel do workflow: minimo de leitura;
- job que atualiza estado: `contents: write`.

### Secrets necessarios

- `DISCORD_WEBHOOK_URL`
- `JOOBLE_API_KEY`
- `CANDIDATE_EMAIL`
- `CANDIDATE_PHONE`
- `CANDIDATE_PROFILE_YAML`

## Agenda

O workflow produtivo roda de segunda a sexta em dois horarios de referencia de negocio:

- 08:00
- 14:00

Timezone documentado:

- `America/Sao_Paulo`

## Estado operacional

O arquivo `data/seen_jobs.json` e tratado como estado operacional e sincronizado por branch dedicada `radar-state`.

Mais detalhes:

- [Arquitetura](architecture.md)
- [Operacoes](operations.md)
- [Seguranca](security.md)

## Validacao manual recomendada

1. Rodar `ruff check .`.
2. Rodar `pytest`.
3. Rodar `python -m radar_vagas --dry-run --save-resumes --verbose`.
4. Revisar os DOCX gerados em `output/resumes/`.
5. Rodar `python -m radar_vagas --verbose` somente com secrets e perfil local validos.
