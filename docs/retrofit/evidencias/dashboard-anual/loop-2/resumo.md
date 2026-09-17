# L2 — Dados e backend (evidência)

Data: 2026-09-17 · Commit: `feat(planning)` (LOOP 2)

## Entregas
- Novo app `apps/planning`: `models.PlanoAnual` (ano, pilar, base, previsto,
  executado + unique + checks), `services` (percentual, faixa, pct_inteiro,
  rotulo_previsto, painel — 1 query por render), `charts` (geometria SVG pura),
  `admin`, `migrations/0001_initial.py`.
- `seed_demo`: constante `PLANO_ANUAL` (matriz Anexo A) + `_plano_anual()`
  idempotente (48 linhas).
- `apps/planning/tests.py`: 20 testes (10 estados × cards, tabela acumulada,
  rodapés, séries, farol, denominador zero, queries, geometria, seed).

## Verificação
- `manage.py test apps.planning` → 20/20 OK.
- `manage.py test` (suíte completa) → 210/210 OK (190 existentes + 20 novos).
- `manage.py migrate planning` no banco local → OK; `seed_demo` → 48 linhas,
  financeiro soma previsto 75,5 / executado 42.
- DoD L2: testes unitários verdes cobrindo Anexo A nos 10 estados ✅,
  farol por faixa ✅, denominadores zero ("—"/None, sem exceção) ✅.
