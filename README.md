# Radar de Vagas

Projeto Python para buscar, filtrar, priorizar e notificar vagas aderentes ao perfil profissional de Renan, com geracao deterministica de curriculos ATS em DOCX e envio por webhook do Discord.

## Status

O projeto ja possui pipeline integrado com providers, scoring deterministico, historico local, geracao de curriculos e notificacao no Discord. As credenciais e o perfil profissional real continuam locais e fora do versionamento.

## Requisitos

- Windows ou Linux
- Python 3.12+
- Git

## Setup no Windows

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Se o launcher `py` nao estiver disponivel, use o executavel absoluto do Python 3.12 instalado na maquina.

## Comandos principais

```powershell
ruff check .
pytest
python -m radar_vagas --dry-run
python -m radar_vagas --dry-run --provider remotive --max-jobs 3 --save-resumes
python -m radar_vagas --provider jooble --minimum-score 75 --verbose
python -m radar_vagas --generate-resume tests/fixtures/jobs/bi_job.json
python -m radar_vagas --test-discord
```

## GitHub Actions

O workflow principal fica em `.github/workflows/radar.yml` e executa o radar manualmente ou de segunda a sexta, as `08:00` e `14:00`, com timezone `America/Sao_Paulo`.

### Secrets obrigatorios

Configure estes GitHub Secrets no repositorio:

- `DISCORD_WEBHOOK_URL`
- `JOOBLE_API_KEY`
- `CANDIDATE_EMAIL`
- `CANDIDATE_PHONE`
- `CANDIDATE_PROFILE_YAML`

O segredo `CANDIDATE_PROFILE_YAML` deve conter o conteudo completo do seu `config/candidate_profile.local.yaml`. O workflow recria esse arquivo apenas no runner, usa um diretorio temporario para os DOCX e remove os arquivos sensiveis ao final.

### Primeira validacao manual

1. Abra `Actions` no GitHub e execute `Radar de Vagas` com `workflow_dispatch`.
2. Confirme que as etapas `Lint`, `Test` e `Run radar` concluem com sucesso.
3. Se quiser inspecionar os DOCX da execucao manual, marque `upload_resume_artifact=true`.
4. Verifique se apenas `data/seen_jobs.json` foi commitado automaticamente quando houver alteracao.
5. Rode uma segunda execucao manual e confirme que vagas ja notificadas nao geram novo envio nem novo curriculo.

## Fluxo da CLI

- `python -m radar_vagas` executa o pipeline completo com os termos e localizacoes definidos em `config/profile.yaml`.
- `--dry-run` busca, pontua e gera curriculos sem enviar mensagens e sem alterar `data/seen_jobs.json`.
- `--provider jooble` ou `--provider remotive` limita as fontes processadas. A opcao pode ser repetida.
- `--minimum-score` e `--max-jobs` sobrescrevem os limites configurados.
- `--save-resumes` preserva os DOCX gerados; sem ela, arquivos temporarios sao removidos ao final.
- `--generate-resume CAMINHO_JSON` gera um DOCX para uma vaga normalizada em JSON.
- `--test-discord` envia uma mensagem de teste com um DOCX ficticio.
- `--verbose` ativa logs detalhados.
- Na automacao do GitHub Actions, o runner usa `RESUME_OUTPUT_DIRECTORY` temporario e limpa os DOCX ao final da execucao.

## Estrutura inicial

```text
src/radar_vagas/      Codigo-fonte do pacote
config/               Configuracoes YAML e exemplos
data/                 Persistencia local do historico
output/resumes/       Saida de curriculos gerados
tests/                Testes automatizados
Context/              Documentos de especificacao originais
```

## Seguranca

- Nao versione `.env`.
- Nao versione `config/candidate_profile.local.yaml`.
- Nao versione curriculos gerados em `output/resumes/`.
- Nunca cole o conteudo de `CANDIDATE_PROFILE_YAML` em arquivos versionados.
- Nao adicione credenciais reais em testes, codigo ou documentacao.

## Especificacao

Os arquivos `CONTEXTO_RADAR_VAGAS_DISCORD.md` e `GUIA_CODEX_RADAR_VAGAS_DISCORD.md` devem ser tratados como a fonte principal de requisitos do projeto.
