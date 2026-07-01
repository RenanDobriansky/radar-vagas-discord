# Seguranca e Privacidade

## Principios

O projeto foi estruturado para reduzir exposicao de segredos, dados pessoais e artefatos sensiveis durante a execucao local e no GitHub Actions.

## Segredos

Segredos obrigatorios de producao:

- `DISCORD_WEBHOOK_URL`
- `JOOBLE_API_KEY`
- `CANDIDATE_EMAIL`
- `CANDIDATE_PHONE`
- `CANDIDATE_PROFILE_YAML`

Regras:

- nao versionar `.env`;
- nao copiar secrets para fixtures ou docs;
- nao deixar secrets no escopo completo do workflow produtivo;
- injetar secrets somente nos passos que realmente precisam deles.

## Perfil profissional real

O perfil profissional real deve existir apenas em:

- `config/candidate_profile.local.yaml`

Esse arquivo:

- nao deve ser versionado;
- nao deve aparecer em screenshots, logs ou exemplos;
- e recriado no runner apenas durante a execucao produtiva.

## Historico operacional

O historico `v3` minimiza dados persistidos:

- usa hash da URL normalizada em vez de armazenar a URL normalizada em texto;
- nao persiste descricao completa;
- nao persiste salario;
- mantem apenas snapshot minimo para auditoria e retry;
- mantem dados necessarios para status, retries e deduplicacao.

## GitHub Actions

### CI

- `contents: read`
- sem secrets produtivos
- roda apenas validacao

### Workflow produtivo

- nivel do workflow com `contents: read`
- job produtivo com `contents: write` somente porque precisa atualizar o estado operacional
- estado salvo em branch dedicada `radar-state`
- commits operacionais usam `[skip ci]`

## Artifacts

O workflow produtivo:

- nao publica curriculos reais;
- pode publicar apenas relatorio sanitizado em execucao manual;
- remove arquivos sensiveis ao final da execucao.

## Logs

Os logs nao devem expor:

- webhook completo;
- chave da Jooble;
- email;
- telefone;
- conteudo integral do perfil profissional real.

## Riscos conhecidos

- providers externos podem retornar vagas muito fora do escopo;
- resultados remotos podem mudar sem aviso;
- uma configuracao local incorreta ainda pode gerar ruido operacional, mesmo sem vazar segredos.
