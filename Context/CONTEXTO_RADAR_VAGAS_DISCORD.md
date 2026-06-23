# Contexto do Projeto — Radar de Vagas com Discord

**Versão 2.0 — inclui geração automática de currículos otimizados por vaga**

## 1. Visão geral

Criar um sistema pessoal e automatizado para localizar, filtrar, classificar e notificar vagas de emprego aderentes ao perfil de Renan Dobriansky da Silva. Para cada vaga elegível, o sistema também deverá gerar um currículo individual em formato DOCX, otimizado para a descrição da oportunidade e compatível com sistemas ATS.

O sistema deverá executar duas vezes por dia, de segunda a sexta-feira, às 08:00 e às 14:00 no fuso `America/Sao_Paulo`, e publicar somente vagas novas e relevantes em um servidor privado do Discord. Cada notificação deverá incluir a análise da vaga, o link original e o currículo correspondente como arquivo anexado.

O projeto será desenvolvido em Python com apoio do Codex e deverá ser simples de executar localmente, testável e preparado para automação pelo GitHub Actions.

Nome sugerido do projeto:

```text
radar-vagas-discord
```

---

## 2. Objetivo principal

Automatizar o seguinte fluxo:

```text
APIs de vagas
    ↓
normalização dos resultados
    ↓
remoção de duplicatas
    ↓
filtros eliminatórios
    ↓
cálculo de aderência
    ↓
seleção de vagas com score >= 70
    ↓
extração de palavras-chave e requisitos
    ↓
seleção de experiências, competências e projetos verdadeiros
    ↓
geração de currículo ATS em DOCX
    ↓
notificação no Discord com currículo anexado
    ↓
registro da vaga e do currículo gerado
```

O sistema não deve realizar candidaturas automaticamente.

---

## 3. Perfil profissional utilizado na análise

### 3.1 Dados pessoais relevantes

- Nome: Renan Dobriansky da Silva
- Localização principal: Curitiba, Paraná
- Formação: Ciência de Dados para Negócios — FAE Business School
- Previsão de conclusão: 2027
- Área de atuação: Dados, Business Intelligence e automações
- Senioridade desejada: Júnior ou Pleno inicial

### 3.2 Competências principais

- Python
- pandas
- SQL
- PostgreSQL
- Firebird
- SQL Server
- Power BI
- DAX
- Power Query / linguagem M
- ETL e pipelines de dados
- Modelagem de dados
- Dashboards e indicadores
- Análise exploratória
- Automação de processos
- Git e GitHub
- Excel

### 3.3 Experiências e diferenciais

- Experiência profissional como Analista de Dados
- Construção de dashboards e indicadores no Power BI
- Automação de processos e rotinas de dados
- Integração com bancos de dados relacionais
- Projetos acadêmicos e pessoais envolvendo engenharia e análise de dados
- 1º lugar no Data Science Day 2024 da FAE
- 2º lugar em competição de dashboards da FAE



### 3.4 Dados utilizados no currículo

Cabeçalho padrão:

- Nome: Renan Dobriansky da Silva
- Cargo-alvo: adaptado ao título de cada vaga
- Localização: Curitiba — PR
- Telefone: obtido de variável de ambiente protegida
- E-mail: obtido de variável de ambiente protegida
- LinkedIn: `https://www.linkedin.com/in/renandobriansky/`
- GitHub: `https://github.com/RenanDobriansky`

Estrutura obrigatória:

1. Cabeçalho;
2. Resumo Profissional;
3. Competências Técnicas;
4. Experiência Profissional;
5. Projetos Selecionados;
6. Formação e Destaques;
7. Experiência Adicional, somente quando relevante.

Regras de veracidade:

- nunca inventar experiência, resultado, ferramenta, certificação ou formação;
- usar apenas conteúdo previamente aprovado no perfil-base;
- adaptar a ordem e a redação sem alterar o significado factual;
- mencionar Administração na ESIC somente como curso interrompido;
- não afirmar domínio de ferramentas que aparecem apenas como lacunas;
- não copiar blocos extensos da descrição da vaga;
- não inserir palavras-chave sem evidência no perfil profissional;
- manter datas, empresas e títulos exatamente como registrados no perfil-base.

### 3.5 Conteúdo profissional priorizado

O catálogo de conteúdo aprovado deverá incluir, no mínimo:

- experiência como Analista de Dados na Smart Data BI;
- criação de dashboards e indicadores em Power BI;
- desenvolvimento de medidas DAX e transformações em Power Query;
- consultas e integração com bancos PostgreSQL, Firebird e SQL Server;
- automações e rotinas em Python;
- projetos de BI integrado a ERP Firebird;
- pipeline de indicadores financeiros com dados da CVM em Python e PostgreSQL;
- automação de ordens de compra em PDF para arquivos de importação;
- formação em Ciência de Dados para Negócios na FAE, conclusão prevista em 2027;
- Administração na ESIC, curso interrompido;
- 1º lugar no Data Science Day 2024 da FAE;
- 2º lugar em competição de dashboards da FAE.

Cada experiência, competência e projeto deverá possuir tags para permitir seleção determinística, por exemplo:

```yaml
tags:
  - power-bi
  - sql
  - python
  - financeiro
  - automacao
```

---

## 4. Vagas-alvo

### 4.1 Títulos prioritários

- Analista de Dados Júnior
- Analista de Dados
- Analista de BI Júnior
- Analista de Business Intelligence
- BI Analyst
- Data Analyst
- Analista de Inteligência Comercial
- Analista de Inteligência de Mercado
- Analista de Dados Financeiros
- Analista de Governança de Dados
- Analista de Analytics
- Analista de Performance
- Analista de Indicadores
- Engenheiro de Dados Júnior
- Analytics Engineer Júnior
- Desenvolvedor Power BI
- Consultor de BI Júnior

### 4.2 Senioridade aceita

Priorizar:

- Júnior
- Assistente com atuação analítica
- Pleno inicial
- Vagas sem senioridade explícita, desde que os requisitos sejam compatíveis

Aplicar penalização ou rejeição para:

- Sênior
- Especialista
- Staff
- Principal
- Tech Lead
- Coordenador
- Gerente
- Diretor
- Head

Estágios não fazem parte do escopo inicial, mas a regra deve ser configurável.

---

## 5. Localizações aceitas

### 5.1 Presencial ou híbrido

- Curitiba
- São José dos Pinhais
- Pinhais
- Colombo
- Araucária
- Campo Largo
- Fazenda Rio Grande
- Região Metropolitana de Curitiba

### 5.2 Remoto

Aceitar vagas remotas disponíveis para candidatos residentes no Brasil.

Rejeitar vagas presenciais ou híbridas fora da região definida, salvo se a configuração indicar o contrário.

---

## 6. Fontes de vagas

### 6.1 Fonte principal — Jooble REST API

A Jooble será a primeira integração do MVP porque oferece pesquisa por palavras-chave e localização e retorna dados estruturados como:

- título;
- empresa;
- localização;
- descrição resumida;
- salário, quando disponível;
- tipo de contratação;
- link;
- data de atualização;
- identificador da vaga.

A integração exige uma chave da API, armazenada somente em variável de ambiente ou segredo do GitHub.

Documentação:

```text
https://help.jooble.org/pt-PT/support/solutions/articles/60001448238-documenta%C3%A7%C3%A3o-da-api-rest
```

Cadastro da chave:

```text
https://pt.jooble.org/api/about
```

### 6.2 Fonte complementar — Remotive

A Remotive será utilizada para vagas remotas.

Regras importantes:

- manter o link original da Remotive;
- identificar a Remotive como fonte;
- não republicar os resultados em outros agregadores;
- considerar que a API pública pode apresentar vagas com atraso.

Documentação:

```text
https://remotive.com/remote-jobs/api
```

### 6.3 Fontes futuras

- Adzuna
- páginas de carreira de empresas específicas;
- feeds RSS;
- Google Programmable Search;
- integrações permitidas com outros portais.

### 6.4 Fontes fora do MVP

Não implementar scraping direto de LinkedIn, Indeed ou outros portais protegidos no MVP.

Motivos:

- mudanças frequentes de HTML;
- bloqueios e captchas;
- necessidade de autenticação;
- risco de violar termos de uso;
- baixa estabilidade da automação.

---

## 7. Requisitos funcionais

### RF01 — Consultar vagas

O sistema deve consultar todas as combinações configuradas de termo, localização e fonte.

### RF02 — Normalizar resultados

Todas as fontes devem ser convertidas para um modelo comum de vaga.

### RF03 — Remover duplicatas

Uma vaga não pode ser enviada mais de uma vez.

A deduplicação deve usar, nesta ordem:

1. identificador da fonte;
2. URL normalizada;
3. fingerprint formada por título, empresa e localização normalizados.

Parâmetros de rastreamento, como `utm_source`, devem ser removidos da URL antes da comparação.

### RF04 — Aplicar filtros eliminatórios

Eliminar vagas que:

- sejam claramente sênior ou de liderança;
- sejam presenciais fora das localizações aceitas;
- não tenham relação com Dados, BI ou Analytics;
- já tenham sido processadas;
- estejam antigas além do limite configurado;
- contenham termos de exclusão configurados.

### RF05 — Calcular score

Cada vaga deve receber um score de 0 a 100.

### RF06 — Classificar prioridade

- 85 a 100: Alta prioridade;
- 70 a 84: Boa oportunidade;
- abaixo de 70: não notificar nem gerar currículo.

### RF07 — Extrair requisitos e palavras-chave

Para cada vaga elegível, extrair:

- título-alvo;
- competências técnicas;
- ferramentas;
- responsabilidades;
- domínio de negócio;
- senioridade;
- modalidade;
- palavras-chave relevantes para ATS;
- lacunas reais do candidato.

A extração do MVP deve ser determinística, baseada em aliases e regras configuráveis.

### RF08 — Gerar currículo otimizado

Gerar um currículo individual em DOCX para cada vaga elegível.

O currículo deve:

- usar o título da vaga como cargo-alvo;
- priorizar palavras-chave verdadeiras encontradas no anúncio;
- selecionar e ordenar competências aderentes;
- selecionar os bullets de experiência mais relevantes;
- selecionar de dois a três projetos aderentes;
- gerar resumo profissional curto com blocos previamente aprovados;
- ser compatível com ATS;
- evitar tabelas, colunas, ícones, imagens, cabeçalhos flutuantes e elementos gráficos;
- ocupar preferencialmente uma página e no máximo duas;
- usar português no MVP;
- ser salvo com nome sanitizado:

```text
Curriculo_Renan_Dobriansky_<Empresa>_<Cargo>.docx
```

### RF09 — Validar o currículo

Antes do envio, validar:

- presença das seções obrigatórias;
- ausência de campos vazios críticos;
- ausência de competências não comprovadas;
- ausência de placeholders;
- tamanho máximo configurado;
- nome de arquivo seguro;
- extensão DOCX válida;
- leitura do arquivo gerado sem corrupção.

Se a validação falhar, a vaga não deve ser marcada como notificada.

### RF10 — Notificar no Discord

Cada vaga deve ser enviada em uma mensagem própria, contendo:

- cargo;
- empresa;
- localização;
- modalidade;
- score;
- prioridade;
- competências aderentes;
- lacunas;
- data de publicação ou atualização;
- fonte;
- link direto;
- currículo DOCX anexado.

A mensagem deve deixar claro que as lacunas não foram incluídas como competências no currículo.

### RF11 — Registrar histórico

Após o processamento, registrar a vaga e o estado do currículo.

Status mínimos:

- `rejected`;
- `eligible`;
- `resume_generated`;
- `resume_failed`;
- `notified`;
- `notification_failed`.

### RF12 — Modo de simulação

O programa deve aceitar:

```bash
python -m radar_vagas --dry-run
```

Nesse modo, deve buscar, analisar e mostrar quais conteúdos seriam selecionados, sem enviar ao Discord e sem alterar o histórico.

Também deve aceitar:

```bash
python -m radar_vagas --dry-run --save-resumes
```

Nesse modo, pode salvar os DOCX localmente para revisão, mas continua sem enviar ao Discord e sem alterar o histórico.

### RF13 — Teste do webhook

O programa deve aceitar:

```bash
python -m radar_vagas --test-discord
```

O teste deve enviar uma mensagem e um DOCX fictício sem dados pessoais reais.

### RF14 — Geração manual de currículo

O programa deve permitir gerar um currículo a partir de uma vaga já normalizada ou de um arquivo JSON de entrada:

```bash
python -m radar_vagas --generate-resume job.json
```

### RF15 — Limite por execução

Para não poluir o canal:

- processar e enviar no máximo 10 vagas por execução;
- ordenar por score decrescente;
- gerar um currículo por vaga enviada;
- não agrupar currículos de vagas diferentes na mesma mensagem;
- manter vagas excedentes em uma fila ou status configurável.

---

## 8. Modelo normalizado da vaga

```python
JobPosting(
    provider: str,
    provider_job_id: str | None,
    title: str,
    company: str | None,
    location: str | None,
    work_mode: str | None,
    employment_type: str | None,
    description: str,
    salary: str | None,
    published_at: datetime | None,
    updated_at: datetime | None,
    url: str,
    source_name: str,
    search_term: str | None,
    collected_at: datetime,
)
```

Após a análise:

```python
EvaluatedJob(
    job: JobPosting,
    score: int,
    priority: str,
    matched_skills: list[str],
    missing_skills: list[str],
    extracted_keywords: list[str],
    relevant_domains: list[str],
    rejection_reasons: list[str],
    is_eligible: bool,
    fingerprint: str,
)

ResumeArtifact(
    job_fingerprint: str,
    target_title: str,
    company: str,
    file_path: Path,
    file_name: str,
    file_sha256: str,
    selected_skill_ids: list[str],
    selected_experience_bullet_ids: list[str],
    selected_project_ids: list[str],
    generated_at: datetime,
    validation_errors: list[str],
    is_valid: bool,
)
```

---

## 9. Regra inicial de scoring

O algoritmo deve ser determinístico e configurável. O MVP não precisa usar uma API de inteligência artificial em tempo de execução.

### 9.1 Distribuição sugerida

| Grupo | Pontos |
|---|---:|
| Compatibilidade do cargo | 25 |
| Compatibilidade técnica | 35 |
| Senioridade | 15 |
| Localização/modalidade | 15 |
| Atualidade da vaga | 10 |
| **Total** | **100** |

### 9.2 Cargo — até 25 pontos

- título prioritário exato ou muito próximo: 25;
- título relacionado: 15 a 22;
- título apenas parcialmente relacionado: 5 a 14;
- título fora da área: rejeitar.

### 9.3 Competências — até 35 pontos

Pesos iniciais sugeridos:

| Competência | Peso relativo |
|---|---:|
| SQL | 10 |
| Power BI | 10 |
| Python | 8 |
| DAX | 6 |
| Power Query / M | 6 |
| ETL / pipeline | 5 |
| PostgreSQL | 4 |
| Modelagem de dados | 4 |
| Dashboard / indicadores | 4 |
| Excel | 3 |
| Git | 2 |
| Cloud | 2 |
| PySpark | 2 |

O cálculo deve normalizar a pontuação para o limite máximo de 35.

Competências desejáveis não encontradas no perfil devem ser exibidas como lacunas, mas não necessariamente causar rejeição.

### 9.4 Senioridade — até 15 pontos

- Júnior: 15
- Sem senioridade explícita: 12
- Pleno: 8
- Assistente: 7
- Sênior ou liderança: rejeitar

### 9.5 Localização — até 15 pontos

- remoto Brasil: 15
- Curitiba: 15
- Região Metropolitana de Curitiba: 13
- híbrido com localização ambígua: 6
- presencial fora da região: rejeitar

### 9.6 Atualidade — até 10 pontos

- publicada ou atualizada nas últimas 24 horas: 10
- até 3 dias: 8
- até 7 dias: 5
- até 14 dias: 2
- acima do limite configurado: rejeitar

### 9.7 Regras de segurança do score

- O score nunca pode ultrapassar 100.
- Uma vaga rejeitada deve permanecer rejeitada mesmo que a soma parcial ultrapasse 70.
- Ausência de descrição deve reduzir a confiança do score.
- A decisão deve armazenar uma explicação curta e auditável.

---

## 10. Configuração sugerida

Arquivo:

```text
config/profile.yaml
```

Exemplo:

```yaml
candidate:
  name: "Renan Dobriansky da Silva"
  city: "Curitiba"
  state: "PR"
  timezone: "America/Sao_Paulo"
  linkedin_url: "https://www.linkedin.com/in/renandobriansky/"
  github_url: "https://github.com/RenanDobriansky"
  email_env: "CANDIDATE_EMAIL"
  phone_env: "CANDIDATE_PHONE"

resume:
  enabled: true
  output_directory: "output/resumes"
  language: "pt-BR"
  preferred_max_pages: 1
  hard_max_pages: 2
  maximum_projects: 3
  maximum_skills: 12
  attach_to_discord: true
  keep_generated_files: false
  file_name_pattern: "Curriculo_Renan_Dobriansky_{company}_{title}.docx"

search:
  minimum_score: 70
  maximum_jobs_per_run: 10
  maximum_age_days: 14
  include_internships: false

  terms:
    - "Analista de Dados"
    - "Analista de BI"
    - "Business Intelligence"
    - "Data Analyst"
    - "BI Analyst"
    - "Inteligência Comercial"
    - "Governança de Dados"
    - "Engenheiro de Dados Júnior"

  locations:
    - "Curitiba"
    - "São José dos Pinhais"
    - "Pinhais"
    - "Colombo"
    - "Araucária"
    - "Campo Largo"
    - "Fazenda Rio Grande"
    - "Remoto Brasil"

profile:
  primary_skills:
    - "Python"
    - "pandas"
    - "SQL"
    - "PostgreSQL"
    - "Firebird"
    - "Power BI"
    - "DAX"
    - "Power Query"
    - "M"
    - "ETL"
    - "modelagem de dados"
    - "dashboards"
    - "automação"

  secondary_skills:
    - "Excel"
    - "Git"
    - "SQL Server"
    - "Oracle"
    - "MySQL"

filters:
  excluded_seniority:
    - "sênior"
    - "senior"
    - "especialista"
    - "staff"
    - "principal"
    - "lead"
    - "coordenador"
    - "gerente"
    - "diretor"
    - "head"

  excluded_terms:
    - "cientista de dados sênior"
    - "engenheiro de software"
    - "desenvolvedor full stack"
```

---

## 11. Estrutura do projeto

```text
radar-vagas-discord/
├── AGENTS.md
├── README.md
├── CONTEXTO_RADAR_VAGAS_DISCORD.md
├── pyproject.toml
├── .env.example
├── .gitignore
│
├── config/
│   ├── profile.yaml
│   ├── candidate_profile.example.yaml
│   └── candidate_profile.local.yaml
│
├── data/
│   ├── .gitkeep
│   └── seen_jobs.json
│
├── output/
│   └── resumes/
│       └── .gitkeep
│
├── src/
│   └── radar_vagas/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── config.py
│       ├── models.py
│       ├── pipeline.py
│       ├── scoring.py
│       ├── deduplication.py
│       ├── storage.py
│       ├── text_utils.py
│       │
│       ├── providers/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── jooble.py
│       │   └── remotive.py
│       │
│       ├── resumes/
│       │   ├── __init__.py
│       │   ├── profile.py
│       │   ├── keyword_extractor.py
│       │   ├── content_selector.py
│       │   ├── generator.py
│       │   ├── validator.py
│       │   └── file_names.py
│       │
│       └── notifications/
│           ├── __init__.py
│           └── discord.py
│
├── tests/
│   ├── fixtures/
│   │   ├── candidate_profile.yaml
│   │   └── jobs/
│   ├── test_scoring.py
│   ├── test_deduplication.py
│   ├── test_storage.py
│   ├── test_resume_profile.py
│   ├── test_resume_keywords.py
│   ├── test_resume_selection.py
│   ├── test_resume_generator.py
│   ├── test_resume_validator.py
│   ├── test_jooble_provider.py
│   ├── test_remotive_provider.py
│   └── test_discord_notification.py
│
└── .github/
    └── workflows/
        └── radar.yml
```

O arquivo `candidate_profile.local.yaml` contém o perfil profissional aprovado e não deve ser versionado quando houver dados pessoais. O arquivo `candidate_profile.example.yaml` deve mostrar somente a estrutura, com valores fictícios.

A pasta `output/resumes/` deve ser ignorada pelo Git, exceto pelo `.gitkeep`.

---

## 12. Dependências sugeridas

### Produção

- `httpx`
- `pydantic`
- `pydantic-settings`
- `PyYAML`
- `python-dotenv`
- `tenacity`
- `python-dateutil`
- `python-docx`

### Desenvolvimento

- `pytest`
- `pytest-cov`
- `respx`
- `ruff`

Evitar dependências sem necessidade.

A persistência inicial será feita em JSON para funcionar localmente e permitir versionamento simples no GitHub Actions. Uma migração para SQLite ou PostgreSQL poderá ser feita posteriormente.

---

## 13. Variáveis de ambiente

Arquivo local:

```text
.env
```

Modelo seguro:

```dotenv
DISCORD_WEBHOOK_URL=
JOOBLE_API_KEY=
CANDIDATE_EMAIL=
CANDIDATE_PHONE=
CANDIDATE_PROFILE_PATH=config/candidate_profile.local.yaml
LOG_LEVEL=INFO
ENVIRONMENT=development
```

Regras:

- nunca versionar `.env`;
- nunca imprimir a URL completa do webhook nos logs;
- nunca incluir chaves, telefone ou e-mail em mensagens de erro;
- usar GitHub Secrets na automação;
- revogar o webhook se a URL for exposta.

---

## 14. Discord

### 14.1 Servidor sugerido

Nome:

```text
Radar de Vagas — Renan
```

### 14.2 Estrutura inicial de canais

```text
📌 ACOMPANHAMENTO
├── #novas-vagas
├── #alta-prioridade
├── #candidaturas
└── #logs-radar
```

No MVP, utilizar somente:

```text
#novas-vagas
```

### 14.3 Webhook

O webhook será criado no canal `#novas-vagas`.

O envio deve usar:

- requisição HTTP `POST` multipart;
- `payload_json` para o embed;
- `files[0]` para anexar o currículo DOCX;
- `wait=true` para confirmar que a mensagem foi criada;
- `allowed_mentions` com lista vazia para impedir menções acidentais;
- uma vaga e um currículo por mensagem;
- timeout;
- retry com backoff apenas para erros transitórios;
- validação prévia do tamanho e da existência do anexo.

### 14.4 Formato do embed

Título:

```text
Analista de Dados Júnior — Empresa
```

Campos:

```text
Localização: Curitiba — Híbrido
Aderência: 86%
Prioridade: Alta
Compatível: SQL, Power BI, Python
Lacunas: Azure, Databricks
Atualização: 23/06/2026
Fonte: Jooble
Currículo: DOCX otimizado anexado
```

Descrição curta:

```text
Boa compatibilidade com BI, SQL e construção de indicadores.
```

Links e anexo:

- o título do embed deve apontar para a URL original da vaga;
- o arquivo DOCX deve aparecer como anexo da mesma mensagem;
- o nome do arquivo deve identificar empresa e cargo;
- o corpo da mensagem não deve expor telefone ou e-mail, pois esses dados já estarão no currículo anexado.

### 14.5 Cores sugeridas

- Alta prioridade: verde
- Boa oportunidade: amarelo
- Erro/log crítico: vermelho

As cores devem ficar centralizadas em constantes e não espalhadas pelo código.

---

## 15. Persistência e deduplicação

Arquivo inicial:

```text
data/seen_jobs.json
```

Estrutura sugerida:

```json
{
  "version": 1,
  "jobs": {
    "fingerprint_sha256": {
      "provider": "jooble",
      "provider_job_id": "123456",
      "title": "Analista de Dados",
      "company": "Empresa",
      "url": "https://exemplo.com/vaga",
      "score": 82,
      "status": "notified",
      "first_seen_at": "2026-06-23T11:00:00Z",
      "last_seen_at": "2026-06-23T11:00:00Z",
      "notified_at": "2026-06-23T11:00:05Z",
      "resume_status": "generated",
      "resume_file_name": "Curriculo_Renan_Dobriansky_Empresa_Analista_de_Dados.docx",
      "resume_sha256": "hash_do_arquivo",
      "resume_generated_at": "2026-06-23T11:00:04Z"
    }
  }
}
```

Requisitos:

- escrita atômica usando arquivo temporário;
- backup simples em caso de JSON inválido;
- poda de registros antigos, por exemplo, acima de 180 dias;
- não alterar o estado no modo `--dry-run`;
- diferenciar `rejected`, `eligible`, `resume_generated`, `resume_failed`, `notified` e `notification_failed`;
- registrar o hash do currículo para auditoria sem versionar o DOCX;
- não persistir o caminho temporário de um runner do GitHub Actions.

---

## 16. Logs

Os logs devem conter:

- início e fim da execução;
- fonte consultada;
- número de vagas retornadas;
- número de duplicadas;
- número de rejeitadas;
- número de elegíveis;
- número de currículos gerados e validados;
- número de falhas na geração de currículos;
- número de notificações enviadas;
- erros resumidos.

Nunca registrar:

- webhook completo;
- chaves de API;
- conteúdo integral de variáveis de ambiente.

Formato recomendado:

```text
2026-06-23 08:00:02 | INFO | jooble | fetched=42
2026-06-23 08:00:03 | INFO | pipeline | duplicates=12 rejected=23 eligible=7
2026-06-23 08:00:04 | INFO | resumes | generated=7 invalid=0
2026-06-23 08:00:05 | INFO | discord | sent=7 failed=0
```

---

## 17. Tratamento de erros

### API de vagas

- timeout de conexão e leitura;
- retry com backoff para `429`, `500`, `502`, `503` e `504`;
- não repetir automaticamente erros `400`, `401`, `403` e `404`;
- falha de uma fonte não deve impedir o processamento das demais.

### Discord

- validar presença do webhook;
- tratar `429` respeitando o tempo de espera retornado;
- usar `wait=true`;
- registrar apenas parte segura da resposta em erros;
- marcar a vaga como `notification_failed` quando necessário.

### Geração de currículos

- falha ao carregar o perfil-base não pode gerar currículo incompleto;
- ausência de dados de contato deve produzir erro de configuração;
- arquivo DOCX inválido deve ser descartado;
- falha de uma vaga não deve impedir a geração das demais;
- nunca substituir currículo existente sem geração bem-sucedida;
- remover arquivos temporários após envio, quando configurado;
- registrar somente nomes de arquivos e códigos de erro seguros.

### Estado

- usar lock ou escrita atômica;
- impedir corrupção do JSON;
- não perder o histórico anterior em caso de falha parcial.

---

## 18. GitHub Actions

O workflow deve:

- executar manualmente com `workflow_dispatch`;
- executar de segunda a sexta às 08:00 e 14:00;
- usar o fuso `America/Sao_Paulo`;
- instalar Python;
- instalar dependências;
- executar testes rápidos antes do pipeline;
- executar o radar;
- persistir mudanças em `data/seen_jobs.json`;
- usar `concurrency` para evitar execuções simultâneas;
- receber os segredos pelo GitHub Secrets;
- gerar os currículos em diretório temporário;
- anexar os currículos ao Discord antes de limpar os arquivos;
- não fazer commit dos currículos gerados;
- disponibilizar os DOCX como artifact somente em execução manual e com retenção curta, quando explicitamente habilitado.

Agendamento esperado:

```yaml
on:
  workflow_dispatch:
  schedule:
    - cron: "0 8,14 * * 1-5"
      timezone: "America/Sao_Paulo"
```

Permissões necessárias para persistir o arquivo:

```yaml
permissions:
  contents: write
```

O workflow não deve fazer commit quando o arquivo não tiver sido alterado.

Mensagem de commit sugerida:

```text
chore: update radar job history [skip ci]
```

---

## 19. Requisitos não funcionais

- Python 3.12 ou superior.
- Código tipado.
- Funções pequenas e com responsabilidade clara.
- Configurações fora do código.
- Cobertura de testes para regras críticas.
- Nenhum segredo versionado.
- Compatível com Windows e Linux.
- Mensagens e documentação em português.
- Datas internas em UTC e apresentação em `America/Sao_Paulo`.
- Requisições HTTP com timeout.
- Logs estruturados e legíveis.
- Projeto executável sem dependência de uma API de IA.
- Currículos gerados com `python-docx` e estrutura linear compatível com ATS.
- Nenhuma afirmação profissional pode ser criada sem origem no perfil-base aprovado.
- Diretório de currículos gerados deve permanecer fora do versionamento.
- Nomes de arquivo devem ser sanitizados para Windows e Linux.

---

## 20. Critérios de aceite do MVP

O MVP será considerado concluído quando:

1. A mensagem de teste chegar ao canal do Discord.
2. A Jooble retornar e normalizar vagas.
3. A Remotive retornar e normalizar vagas remotas.
4. O score produzir uma explicação auditável.
5. Vagas abaixo de 70 não forem notificadas nem gerarem currículo.
6. Vagas sênior forem rejeitadas.
7. A mesma vaga não for enviada duas vezes.
8. O perfil profissional aprovado for carregado e validado.
9. Uma vaga elegível gerar um DOCX sem corrupção.
10. O currículo usar o título correto da vaga.
11. O currículo priorizar competências, experiências e projetos aderentes.
12. Nenhuma lacuna for apresentada como competência do candidato.
13. O DOCX não utilizar tabelas, colunas, imagens ou ícones.
14. O currículo for anexado à mesma mensagem da vaga no Discord.
15. O nome do arquivo seguir o padrão definido.
16. O modo `--dry-run` não enviar mensagem nem alterar histórico.
17. O modo `--dry-run --save-resumes` gerar arquivos para inspeção sem alterar histórico.
18. Os testes automatizados passarem.
19. O workflow manual do GitHub Actions funcionar.
20. O agendamento estiver configurado para 08:00 e 14:00 em dias úteis.
21. Nenhum segredo, dado de contato ou currículo gerado estiver versionado indevidamente.

---

## 21. Fora do escopo inicial

- candidatura automática;
- login automático em sites de emprego;
- preenchimento automático de formulários;
- leitura de e-mails;
- integração com WhatsApp;
- dashboard web;
- uso obrigatório de LLM para scoring ou redação;
- geração de afirmações profissionais novas por IA;
- sincronização com a planilha Controle de Candidaturas;
- scraping de LinkedIn ou Indeed;
- bot interativo com comandos no Discord.

Esses itens podem ser desenvolvidos em fases posteriores.

---

## 22. Evoluções futuras

### Fase 2

- dois webhooks: `#alta-prioridade` e `#novas-vagas`;
- integração com Adzuna;
- lista configurável de empresas-alvo;
- SQLite;
- resumo diário;
- exportação CSV;
- geração opcional de PDF a partir do DOCX;
- versões de currículo em português e inglês;
- revisão visual automática de tamanho e quebras de página.

### Fase 3

- integração com Google Sheets;
- atualização da planilha Controle de Candidaturas;
- painel Streamlit;
- análise semântica com embeddings ou LLM;
- comandos no Discord;
- botão para marcar candidatura;
- alerta de follow-up.

### Fase 4

- uso opcional de LLM para reescrita controlada de resumos e bullets;
- validação de toda frase gerada contra evidências do perfil-base;
- geração de carta de apresentação;
- geração de checklist para candidatura;
- preparação de perguntas de entrevista;
- integração com calendário.

---

## 23. Decisões arquiteturais

1. **Webhook em vez de bot completo:** o MVP só precisa publicar mensagens.
2. **APIs em vez de scraping:** maior estabilidade e menor risco operacional.
3. **Scoring determinístico:** sem custo de API e com decisão auditável.
4. **Configuração YAML:** filtros e pesos podem ser alterados sem editar o código.
5. **Estado em JSON:** simples para desenvolvimento e GitHub Actions.
6. **Arquitetura por providers:** novas fontes podem ser adicionadas sem alterar o pipeline central.
7. **GitHub Actions como execução principal:** o radar funciona mesmo com o computador desligado.
8. **Execução local preservada:** facilita testes e depuração no Windows.
9. **Currículo por catálogo aprovado:** a otimização seleciona e reorganiza fatos verdadeiros, sem inventar conteúdo.
10. **DOCX gerado com python-docx:** permite arquivo ATS simples e dispensa um editor externo no runner.
11. **Uma mensagem por vaga:** mantém o currículo anexado claramente associado à oportunidade correta.
12. **Arquivos temporários não versionados:** protege dados pessoais e evita crescimento do repositório.

---

## 24. Resultado esperado

Ao fim da primeira versão, Renan deverá receber no Discord apenas vagas novas, relevantes e priorizadas, sem precisar executar buscas manuais todos os dias.

Exemplo:

```text
🟢 Analista de BI Júnior — Empresa X

📍 Curitiba — Híbrido
🎯 Aderência: 88%
✅ SQL, Power BI, DAX e modelagem de dados
⚠️ Lacunas: Azure
📅 Atualizada hoje
🔎 Fonte: Jooble

Prioridade: Alta
[Abrir vaga]

📎 Curriculo_Renan_Dobriansky_Empresa_X_Analista_de_BI_Junior.docx
```
