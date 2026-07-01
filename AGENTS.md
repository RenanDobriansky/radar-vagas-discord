# AGENTS

## Regras deste repositorio

- Leia `CONTEXTO_RADAR_VAGAS_DISCORD.md`, `GUIA_CODEX_RADAR_VAGAS_DISCORD.md` e `PLANO_REAJUSTE_RADAR_VAGAS_CODEX.md` antes de alterar funcionalidades relevantes.
- Use Python 3.12 ou superior.
- Priorize alteracoes pequenas, verificaveis e com escopo bem definido.
- Mantenha tipagem consistente e modulos com responsabilidade clara.
- Sempre rode `ruff check .` e `pytest` ao finalizar cada etapa implementada.
- Atualize documentacao em `README.md` e `docs/` quando mudar arquitetura, estado operacional, workflows ou comportamento da CLI.
- Nunca solicite nem grave credenciais reais no repositorio.
- Nunca exponha webhooks, chaves de API, telefone, email ou perfil profissional real em logs, fixtures ou docs.
- O perfil profissional real deve ficar somente em `config/candidate_profile.local.yaml`, fora do versionamento.
- Nao invente experiencias, competencias, certificacoes ou resultados profissionais.
- Preserve a compatibilidade dos comandos documentados, salvo quando a mudanca exigir atualizacao explicita da documentacao.
- Trate `data/seen_jobs.json` como estado operacional, nao como codigo de produto.
