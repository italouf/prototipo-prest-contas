# Auditoria dos números entre dashboards (L22–L25)

Re-auditar a qualquer momento: `python manage.py auditar_dashboards`
(somente leitura; sai 1 se alguma invariante falhar). Invariantes em
`apps/core/tests_paridade.py` (I1–I3 + I5).

## 1. Fontes de verdade por tela

| Tela | Fonte | Unidade/semântica |
|---|---|---|
| Geral + Pilares (anual) | `PlanoAnual` (snapshot do Anexo A) | R$ mi / metas do plano |
| Mensal | `Lancamento` + `Meta` + `FinanceiroConsolidado` do mês | % médio dos indicadores + R$ operacional |
| Semestral | mesmos, agregados em 6 meses | % (YTD do último mês com dado; MENSAL em média) + R$ do semestre |
| Relatório mensal | mesmos do Mensal, com RBAC (L24) | idem Mensal |

## 2. O que DEVE divergir (by design)

- **Plano × operacional**: Geral 2026 executado R$ 16 mi (PPI 15 + AT 1) ×
  Mensal/Semestral YTD R$ 7,5 mi. Rótulos iguais, fontes distintas (decisão 2).
- **Janela**: mês × semestre. Mensal/junho Formação 187% × S1 187% (após L23);
  antes: 46,76% (média com meses zerados).
- **Bases**: R$ mi/metas (plano) × % médio + R$ (operacional).

## 3. Defeitos encontrados e corrigidos

| # | Achado | Fix |
|---|---|---|
| D1 | YTD do lote somava só a janela da lista (S2 = 0% onde Mensal = 200%) | `calculos._ytd`: jan..alvo (L22) |
| D2 | Mês sem operação valia 0% crítica e diluía a média | sem dado ⇒ `None` (L23) |
| D3 | Pendências = indicador×mês (PDI 33) | pendência = meta no último mês sem lançamento (L23) |
| D4 | KPI ≥100 × heatmap ≥90; denominadores 5 × 8 | critério único + resumo "N/M com execução ≥ 90%" (L23) |
| D5 | 34 indicadores ativos (12 sem meta fora do seed) | `seed_demo` reconcilia; 22/22 dourados (L25) |
| D6 | `AT_LEI_TICS` fora dos cards, dentro das séries | `captacao_at` = AT + AT_LEI_TICS (L24) |
| D7 | "90%" exibido com badge parcial | piso em 1 casa, farol sobre exato (L24) |
| D8 | Relatório sem RBAC no financeiro | filtra pilares visíveis (L24) |

## 4. Números dourados do demo (pós-`seed_demo`)

- Anual: PPI 60/40; AT 7,75/2; Outras 7,75/0 (Anexo A, `test_seed_reproduz_anexo_a`).
- Operacional junho/S1: execução 6.000.000; captação AT 3.000.000; outras
  4.000.000; captado S1 7.000.000 (`SeedReconciliaTestes`).
