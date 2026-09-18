# L16 — Regressão completa do painel por pilar (evidência)

Data: 2026-09-18 · TDD + paridade em todos os loops.

## Verificação
- Django: **276/276 OK** (168 + 108, duas metades; inclui 11 painel_pilar,
  13 toolbar pilar, 9 view pilar, 7 navegação, query ≤ 25 na página do pilar).
- e2e: **112/112** (inclui 12 pilar_anual: P01–P11; P07 navegação; P08–P10b toolbar).
- axe: P11 (2 estados do pilar) + suíte a11y verdes.
- Paridade: matriz SDD §9.4 confirmada por pilar/ano/base (unit + e2e).

## Correções no loop
- `portal.spec.ts`: heading com `exact: true` (painel adicionou headings do pilar).
- Flake de carga: `a11y: /auditoria/` estourou 30s no run completo; verde isolado (8.5s).
- Decisão L12.0 registrada (item 31); spec SDD §9 + `specs/painel-pilar.md` revisados e aprovados.
