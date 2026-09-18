# L14 — Sidebar com AT em Pilares (evidência)

Data: 2026-09-17 · TDD: testes de navegação atualizados antes.

## Entregas
- `PILARES_COM_PAINEL = (PDI, FORMACAO, STARTUPS, AT, INFRA)` em
  `planning/services.py`; `context_processors` usa a constante (ordem do pilar).
- Sidebar: AT em `#grp-pilares` (link `core:pilar`, rótulo com "(AT)");
  Gestão com **Funil AT** (mesma URL/gate do CRM).
- Correção de navegação: `_hx_parcial()` — fragmento só em swap de filtro;
  navegação com boost (`HX-Boosted`) recebe página completa, senão o OOB
  atualizava header/URL mas o `#main` jamais trocava (bug real pego pelo P07).

## Verificação
- Django `apps.core` 73/73 (Pilares com os 5; auditor só Auditoria em Gestão).
- e2e pilar_anual + dashboard_anual + shell verdes (P07 navega sidebar→AT;
  teste L9 atualizado; teste do banner legado reescrito).
- Evidência visual: `sidebar-at-pilares.png`.
