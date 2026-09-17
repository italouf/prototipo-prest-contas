# L8 — Regressão final e polish (evidência)

Data: 2026-09-17 · Commit: `test(...)` (LOOP 8)

## Verificação
- Django: **240/240 OK** (190 base + 50 novos: planning 32, painel_anual 12,
  navegação 7, ajustes mensais/highlights/entries).
- e2e: **93/93** (62 base + 31 novos: anual 28 com paridade L0 nos 10 estados,
  shell 3 de navegação; demais re-apontadas sem mudar asserções).
- axe-core: 12/12 rotas + T17 (3 estados do painel) sem critical/serious.
- Queries: render `/` em **9** (teto de teste: 20); `painel()` em 1.
- Impressão: T13 + `impressao-a4.png` (cabeçalho de filtros, sem controles).
- Responsivo: teste 390px sem overflow + `mobile-390.png`; off-canvas OK.
- Catálogo `/dev/design-system/`: seção "Painel anual" (farol ×4, kpi, chart).
- Console/pageerror: teste dedicado sem erros ao filtrar.
- `manage.py check` limpo; `tailwind build --force` + `collectstatic` aplicados.

## Correções no loop
- Highlights/entries/cards mensais re-apontados p/ `core:mensal` (3 arquivos).
- `docs/decisoes.md` + SDD atualizados (decisões 15–25, status implementado).

## Evidência visual
`impressao-a4.png`, `mobile-390.png` (+ loops anteriores).

## DoD L8
Tudo verde ✅ + relatório final (resposta de entrega).
