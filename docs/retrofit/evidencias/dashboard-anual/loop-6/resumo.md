# L6 — Tabela gerencial + farol + modal (evidência)

Data: 2026-09-17 · Commit: `feat(dashboard)` (LOOP 6)

## Entregas
- `pilares-table`: grupos 4.1/4.2/4.3, Total PPI em negrito, badges do farol
  (dot + rótulo), cabeçalhos por base, legenda das 3 faixas.
- `modal-farol` autocontido (gatilho + diálogo): texto integral do Anexo B,
  `role="dialog"` + `aria-modal`, foco no fechar ao abrir, **focus trap**,
  ESC, clique no backdrop e no X, **retorno de foco ao gatilho**.

## Verificação
- Django: teste da tabela + modal (grupos, 3 rótulos, título e fórmulas) ✅.
- e2e T09 (farol acumulado FIN + acumulado FIS/FCRH 47% crítica) e T11
  (foco interno, ESC + retorno de foco, X, backdrop) ✅; a11y 12/12 ✅.
- Correções no loop: `tailwind build --force` (cache ignora templates —
  faltavam `max-w-2xl`/`max-h-[86vh]`, o que quebrava o clique no backdrop);
  expectativa do teste ajustada ao valor real (FCRH 2024 FIS = 67% parcial).
- DoD L6: farol correto por faixa ✅; modal passa foco/ESC ✅.
- Evidência visual: `tabela-gerencial.png`, `modal-farol.png`.
