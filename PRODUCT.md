# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- Master/Admin (coordenação e apoio operacional): consolidam, aprovam, devolvem,
  fecham períodos, importam financeiro e conferem auditoria. São o perfil com
  melhor experiência de uso (modo Operate).
- PontoFocal: lança indicadores mensais dos pilares aos quais foi vinculado
  (rascunho ou envio para validação).
- Liderança: visualiza dashboards e relatório mensal, sem edição.
- Auditor: consulta histórico de alterações, sem edição.

## Product Purpose

Portal local de gestão e prestação de contas mensal do Programa QuIIN: coletar
indicadores por pilar, comparar meta × realizado × percentual, aprovar
lançamentos, fechar períodos com snapshot, importar financeiro consolidado via
CSV e gerar relatório mensal HTML imprimível para a reunião com a Embrapii.

## Positioning

Protótipo funcional que substitui a consolidação manual de planilhas por um
fluxo mensal rastreável (quem lançou, quem aprovou, quando), com visão
consolidada e segregada por pilar, rodando apenas localmente.

## Operating Context

- Ciclo mensal: a reunião com a Embrapii ocorre após o dia 15 e apresenta o
  mês de competência anterior (RN-001).
- Pilares: PDI/FCCT, Formação, Startups, Associação Tecnológica, Infraestrutura,
  Financeiro/Outras Fontes.
- Execução financeira = valor efetivamente gasto/comprovado; captação ≠ execução.
- Renovações não contam para a meta de CNPJs novos.
- Ambiente: Django 5.2 + SQLite, executado via `runserver`; interface via
  Django Templates + CSS local, sem build frontend e sem CDN.

## Capabilities and Constraints

- Login local com perfis Master, Admin, PontoFocal, Lideranca, Auditor.
- Pilares, indicadores (QTD/MON/PER/TXT), metas (MENSAL/ANUAL/ACUMULADA), períodos
  com status Planejado/Aberto/Fechado/Reaberto.
- Lançamentos com fluxo Rascunho → Enviado → Aprovado/Devolvido; duplicidade
  impedida; período fechado bloqueia edição.
- Importação CSV atômica de financeiro consolidado (layout fixo de colunas).
- Auditoria de ações relevantes.
- Restrições: sem cloud, Docker, PostgreSQL, filas, SSO, APIs externas, e-mail;
  sem dados reais/sensíveis (apenas fictícios e consolidados).

## Brand Commitments

- Identidade visual QuIIN definida: paleta oficial (navy `#04047E`, deep-purple
  `#1B1641`, royal `#0F3B94`, blue `#144FAD`, sky `#1D72B9`, quantum-green
  `#2EBF7D`, violet `#3B249C`, mist `#DEDFE8`), com tokens semânticos por
  status e por pilar.
- Tipografia: Panton (headlines; arquivos trial para uso interno/local —
  substituir por licença comercial antes de publicar), Myriad Pro (corpo),
  JetBrains Mono (dados numéricos).
- Design system interno em `templates/components/` com catálogo em
  `/dev/design-system/` (somente DEBUG).
- `relatorio.html` continua sem valor de referência visual.

## Evidence on Hand

- `relatorio.html`: contexto textual de engenharia e requisitos (não é template).
- `docs/`: SDD, requisitos (RF/RNF/RN/US/AC), modelo de dados, loops, decisões.
- `data/seed/financeiro_demo.csv`: layout de importação financeira.
- Base demo via `python manage.py seed_demo` (8 usuários, 6 pilares, 22 indicadores).

## Product Principles

1. Preferir clareza à sofisticação — interface simples, escaneável e sem dependências.
2. Validação no backend (views/serviços), nunca apenas no template.
3. Rastreabilidade total: toda ação relevante gera auditoria.
4. Execução local simples e evolutiva por domínio (apps).
5. Permissões rígidas por papel e pilar (RN-012).

## Accessibility & Inclusion

Interface responsiva (desktop e viewport móvel), formulários com labels
explícitas, foco visível e suporte a impressão do relatório mensal.
