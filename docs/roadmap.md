# Roadmap

## Objetivo

Este roadmap resume as proximas evolucoes esperadas para o Radar de Vagas sem comprometer o escopo atual deterministico e auditavel.

## Curto prazo

- reduzir ruido de providers com filtros semanticos melhores antes do scoring completo;
- ampliar os diagnosticos da fila, retries e dead letter para facilitar suporte operacional;
- refinar continuamente aliases, pesos e taxonomias de competencias;
- melhorar a documentacao com mais exemplos sanitizados de execucao real.

## Medio prazo

- criar comandos de inspecao do estado operacional sem editar manualmente `seen_jobs.json`;
- adicionar relatorios resumidos de execucao para auditoria local e no GitHub Actions;
- fortalecer testes de regressao sobre curriculos e classificacao de vagas;
- revisar periodicamente dependencias e versoes das actions usadas nos workflows.

## Longo prazo

- avaliar novos providers desde que mantenham isolamento de falhas e contratos claros;
- estudar formas de reduzir ainda mais o armazenamento operacional sem perder auditoria;
- evoluir observabilidade da branch `radar-state`;
- organizar exemplos ficticios de ponta a ponta para demonstracao de portfolio.

## Fora do escopo atual

- uso de IA generativa para scoring;
- reescrita livre de conteudo profissional;
- armazenamento externo complexo para estado operacional;
- publicacao de dados pessoais, curriculos reais ou artifacts sensiveis.
