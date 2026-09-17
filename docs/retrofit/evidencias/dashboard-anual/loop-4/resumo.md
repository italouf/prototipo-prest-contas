# L4 — Sidebar e navegação (evidência)

Data: 2026-09-17 · Commit: `feat(nav)` (LOOP 4)

## Entregas
- Sidebar reescrita (fundo claro, tokens): Geral; grupo Pilares
  (PDI, Formação FCRH, ACS, Infraestrutura + Associação Tecnológica→CRM);
  Talentos; grupo Prestação de contas (Mensal/Semestral); Relatórios;
  grupos Operação e Gestão por papel. OUTRASFONTES segue via URL/mensal.
- Grupos colapsáveis: `aria-expanded`, `hidden` acessível, persistência em
  `localStorage['quiin-nav-grupos']` (aberto por padrão; grupo do item ativo
  sempre abre); chevron gira via CSS; `nav-ativo` + `aria-current` (server + JS).
- `/prestacao/semestral/`: ano + 2 semestres com períodos/status e links p/ mensal.
- Pilar aceita `?ano&base` válidos e exibe banner `contexto-anual` c/ volta ao painel.
- `rotulo_painel` filter + `pilares_grupo` no context processor.

## Verificação
- Django `apps.core` → 64/64 OK (7 novos: sidebar, semestral, pilar).
- e2e shell + a11y → 21/21 (4 testes novos/ajustados: grupos+persistem,
  mensal/semestral, pilar→painel; loop de 5 páginas intacto).
- DoD L4: navegação completa sem regressão ✅; axe sem novos achados ✅.
- Evidência visual: `sidebar-painel.png`, `semestral.png`, `pilar-contexto-anual.png`.
