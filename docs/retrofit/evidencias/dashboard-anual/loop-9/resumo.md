# L9 — Correções (evidência)

Data: 2026-09-17 · Causa raiz dos gráficos: localização pt-BR em atributos SVG.

## Diagnóstico
`LANGUAGE_CODE=pt-br` + `USE_I18N` faziam floats renderizar com vírgula:
`<rect x="22,06" … width="24,84">` (inválido → largura 0 → barras invisíveis;
`x/y` inválidos → rótulos e grades colapsados em 0). Mesmo bug latente em
`value="1,75"` nos `<input type="number">` do editor. Prova: HTML capturado
no output de teste anterior + matriz L0 intacta (dados corretos, render quebrado).

## Entregas
- F1: `{% localize off %}` nos dois SVGs + kpi-card; `|unlocalize` no editor.
  Rótulos visíveis seguem pt-BR (`numero_curto`).
- F2: tabela `min-w-[880px] print:min-w-0` + `whitespace-nowrap` + `pr-4`
  (cabe em ≥1280px, rola abaixo, imprime sem corte).
- F3: removido parágrafo duplicado de `anual.html`.
- F4: AT e Talentos em Gestão (restrita, condição inalterada); Pilares só
  com os 4 pilares PPI. PontoFocal perde o link (URL preservada) — aceito.

## Verificação
- Django: 244/244 (4 novos em `planning/tests_render.py` + estruturais em navegação).
- e2e: 97/97 (4 novos: pintura via getBBox, tabela no card, sticky real, IA sidebar).
- Evidência visual: `graficos-corrigidos.png`, `tabela-2026-fis.png`, `sidebar-gestao.png`.
