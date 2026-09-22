# L24 — Robustez de exibição e contratos (evidência)

Data: 2026-09-22 · Auditoria dos números (QA), TDD.

## Mudança (decisões 2–3 do usuário)

- `captacao_at` soma AT + AT_LEI_TICS (antes só AT; séries já somavam tudo —
  card ≠ gráfico com Lei de TICs). EMBRAPII captado segue fora dos cards
  (repasse, não captação).
- `_formatar_percentual` com 1 casa e piso (nunca arredonda para cima):
  "89,9%" não vira "90%" com badge parcial; vale para KPI, farol e
  tooltips do heatmap.
- `reports:mensal` filtra `pilar__in=pilares_visiveis` no financeiro, nos
  totais e nos aprovados (antes consolidado global para qualquer papel).

## Verificação

- Novos: fronteiras exibição×farol, `CaptacaoBucketsTestes` (I5),
  `RelatorioRBACTestes` — RED antes, GREEN depois.
- Django `core+reports+entries+highlights+crm_at+planning`: 234/234 OK.
- e2e `semestral` + `dashboard_r2` + `dashboard` + `portal` + `reports_r5` +
  `crm_talentos_r4`: 38/38.
