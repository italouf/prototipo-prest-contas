# L5 — Cards e gráficos (evidência)

Data: 2026-09-17 · Commit: `feat(dashboard)` (LOOP 5)

## Entregas
- Componentes cotton em `templates/components/dashboard/`: `kpi-card`
  (borda colorida por token, valor `.numerico`, barra + badge do farol),
  `farol-badge` (sempre dot + rótulo), `chart-fonte` e `chart-consolidado`
  (SVG server-side: divisor do acumulado, rótulos numéricos, destaque por
  opacidade + `data-destaque`, tooltips via `<title>`, cores só por
  utilities `fill-*/stroke-*` de tokens + `fill-current`).
- Geometria 100% em `planning/charts.py` (centros, rótulos, grade, fundo);
  view injeta `geo_fonte`/`geo_consolidado`; template só emite SVG.
- Filtro `numero_curto` (até 2 decimais, sem zeros à direita: 75,5 · 7,75 · 40).
- CSS: `.kpi-borda-1..4` via `var(--color-quiin-*)` (sem hex inline).

## Verificação
- e2e `dashboard_anual`: 16/16 — paridade de valores com o Anexo A nos
  10 estados (cards + subs + badges + rodapés + chips, lidos da matriz L0)
  e destaques corretos (fonte + consolidado).
- Django planning 20/20; painel_anual + navegação verdes; a11y 12/12.
- DoD L5: paridade Anexo A nos 10 estados ✅; highlights ✅.
- Evidência visual: `cards-graficos-padrao.png`, `cards-graficos-2026-fis.png`.
