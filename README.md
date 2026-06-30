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

## Fluxo da CLI

- `python -m radar_vagas` executa o pipeline completo com os termos e localizacoes definidos em `config/profile.yaml`.
- `--dry-run` busca, pontua e gera curriculos sem enviar mensagens e sem alterar `data/seen_jobs.json`.
- `--provider jooble` ou `--provider remotive` limita as fontes processadas. A opcao pode ser repetida.
- `--minimum-score` e `--max-jobs` sobrescrevem os limites configurados.
- `--save-resumes` preserva os DOCX gerados; sem ela, arquivos temporarios sao removidos ao final.
- `--generate-resume CAMINHO_JSON` gera um DOCX para uma vaga normalizada em JSON.
- `--test-discord` envia uma mensagem de teste com um DOCX ficticio.
- `--verbose` ativa logs detalhados.

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
- Nao adicione credenciais reais em testes, codigo ou documentacao.

## Especificacao

Os arquivos `CONTEXTO_RADAR_VAGAS_DISCORD.md` e `GUIA_CODEX_RADAR_VAGAS_DISCORD.md` devem ser tratados como a fonte principal de requisitos do projeto.
