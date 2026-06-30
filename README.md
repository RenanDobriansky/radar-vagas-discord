# Radar de Vagas

Projeto Python para buscar vagas, normalizar resultados, deduplicar, aplicar scoring deterministico, gerar curriculos ATS em DOCX e enviar oportunidades elegiveis para o Discord com um anexo por vaga.

## Status atual

O projeto ja esta funcional nas frentes principais:

- providers `Jooble` e `Remotive`
- deduplicacao por `provider_job_id`, URL normalizada e fingerprint
- filtros eliminatorios e scoring de `0` a `100`
- geracao deterministica de curriculos ATS em DOCX
- validacao do curriculo antes do envio
- notificacao no Discord com webhook e anexo
- persistencia em `data/seen_jobs.json`
- pipeline completo via CLI e GitHub Actions

Na ultima validacao local, `ruff check .` passou e `pytest --cov=src/radar_vagas --cov-report=term-missing` retornou `86 passed` com cobertura total de `89%`.

## Stack

- Python 3.12+
- `httpx`
- `pydantic` e `pydantic-settings`
- `PyYAML`
- `tenacity`
- `python-docx`
- `pytest`, `pytest-cov`, `respx`, `ruff`

## Fluxo do radar

```text
providers -> normalizacao -> deduplicacao -> historico -> filtros -> scoring
-> extracao de palavras-chave -> selecao de conteudo verdadeiro
-> geracao de curriculo DOCX -> validacao -> Discord -> atualizacao do historico
```

## Requisitos

- Windows ou Linux
- Python 3.12+
- Git

## Setup local no Windows

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Se o launcher `py` nao estiver disponivel, use o executavel absoluto do Python 3.12 instalado na maquina.

## Configuracao local

Arquivos relevantes:

- `.env`
- `config/profile.yaml`
- `config/candidate_profile.local.yaml`
- `config/candidate_profile.example.yaml`

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

Regras importantes:

- `.env` nao deve ser versionado
- `config/candidate_profile.local.yaml` deve conter apenas o perfil real local
- `config/candidate_profile.example.yaml` existe apenas como modelo ficticio
- `config/profile.yaml` concentra termos, localizacoes, filtros e pesos

## Comandos principais

```powershell
ruff check .
pytest
pytest --cov=src/radar_vagas --cov-report=term-missing
python -m radar_vagas
python -m radar_vagas --dry-run
python -m radar_vagas --dry-run --save-resumes
python -m radar_vagas --provider remotive --max-jobs 3 --verbose
python -m radar_vagas --provider jooble --term "Analista de Dados" --location "Curitiba"
python -m radar_vagas --generate-resume tests/fixtures/jobs/bi_job.json
python -m radar_vagas --test-discord
```

## Comportamento da CLI

- `python -m radar_vagas` executa o pipeline completo com a configuracao atual.
- `--dry-run` busca, avalia e gera saida sem enviar mensagens e sem alterar `data/seen_jobs.json`.
- `--dry-run --save-resumes` preserva os DOCX gerados para revisao local.
- `--provider jooble` ou `--provider remotive` limita as fontes processadas.
- `--minimum-score` e `--max-jobs` sobrescrevem os limites configurados.
- `--generate-resume CAMINHO_JSON` gera um curriculo a partir de uma vaga normalizada.
- `--test-discord` envia uma mensagem de teste com DOCX ficticio; por padrao, o arquivo de teste fica apenas em diretorio temporario.
- `--verbose` ativa logs detalhados.

## Curriculos gerados

Os curriculos seguem um modelo linear e compativel com ATS:

- sem tabelas
- sem colunas
- sem imagens
- sem icones
- com secoes claras
- com conteudo somente do perfil-base aprovado

Estrutura usada:

1. Cabecalho
2. Resumo Profissional
3. Competencias Tecnicas
4. Experiencia em Dados
5. Projetos Selecionados
6. Formacao e Destaques
7. Experiencia Adicional, quando aplicavel

Os arquivos usam o padrao:

```text
Curriculo_Renan_Dobriansky_<Empresa>_<Cargo>.docx
```

## Historico e deduplicacao

- o historico fica em `data/seen_jobs.json`
- a escrita e atomica
- JSON invalido gera backup antes da recuperacao
- registros antigos sao podados
- o modo `dry-run` nao persiste alteracoes
- a deduplicacao segue esta ordem:

```text
1. provider + provider_job_id
2. URL normalizada
3. fingerprint SHA-256 de titulo + empresa + localizacao
```

## GitHub Actions

O workflow principal fica em `.github/workflows/radar.yml`.

Ele executa:

- `workflow_dispatch`
- agendamento de segunda a sexta as `08:00` e `14:00`
- timezone `America/Sao_Paulo`
- `ruff check .`
- `pytest`
- `python -m radar_vagas`
- commit automatico de `data/seen_jobs.json` apenas quando houver alteracao

### Secrets obrigatorios

- `DISCORD_WEBHOOK_URL`
- `JOOBLE_API_KEY`
- `CANDIDATE_EMAIL`
- `CANDIDATE_PHONE`
- `CANDIDATE_PROFILE_YAML`

O secret `CANDIDATE_PROFILE_YAML` deve conter o conteudo completo de `config/candidate_profile.local.yaml`. O workflow recria esse arquivo apenas no runner, usa `RESUME_OUTPUT_DIRECTORY` temporario para os DOCX e remove os arquivos sensiveis ao final.

### Validacao manual inicial

1. Abra `Actions` no GitHub.
2. Execute o workflow `Radar de Vagas` com `workflow_dispatch`.
3. Confirme que `Lint`, `Test` e `Run radar` concluem com sucesso.
4. Se quiser inspecionar os curriculos gerados manualmente, rode com `upload_resume_artifact=true`.
5. Verifique se apenas `data/seen_jobs.json` foi commitado automaticamente quando houver alteracao.
6. Rode uma segunda execucao e confirme que vagas ja notificadas nao sao reenviadas.

## Estrutura do repositorio

```text
src/radar_vagas/      Codigo-fonte do pacote
config/               Configuracoes YAML e exemplos
data/                 Persistencia local do historico
output/resumes/       Saida local de curriculos preservados
tests/                Testes automatizados
Context/              Documentos de especificacao originais
.github/workflows/    Automacao do GitHub Actions
```

## Seguranca e versionamento

- nao versione `.env`
- nao versione `config/candidate_profile.local.yaml`
- nao versione curriculos gerados em `output/resumes/`
- nao versione backups operacionais de `data/`
- nunca cole o conteudo de `CANDIDATE_PROFILE_YAML` em arquivos versionados
- nunca registre webhook completo, chave de API, email ou telefone em logs

## Validacao recomendada

```powershell
ruff check .
pytest
pytest --cov=src/radar_vagas --cov-report=term-missing
python -m radar_vagas --dry-run --save-resumes --verbose
python -m radar_vagas --test-discord
```

## Especificacao

Os arquivos `CONTEXTO_RADAR_VAGAS_DISCORD.md` e `GUIA_CODEX_RADAR_VAGAS_DISCORD.md` continuam sendo a fonte principal de requisitos do projeto.
