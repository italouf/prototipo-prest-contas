# L23 — Semântica "sem dado ≠ zero" + critério único (evidência)

Data: 2026-09-22 · Auditoria dos números (QA), TDD.

## Mudança (decisões 1–2 do usuário)

- `calculos`: YTD sem lançamento aprovado no ano ⇒ `realizado/percentual =
  None` (antes 0% crítica); vale para `valor_acumulado_ytd`,
  `meta_realizado_percentual`, `itens_do_periodo` e `itens_por_periodo`.
- `prestacao.painel_semestral`: por pilar, YTD usa o mês mais recente com
  lançamento e MENSAL usa a média dos meses com lançamento; `pendentes` =
  meta no último mês sem lançamento; `atingidos` segue ≥100.
- `dashboard.heatmap_por_pilar`: `resumo` = "N/M com execução ≥ 90%" com
  M = indicadores com meta (antes "N/M na meta" com todos, critério ≥90
  implícito × KPI ≥100).
- Specs `prestacao-mensal.md`/`prestacao-semestral.md` atualizadas.

## Verificação

- Django `apps.core` 106/106 + `entries/highlights/reports/crm_at/planning`
  125/125 OK (inclui invariante I1 e `test_heatmap` com resumo).
- e2e `semestral` + `dashboard_r2` + `dashboard` + `polish_r6`: 28/28.
- Efeito esperado no demo: Formação S1 passa a usar meses com dado
  (187% no seed); S2 sem lançamentos fica neutro ("—").
