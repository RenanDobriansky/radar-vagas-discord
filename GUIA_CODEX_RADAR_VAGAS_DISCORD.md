# Guia de Implementação com Codex — Radar de Vagas no Discord

**Versão 2.0 — inclui geração e envio de currículos DOCX otimizados**

## 1. Estratégia recomendada

O projeto será criado em etapas pequenas. Em cada etapa, o Codex deverá:

1. ler o contexto e os arquivos existentes;
2. implementar somente o escopo solicitado;
3. executar lint e testes;
4. corrigir falhas;
5. apresentar um resumo dos arquivos alterados;
6. indicar comandos para validação manual;
7. não acessar, criar ou imprimir segredos reais;
8. validar que nenhum currículo contenha informação não aprovada;
9. verificar o DOCX gerado antes de integrar com o Discord.

Evite pedir ao Codex para desenvolver o projeto inteiro em um único prompt.

---

## 2. Preparação manual do Discord

### Passo 1 — Criar o servidor

No Discord:

1. Clique no botão `+` na barra lateral.
2. Escolha criar um servidor próprio.
3. Use o nome:

```text
Radar de Vagas — Renan
```

4. Deixe o servidor privado.

### Passo 2 — Criar os canais

Crie a categoria:

```text
📌 ACOMPANHAMENTO
```

Crie os canais de texto:

```text
#novas-vagas
#alta-prioridade
#candidaturas
#logs-radar
```

No MVP, o sistema publicará somente em `#novas-vagas`.

### Passo 3 — Criar o webhook

No canal `#novas-vagas`:

1. Abra `Editar canal`.
2. Entre em `Integrações`.
3. Abra `Webhooks`.
4. Clique em `Novo webhook`.
5. Nomeie como:

```text
Radar de Vagas
```

6. Confirme que o canal selecionado é `#novas-vagas`.
7. Clique em `Copiar URL do webhook`.

### Passo 4 — Proteger o webhook

A URL do webhook funciona como uma credencial.

Nunca:

- enviar a URL em mensagens;
- colocar a URL no código;
- versionar a URL no GitHub;
- mostrar a URL em prints;
- colar a URL em um prompt do Codex.

Armazene-a somente no `.env` local e nos GitHub Secrets.

Se ela for exposta, exclua o webhook e crie outro.

---

## 3. Obter a chave da Jooble

1. Acesse o cadastro da API da Jooble:

```text
https://pt.jooble.org/api/about
```

2. Faça o cadastro.
3. Copie a chave recebida.
4. Armazene-a como:

```text
JOOBLE_API_KEY
```

A Remotive não exige chave para a API pública utilizada no MVP.

---


## 4. Preparar o perfil-base do currículo

A geração automática não deve depender da memória do chat. O projeto precisa de um arquivo estruturado e revisado pelo usuário.

Crie localmente:

```text
config/candidate_profile.local.yaml
```

Esse arquivo deverá conter:

- dados de cabeçalho;
- resumos profissionais aprovados;
- competências com aliases e tags;
- experiências profissionais;
- bullets verdadeiros de cada experiência;
- projetos;
- formação;
- destaques;
- experiência adicional;
- palavras ou afirmações proibidas.

Exemplo simplificado:

```yaml
candidate:
  name: "Renan Dobriansky da Silva"
  city: "Curitiba"
  state: "PR"
  linkedin_url: "https://www.linkedin.com/in/renandobriansky/"
  github_url: "https://github.com/RenanDobriansky"

summary_blocks:
  - id: "summary_data_bi"
    text: "Analista de Dados com experiência em..."
    tags: ["dados", "bi", "power-bi", "sql"]

skills:
  - id: "power_bi"
    label: "Power BI"
    aliases: ["powerbi", "business intelligence"]
    tags: ["bi", "dashboard"]

experiences:
  - id: "smart_data_bi"
    company: "Smart Data BI"
    role: "Analista de Dados"
    bullets:
      - id: "smart_dashboard"
        text: "Desenvolvimento de dashboards e indicadores..."
        tags: ["power-bi", "dax", "dashboard"]

projects:
  - id: "cvm_financeiro"
    title: "Pipeline de Indicadores Financeiros — CVM"
    bullets:
      - "Pipeline em Python e PostgreSQL..."
    tags: ["python", "postgresql", "financeiro", "etl"]

education:
  - institution: "FAE Business School"
    course: "Ciência de Dados para Negócios"
    status: "Em andamento"
    expected_completion: "2027"
  - institution: "ESIC"
    course: "Administração"
    status: "Curso interrompido"

highlights:
  - "1º lugar no Data Science Day 2024 da FAE"
  - "2º lugar em competição de dashboards da FAE"

forbidden_claims:
  - "formado em Administração"
```

Regras:

- o arquivo real deve ficar no `.gitignore`;
- o repositório deve conter somente `candidate_profile.example.yaml` com dados fictícios;
- e-mail e telefone devem vir de `CANDIDATE_EMAIL` e `CANDIDATE_PHONE`;
- revise todo o conteúdo antes de ativar a automação;
- cada bullet deve possuir um identificador estável e tags.

---

## 5. Criar o repositório

### Passo 1 — Criar a pasta

No PowerShell:

```powershell
cd C:\Projetos
mkdir radar-vagas-discord
cd radar-vagas-discord
```

Caso a pasta `C:\Projetos` não exista, escolha outro diretório.

### Passo 2 — Inicializar o Git

```powershell
git init
git branch -M main
```

### Passo 3 — Copiar o contexto

Copie para a raiz do projeto:

```text
CONTEXTO_RADAR_VAGAS_DISCORD.md
GUIA_CODEX_RADAR_VAGAS_DISCORD.md
```

### Passo 4 — Abrir no VS Code

```powershell
code .
```

### Passo 5 — Abrir o Codex

No terminal da raiz:

```powershell
codex
```

No Codex, execute:

```text
/init
```

Revise o `AGENTS.md` gerado. Ele deverá reforçar:

- leitura obrigatória do contexto;
- Python 3.12;
- testes;
- tipagem;
- segurança de segredos;
- execução de `ruff` e `pytest`;
- alterações pequenas e verificáveis.

---

## 6. Prompt 1 — Inicialização do projeto

Copie o arquivo de contexto para a raiz antes de executar este prompt.

```text
Leia integralmente o arquivo CONTEXTO_RADAR_VAGAS_DISCORD.md e trate-o como a especificação principal do projeto.

Inicialize a estrutura do projeto Python descrita no documento, sem implementar ainda as integrações reais com APIs.

Nesta etapa:

1. crie o pyproject.toml para Python 3.12;
2. configure o pacote src/radar_vagas;
3. adicione as dependências de produção e desenvolvimento descritas no contexto, incluindo python-docx;
4. crie .gitignore e .env.example sem valores reais;
5. crie config/profile.yaml com os filtros e competências definidos no contexto;
6. crie config/candidate_profile.example.yaml somente com dados fictícios;
7. inclua candidate_profile.local.yaml e output/resumes no .gitignore;
8. crie os módulos de providers, resumes e notifications descritos na estrutura;
9. configure Ruff e Pytest;
10. crie um README inicial com os comandos de instalação;
11. atualize ou crie AGENTS.md com instruções específicas deste repositório;
12. não crie nem solicite credenciais reais;
13. não implemente ainda a geração de currículos.

Depois:
- instale as dependências no ambiente disponível;
- execute ruff check;
- execute pytest;
- corrija qualquer erro;
- apresente um resumo dos arquivos criados e os comandos que devo executar no Windows.
```

### Validação manual

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
ruff check .
pytest
```

Faça um commit:

```powershell
git add .
git commit -m "chore: initialize radar project"
```

---

## 7. Prompt 2 — Configuração e modelos

```text
Leia CONTEXTO_RADAR_VAGAS_DISCORD.md, AGENTS.md e o código existente.

Implemente a camada de configuração e os modelos de domínio.

Escopo:

1. implemente src/radar_vagas/config.py;
2. carregue variáveis de ambiente com pydantic-settings;
3. carregue config/profile.yaml com validação;
4. implemente os modelos JobPosting, EvaluatedJob e ResumeArtifact em models.py;
5. implemente modelos para o perfil-base, experiências, bullets, projetos, formação e destaques;
6. normalize datas para UTC;
7. crie enums ou Literal para prioridade, status, modalidade e senioridade quando fizer sentido;
8. crie erros de configuração claros, sem revelar segredos ou dados pessoais;
9. valide que minimum_score esteja entre 0 e 100;
10. valide que exista pelo menos um termo e uma localização;
11. valide IDs únicos no perfil-base;
12. valide que Administração esteja marcada como curso interrompido;
13. escreva testes unitários para configurações válidas e inválidas.

Não implemente provedores ou Discord nesta etapa.

Execute ruff e pytest, corrija falhas e mostre o resumo das mudanças.
```

Commit:

```powershell
git add .
git commit -m "feat: add configuration and domain models"
```

---

## 8. Prompt 3 — Utilitários de texto e deduplicação

```text
Leia a especificação e o código atual.

Implemente os utilitários de normalização e deduplicação.

Requisitos:

1. normalização Unicode e remoção segura de acentos para comparação;
2. lower case e espaços normalizados;
3. remoção de parâmetros de rastreamento das URLs;
4. preservação dos parâmetros funcionais necessários;
5. criação de fingerprint SHA-256 com título, empresa e localização;
6. ordem de deduplicação:
   a. provider + provider_job_id;
   b. URL normalizada;
   c. fingerprint;
7. não considerar pequenas diferenças de caixa ou acentuação como vagas distintas;
8. não juntar vagas de empresas diferentes;
9. criar testes abrangentes com URLs e títulos em português;
10. documentar decisões importantes.

Execute ruff e pytest e corrija qualquer problema.
```

Commit:

```powershell
git add .
git commit -m "feat: add job normalization and deduplication"
```

---

## 9. Prompt 4 — Scoring e filtros

```text
Leia CONTEXTO_RADAR_VAGAS_DISCORD.md e implemente a camada de filtros e scoring determinístico.

Requisitos:

1. score total de 0 a 100;
2. pesos:
   - cargo: 25;
   - competências: 35;
   - senioridade: 15;
   - localização/modalidade: 15;
   - atualidade: 10;
3. pesos e termos devem vir da configuração quando possível;
4. rejeitar senioridade sênior ou liderança;
5. rejeitar presencial fora de Curitiba e região metropolitana;
6. aceitar remoto disponível para o Brasil;
7. detectar competências no título e na descrição;
8. separar matched_skills e missing_skills;
9. gerar rejection_reasons;
10. gerar uma explicação curta e auditável;
11. limitar score entre 0 e 100;
12. não utilizar API de IA;
13. lidar com descrição ou data ausente;
14. criar testes parametrizados para, no mínimo:
    - vaga júnior altamente aderente;
    - vaga pleno parcialmente aderente;
    - vaga sênior;
    - vaga presencial fora da região;
    - vaga remota Brasil;
    - vaga sem descrição;
    - vaga antiga;
    - vaga com score abaixo de 70.

Execute ruff e pytest com cobertura para os módulos implementados.
```

Commit:

```powershell
git add .
git commit -m "feat: implement deterministic job scoring"
```

---

## 10. Prompt 5 — Persistência do histórico

```text
Implemente a persistência em data/seen_jobs.json conforme a especificação.

Requisitos:

1. criar a estrutura automaticamente quando o arquivo não existir;
2. escrita atômica usando arquivo temporário e replace;
3. detectar JSON inválido e criar backup antes de recuperar;
4. registrar first_seen_at, last_seen_at, status, score e notified_at;
5. suportar status rejected, eligible, notified e notification_failed;
6. consultar se provider_job_id, URL ou fingerprint já existem;
7. podar registros com mais de 180 dias;
8. não salvar alterações em dry-run;
9. permitir injeção do caminho do arquivo nos testes;
10. criar testes para:
    - arquivo inexistente;
    - gravação e releitura;
    - duplicidade;
    - JSON corrompido;
    - escrita atômica;
    - dry-run;
    - poda.

Não implemente ainda o GitHub Actions.

Execute ruff e pytest.
```

Commit:

```powershell
git add .
git commit -m "feat: add persistent job history"
```

---

## 11. Prompt 6 — Provider Jooble

```text
Implemente o provider da Jooble com base na documentação oficial e na interface de provider definida no projeto.

Requisitos:

1. usar HTTP POST para o endpoint da Jooble;
2. obter a chave exclusivamente de JOOBLE_API_KEY;
3. receber termo, localização, página e quantidade por página;
4. configurar timeout;
5. usar retry com backoff para 429 e erros 5xx;
6. não repetir 400, 401, 403 ou 404;
7. normalizar todos os resultados para JobPosting;
8. preservar provider_job_id;
9. mapear title, company, location, snippet, salary, type, link e updated;
10. registrar contagens, sem registrar a chave;
11. criar respostas simuladas com respx;
12. testar sucesso, resposta vazia, timeout, 403, 429 e payload incompleto;
13. não fazer chamadas reais nos testes.

Adicione uma opção de linha de comando provisória ou pequeno script de diagnóstico que permita testar a consulta em modo dry-run, sem Discord.

Execute ruff e pytest.
```

### Teste local

Preencha temporariamente o `.env`:

```dotenv
JOOBLE_API_KEY=SUA_CHAVE
DISCORD_WEBHOOK_URL=
LOG_LEVEL=INFO
ENVIRONMENT=development
```

Execute:

```powershell
python -m radar_vagas --provider jooble --dry-run
```

Nunca faça commit do `.env`.

Commit:

```powershell
git add .
git commit -m "feat: add Jooble job provider"
```

---

## 12. Prompt 7 — Provider Remotive

```text
Implemente o provider da Remotive para vagas remotas.

Requisitos:

1. usar a API pública documentada pela Remotive;
2. normalizar os resultados para JobPosting;
3. manter o link original;
4. definir source_name como Remotive;
5. permitir filtro por termo ou categoria quando suportado;
6. considerar que a vaga é remota, mas não assumir elegibilidade para o Brasil sem analisar a localização/candidate_required_location;
7. rejeitar ou reduzir score quando a vaga for restrita a países incompatíveis;
8. configurar timeout e retry para falhas transitórias;
9. respeitar os termos de atribuição;
10. criar testes com respx;
11. não fazer chamadas reais nos testes;
12. incluir a fonte Remotive no embed futuro.

Execute ruff e pytest.
```

Commit:

```powershell
git add .
git commit -m "feat: add Remotive job provider"
```

---


## 13. Prompt 8 — Perfil profissional e geração de currículos

Antes deste prompt, crie localmente `config/candidate_profile.local.yaml` e revise todo o conteúdo.

```text
Leia CONTEXTO_RADAR_VAGAS_DISCORD.md, AGENTS.md e o código atual.

Implemente a geração determinística de currículos otimizados em DOCX.

Escopo:

1. implemente resumes/profile.py para carregar e validar o perfil-base;
2. implemente resumes/keyword_extractor.py para extrair do título e descrição:
   - cargo-alvo;
   - competências;
   - ferramentas;
   - responsabilidades;
   - domínio;
   - senioridade;
   - palavras-chave ATS;
3. implemente aliases configuráveis, incluindo Power BI, PowerBI, DAX, Power Query, M, SQL, Python, pandas, ETL e pipelines;
4. implemente resumes/content_selector.py;
5. selecione somente conteúdo existente no perfil-base;
6. ordene competências pelo grau de aderência;
7. selecione os bullets de experiência mais relevantes;
8. selecione entre dois e três projetos aderentes;
9. não apresente missing_skills como competências;
10. gere um resumo com blocos aprovados, sem inventar frases factuais;
11. implemente resumes/generator.py com python-docx;
12. gere documento linear e compatível com ATS:
    - sem tabelas;
    - sem colunas;
    - sem imagens;
    - sem ícones;
    - sem cabeçalhos flutuantes;
    - fonte comum;
    - títulos claros;
    - bullets simples;
13. use a estrutura:
    - cabeçalho;
    - Resumo Profissional;
    - Competências Técnicas;
    - Experiência Profissional;
    - Projetos Selecionados;
    - Formação e Destaques;
    - Experiência Adicional quando relevante;
14. obtenha telefone e e-mail das variáveis CANDIDATE_PHONE e CANDIDATE_EMAIL;
15. use o título da vaga como cargo-alvo;
16. mantenha Administração como curso interrompido;
17. sanitize empresa e cargo para o nome do arquivo;
18. use o padrão Curriculo_Renan_Dobriansky_<Empresa>_<Cargo>.docx;
19. implemente resumes/validator.py;
20. valide seções obrigatórias, placeholders, arquivo corrompido e afirmações proibidas;
21. retorne ResumeArtifact;
22. escreva testes para:
    - seleção de skills;
    - seleção de bullets;
    - seleção de projetos;
    - vaga financeira;
    - vaga de BI;
    - vaga de engenharia de dados;
    - lacuna não incluída;
    - curso interrompido;
    - nome de arquivo com caracteres especiais;
    - documento que pode ser aberto novamente pelo python-docx;
    - perfil inválido;
23. adicione o comando:
    python -m radar_vagas --generate-resume tests/fixtures/jobs/bi_job.json
24. adicione:
    python -m radar_vagas --dry-run --save-resumes

Não integre com o Discord nesta etapa.

Execute ruff e pytest. Gere um DOCX de exemplo com dados fictícios e informe o caminho para inspeção.
```

### Validação manual

```powershell
python -m radar_vagas --generate-resume tests\fixtures\jobs\bi_job.json
python -m radar_vagas --dry-run --save-resumes --verbose
```

Abra manualmente o DOCX e confirme:

- cargo-alvo correto;
- conteúdo verdadeiro;
- leitura simples;
- ausência de tabelas e colunas;
- nome do arquivo correto;
- Administração identificada como curso interrompido.

Commit:

```powershell
git add .
git commit -m "feat: generate tailored ATS resumes"
```

---

## 14. Prompt 9 — Notificação no Discord

```text
Implemente notifications/discord.py usando webhook do Discord e anexos.

Requisitos:

1. obter a URL somente de DISCORD_WEBHOOK_URL;
2. usar POST multipart com wait=true;
3. enviar payload_json com embed;
4. anexar o currículo com files[0];
5. enviar uma vaga e um currículo por mensagem;
6. usar allowed_mentions com parse vazio;
7. não imprimir ou retornar a URL do webhook;
8. título clicável com a URL original da vaga;
9. incluir cargo, empresa, localização, score, prioridade, matched_skills, missing_skills, data e fonte;
10. informar no embed que o currículo foi otimizado para a vaga;
11. não exibir telefone ou e-mail no corpo da mensagem;
12. validar existência, extensão e tamanho do DOCX antes do envio;
13. truncar campos para respeitar limites do Discord;
14. configurar timeout;
15. tratar respostas 2xx como sucesso;
16. tratar 429 de acordo com retry_after quando disponível;
17. aplicar retry somente em erros transitórios;
18. não recriar o currículo em cada tentativa de retry;
19. criar uma função send_test_message que anexe um DOCX fictício;
20. criar testes com respx para:
    - sucesso com anexo;
    - arquivo inexistente;
    - arquivo inválido;
    - 400;
    - 429;
    - timeout;
    - ausência de configuração;
21. não fazer requisições reais nos testes.

Implemente o comando:

python -m radar_vagas --test-discord

Execute ruff e pytest.
```

### Teste local

No `.env`:

```dotenv
DISCORD_WEBHOOK_URL=URL_COPIADA_DO_DISCORD
JOOBLE_API_KEY=SUA_CHAVE
CANDIDATE_EMAIL=SEU_EMAIL
CANDIDATE_PHONE=SEU_TELEFONE
CANDIDATE_PROFILE_PATH=config/candidate_profile.local.yaml
```

Execute:

```powershell
python -m radar_vagas --test-discord
```

Confirme visualmente no canal `#novas-vagas`:

- embed recebido;
- DOCX fictício anexado;
- nenhuma credencial exposta.

Commit:

```powershell
git add .
git commit -m "feat: send tailored resumes to Discord"
```

---

## 15. Prompt 10 — Pipeline e CLI

```text
Integre todos os componentes no pipeline principal e na CLI.

Fluxo obrigatório:

1. carregar configuração;
2. executar cada provider habilitado;
3. continuar se uma fonte falhar;
4. normalizar;
5. deduplicar resultados da execução;
6. ignorar vagas já presentes no histórico;
7. aplicar filtros e scoring;
8. ordenar elegíveis por score decrescente;
9. limitar vagas ao máximo configurado;
10. extrair palavras-chave de cada vaga selecionada;
11. selecionar conteúdo verdadeiro do perfil-base;
12. gerar e validar um currículo DOCX por vaga;
13. enviar cada vaga ao Discord com seu currículo anexado;
14. atualizar status da vaga e do currículo no histórico;
15. remover arquivos temporários quando configurado;
16. persistir o estado de forma atômica;
17. exibir resumo final nos logs.

Implemente opções:

- --dry-run
- --test-discord
- --provider jooble
- --provider remotive
- --minimum-score
- --max-jobs
- --save-resumes
- --generate-resume CAMINHO_JSON
- --verbose

O dry-run não deve enviar mensagens nem modificar o histórico. Sem `--save-resumes`, os arquivos temporários devem ser removidos.

Crie testes de integração do pipeline com providers, gerador de currículos, storage e Discord simulados. Teste também:

- falha parcial de uma fonte;
- falha ao carregar o perfil;
- falha na geração de um currículo;
- currículo inválido;
- falha de notificação;
- múltiplas vagas com currículos diferentes;
- execução repetida sem duplicidade.

Atualize o README com os comandos.

Execute ruff e pytest.
```

### Teste local completo

```powershell
python -m radar_vagas --dry-run --save-resumes --verbose
python -m radar_vagas
```

Abra os DOCX do dry-run para revisão. Depois execute normalmente e repita a execução: nenhuma vaga já enviada deve ser notificada ou gerar novo currículo.

Commit:

```powershell
git add .
git commit -m "feat: integrate radar pipeline and CLI"
```

---

## 16. Prompt 11 — GitHub Actions

```text
Crie .github/workflows/radar.yml para executar o radar na nuvem.

Requisitos:

1. workflow_dispatch para execução manual;
2. schedule de segunda a sexta às 08:00 e 14:00;
3. timezone America/Sao_Paulo;
4. Python 3.12;
5. cache de dependências quando apropriado;
6. instalação do pacote com dependências de desenvolvimento;
7. execução de ruff check;
8. execução de pytest;
9. execução de python -m radar_vagas;
10. segredos DISCORD_WEBHOOK_URL, JOOBLE_API_KEY, CANDIDATE_EMAIL e CANDIDATE_PHONE;
11. disponibilizar o perfil real ao runner de forma segura;
12. gerar currículos em diretório temporário;
13. anexar os currículos ao Discord;
14. limpar os DOCX após o envio;
15. nunca fazer commit de output/resumes;
16. permission contents: write;
17. concurrency para impedir execuções simultâneas;
18. commit de data/seen_jobs.json apenas quando houver alteração;
19. mensagem de commit com [skip ci];
20. pull --rebase antes do push para reduzir conflitos;
21. não imprimir secrets nem dados de contato;
22. falhar claramente se uma credencial obrigatória estiver ausente;
23. opcionalmente publicar os DOCX como artifact somente no workflow_dispatch e com retenção curta;
24. atualizar o README com a configuração dos GitHub Secrets, perfil-base e teste manual.

Revise a sintaxe YAML e explique como validar a primeira execução manual.
```

Commit:

```powershell
git add .
git commit -m "ci: schedule job radar workflow"
```

---

## 17. Criar o repositório no GitHub

Recomenda-se um repositório privado.

### Com GitHub CLI

```powershell
gh repo create radar-vagas-discord --private --source=. --remote=origin --push
```

### Sem GitHub CLI

1. Crie um repositório privado no GitHub.
2. Não adicione README ou `.gitignore` pelo site, pois eles já existem localmente.
3. Execute os comandos exibidos pelo GitHub, normalmente:

```powershell
git remote add origin URL_DO_REPOSITORIO
git push -u origin main
```

---

## 18. Configurar os GitHub Secrets

No repositório:

1. Abra `Settings`.
2. Entre em `Secrets and variables`.
3. Abra `Actions`.
4. Clique em `New repository secret`.

Crie:

```text
DISCORD_WEBHOOK_URL
JOOBLE_API_KEY
CANDIDATE_EMAIL
CANDIDATE_PHONE
```

Não use GitHub Variables para essas credenciais.

---

## 19. Testar o GitHub Actions

1. Abra a aba `Actions`.
2. Selecione o workflow do radar.
3. Clique em `Run workflow`.
4. Acompanhe os logs.
5. Confirme:
   - lint aprovado;
   - testes aprovados;
   - providers executados;
   - mensagem recebida no Discord;
   - `data/seen_jobs.json` atualizado;
   - commit automático criado somente quando necessário.

Execute manualmente outra vez para verificar a deduplicação.

---

## 20. Prompt 12 — Revisão de segurança e qualidade

```text
Faça uma revisão final completa do projeto com foco em segurança, confiabilidade e manutenção.

Leia CONTEXTO_RADAR_VAGAS_DISCORD.md e AGENTS.md.

Verifique:

1. segredos não versionados;
2. logs sem credenciais;
3. ausência de URLs reais de webhook;
4. timeouts em todas as chamadas HTTP;
5. retry apenas em erros transitórios;
6. tratamento correto de 429;
7. escrita atômica do estado;
8. deduplicação;
9. comportamento do dry-run;
10. limites dos embeds do Discord;
11. datas e timezone;
12. workflow agendado;
13. tipagem;
14. cobertura das regras críticas;
15. documentação do setup no Windows e GitHub;
16. dependências desnecessárias ou vulneráveis;
17. código morto ou duplicado;
18. perfil-base não versionado;
19. currículos não versionados;
20. nenhuma afirmação não comprovada;
21. Administração registrada como curso interrompido;
22. currículo linear e ATS;
23. anexos associados à vaga correta;
24. arquivos temporários removidos;
25. dados de contato ausentes dos logs.

Execute:
- ruff check;
- pytest com cobertura;
- qualquer verificação adicional segura disponível.

Corrija os problemas encontrados, sem alterar o escopo funcional. Ao final, apresente:
- problemas encontrados;
- correções realizadas;
- riscos remanescentes;
- comandos de validação.
```

Commit:

```powershell
git add .
git commit -m "chore: harden radar security and reliability"
git push
```

---

## 21. Comandos principais depois de pronto

### Ativar o ambiente

```powershell
cd C:\Projetos\radar-vagas-discord
.\.venv\Scripts\Activate.ps1
```

### Testar Discord

```powershell
python -m radar_vagas --test-discord
```

### Simular busca

```powershell
python -m radar_vagas --dry-run --verbose
```

### Gerar currículos para revisão sem enviar

```powershell
python -m radar_vagas --dry-run --save-resumes --verbose
```

### Gerar currículo para uma vaga em JSON

```powershell
python -m radar_vagas --generate-resume caminhoaga.json
```

### Executar normalmente

```powershell
python -m radar_vagas
```

### Rodar testes

```powershell
ruff check .
pytest
```

---

## 22. Diagnóstico de problemas comuns

### Erro: webhook ausente

Verifique:

```powershell
Get-Content .env
```

Confirme que existe:

```dotenv
DISCORD_WEBHOOK_URL=...
```

Não compartilhe a saída.

### Erro 401 ou 403 na Jooble

- confira a chave;
- confirme se a chave está ativa;
- evite espaços no início ou fim;
- confirme que o secret do GitHub tem o mesmo nome esperado.

### Erro 404 no webhook

O webhook pode ter sido apagado ou recriado.

- crie outro webhook;
- atualize `.env`;
- atualize o GitHub Secret.

### Vagas repetidas

Verifique:

- normalização da URL;
- provider_job_id;
- fingerprint;
- persistência do `seen_jobs.json`;
- commit do estado no GitHub Actions.

### Nenhuma vaga encontrada

Teste individualmente:

```powershell
python -m radar_vagas --provider jooble --dry-run --verbose
python -m radar_vagas --provider remotive --dry-run --verbose
```

Revise os termos e localizações em `config/profile.yaml`.

### Muitas vagas irrelevantes

- aumente `minimum_score`;
- ajuste títulos prioritários;
- adicione termos de exclusão;
- reduza o peso de competências genéricas;
- revise a regra de localização.


### Currículo não foi gerado

Verifique:

- `CANDIDATE_PROFILE_PATH`;
- existência do perfil local;
- `CANDIDATE_EMAIL`;
- `CANDIDATE_PHONE`;
- IDs duplicados;
- placeholders;
- erros de validação exibidos nos logs.

Teste isoladamente:

```powershell
python -m radar_vagas --generate-resume tests\fixtures\jobs\bi_job.json
```

### Currículo contém conteúdo incorreto

- interrompa a automação;
- corrija o `candidate_profile.local.yaml`;
- verifique tags e aliases;
- adicione a afirmação incorreta em `forbidden_claims`;
- crie um teste de regressão antes de reativar.

### Currículo não apareceu no Discord

- confirme que o arquivo existe antes do POST;
- verifique extensão DOCX;
- verifique o envio multipart;
- confira se `payload_json` e `files[0]` foram montados corretamente;
- revise a resposta do Discord sem expor o webhook.

### Arquivos pessoais apareceram no Git

Execute:

```powershell
git status
git check-ignore -v config\candidate_profile.local.yaml
git check-ignore -v output\resumes\arquivo.docx
```

Caso algum dado já tenha sido commitado, remova-o do histórico e revogue credenciais expostas.

### GitHub Actions não executou no horário

- confirme que o workflow está no branch padrão;
- confirme que o repositório e o workflow estão ativos;
- revise a sintaxe do `schedule`;
- use `Run workflow` para validar manualmente;
- verifique se o fuso está como `America/Sao_Paulo`.

---

## 23. Checklist final

### Discord

- [ ] Servidor criado
- [ ] Canal `#novas-vagas` criado
- [ ] Webhook criado
- [ ] Webhook armazenado com segurança
- [ ] Mensagem de teste recebida

### APIs

- [ ] Chave da Jooble criada
- [ ] Consulta Jooble funcionando
- [ ] Consulta Remotive funcionando
- [ ] Fontes exibidas nas mensagens

### Currículos

- [ ] Perfil-base real revisado
- [ ] Perfil-base real ignorado pelo Git
- [ ] Telefone e e-mail em variáveis protegidas
- [ ] Extração de palavras-chave funcionando
- [ ] Seleção de competências verdadeira
- [ ] Seleção de experiências e projetos funcionando
- [ ] DOCX ATS gerado
- [ ] Administração marcada como curso interrompido
- [ ] Lacunas não incluídas como competências
- [ ] Nome do arquivo correto
- [ ] Currículo anexado à vaga correta
- [ ] Pasta de saída ignorada pelo Git

### Código

- [ ] Configuração YAML funcionando
- [ ] Score implementado
- [ ] Filtros implementados
- [ ] Deduplicação implementada
- [ ] Estado persistente
- [ ] Dry-run funcionando
- [ ] Dry-run com save-resumes funcionando
- [ ] Geração manual por JSON funcionando
- [ ] Testes de currículo passando
- [ ] Testes passando
- [ ] Ruff passando

### GitHub

- [ ] Repositório privado
- [ ] Secrets de API e contato configurados
- [ ] Perfil-base disponibilizado com segurança
- [ ] Workflow manual funcionando
- [ ] Agendamento configurado
- [ ] Estado persistido entre execuções
- [ ] Nenhum segredo no histórico Git

---

## 24. Próxima fase recomendada

Depois de uma ou duas semanas de uso:

1. exportar o histórico das vagas;
2. avaliar falsos positivos e falsos negativos;
3. ajustar os pesos do score;
4. criar o canal `#alta-prioridade`;
5. revisar quais bullets e projetos foram mais selecionados;
6. ajustar tags, aliases e resumos aprovados;
7. integrar a planilha Controle de Candidaturas;
8. adicionar empresas-alvo;
9. criar um resumo diário ou semanal;
10. avaliar geração opcional de PDF;
11. avaliar versão em inglês;
12. avaliar uso opcional de LLM com validação estrita contra o perfil-base.

Não adicione automação de candidatura nem redação livre por IA antes de validar a qualidade e a veracidade dos currículos gerados.
