# L21 — Visão geral semestral no padrão Geral/Pilares (evidência)

Data: 2026-09-22 · TDD + spec `specs/prestacao-semestral.md` (S01–S10, S-U01–S-U05).

## Mudança

- `calculos.itens_por_periodo` (batch 3 queries, mesma semântica de
  `itens_do_periodo` com YTD por ano) + `prestacao.painel_semestral` (média
  dos percentuais-mês, `meses` = meses com lançamento aprovado, tabela do
  último mês para YTD, financeiro somado, status agregado, destaques,
  geometria `core.charts` com 6 grupos).
- `core:semestral` com `?ano=&semestre=` canônico (302; legado `?ano=`
  incluído) + `core:semestral_csv` (`;` + BOM); view casca fina.
- Header: `_controles_semestral.html` (ano + segmentado 1º/2º + chips +
  CSV/Imprimir/Restaurar) + `_fragmento_semestral.html` (OOB espelhado) +
  ramo `painel_semestral` + `barra-toggle`; mensal ganha "Ver semestre".
- Template: `semestral.html` casca + `_painel_semestral.html` (6 KPIs com
  farol, 3 cards financeiros, 2 SVG, status, tabela com Farol, destaques,
  meses com drill-down, empty states, `print-cabecalho`).
- `SemestralViewTestes` reescrito para o novo contrato.

## Verificação

- Django: lotes completos (ver L22); e2e `semestral.spec.ts` S01–S10.
- Orçamento semestral ≤ 40 queries; `tailwind build --force`; detector
  impeccable limpo; axe no semestral (S08 + rota `a11y_r6`).
- Screenshots: `header-semestral.png` e `semestral-geral.png`.
- Achados do loop: (1) servidor e2e obsoleto mascarou o fix de `data-categoria`
  — rotina de identificar/encerrar processos documentada; (2) `bloco=/geo=`
  sem `:` no cotton passam string literal e esvaziam os SVGs — corrigido nos
  4 usos + M01 passou a assertar conteúdo (`g[data-categoria]`), não só
  visibilidade.
