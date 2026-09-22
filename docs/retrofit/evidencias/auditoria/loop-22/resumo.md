# L22 — Harness de paridade + fix da janela YTD (evidência)

Data: 2026-09-22 · Auditoria dos números (QA), TDD.

## Achado crítico (D1)

`calculos.itens_por_periodo._ytd` somava apenas os meses da lista passada:
`FORM-CURSOS` julho = 0% no lote × 200% no cálculo único; 18/34 itens
divergiam quando o lote não começava em janeiro. Semestral S2 exibia 0%
(crítica) onde o Mensal exibe 200%.

## Fix

`_ytd` soma jan..mês-alvo do ano via `somas` por competência, independente
da lista. `apps/core/tests_paridade.py` (novo): I1 lote==único por período,
I2 Σ `painel_pilar` == bloco do `painel`, I3 financeiro Mensal(último mês)
== Semestral.

## Verificação

- `tests_paridade` RED antes (2 falhas na janela), GREEN depois.
- Django `tests_paridade` + `tests_prestacao` OK nesta passada.
