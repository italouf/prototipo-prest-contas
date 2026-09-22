# L20 — Prestação mensal no padrão Geral/Pilares (evidência)

Data: 2026-09-22 · TDD + spec `specs/prestacao-mensal.md` (M01–M09, U01–U05).

## Mudança

- `apps/core/prestacao.py` (novo): `contexto_mensal`, `resolver_periodo`
  (inválido ⇒ 302 canônico), `resolver_destaque` (valida visibilidade —
  fecha micro-vazamento do filtro antigo), séries em R$ mi; view
  `core:mensal` vira casca fina; helpers mortos removidos de `views.py`.
- `apps/core/charts.py` (novo): `geometria_barras` genérica (N grupos,
  divisor opcional); `planning/charts.py::geometria_fonte` delega com
  **saída idêntica**; `geometria_consolidado` intacto.
- `chart-fonte.html`: `eixo_rotulo`/`legenda_a`/`legenda_b` com defaults
  do anual (render anual inalterado).
- Header: `_controles_mensal.html` (período + status + chips + toolbar com
  Aprovar/Abrir-Fechar-Reabrir/Relatório/Imprimir) + `_fragmento_mensal.html`
  (OOB espelhado) + ramo `painel_mensal` + `barra-toggle` no mensal.
- Template: `mensal.html` casca + `_painel_mensal.html` (avisos, 6 KPIs com
  farol, 3 cards financeiros, 2 SVG, status, tabela com Farol, heatmap,
  destaques com swap de painel, drawer fora do swap, `print-cabecalho`).
- Farol unificado (≥90/≥50/<50); `|unlocalize` nos widths (inclusive barras
  de status legadas, que geravam `width: 100,0%` inválido); Chart.js fora
  do dashboard (fica no relatório); filtro de destaques com push-url.

## Verificação

- Django: **292/292 OK** (lotes `core+planning` e demais apps).
- e2e: **122/122** (M01–M09 novos; `dashboard_r2` reescrito; `dashboard.spec`,
  `polish_r6`, `shell` L19 e `a11y_r6` (+ rota mensal) ajustados).
- Orçamento mensal ≤ 30 queries mantido; `tailwind build --force`;
  detector impeccable limpo.
- Screenshots: `header-mensal.png` (controles: período, chips, toolbar com
  "Aprovar 4 pendentes" navy) e `mensal-geral.png` (avisos + KPIs com farol).
