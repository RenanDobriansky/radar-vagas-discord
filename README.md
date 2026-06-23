# Radar de Vagas

Projeto Python para buscar, filtrar e priorizar vagas aderentes ao perfil profissional de Renan, com evolucao planejada para notificacoes no Discord e geracao de curriculos ATS em DOCX.

## Status

Esta primeira etapa inicializa a estrutura do projeto, as configuracoes base, a documentacao e os testes smoke. Integracoes reais com APIs, Discord e curriculos ainda nao foram implementadas.

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
python -m radar_vagas
```

## Estrutura inicial

```text
src/radar_vagas/      Codigo-fonte do pacote
config/               Configuracoes YAML e exemplos
data/                 Persistencia local planejada
output/resumes/       Saida de curriculos gerados no futuro
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

