# L25 — Seed reconciliador + auditoria contínua (evidência)

Data: 2026-09-22 · Auditoria dos números (QA), TDD (decisão 4 do usuário).

## Mudança

- `seed_demo._reconciliar_indicadores`: garante os 22 canônicos ativos e
  desativa extras (os 12 do `seed_operacionais`, que segue opcional fora
  do padrão).
- `SeedReconciliaTestes`: reconciliação (intruso desativado, 22/22,
  idempotente) + números dourados operacionais (junho/S1: execução
  6.000.000, captação AT 3.000.000, outras 4.000.000, captado S1 7.000.000).
- `manage.py auditar_dashboards` (novo, read-only, sai 1 em divergência):
  conjunto demo, somas Geral×Pilares (fin+físico), financeiro
  Mensal×Semestral, lote==único, default do semestral.
- `docs/auditoria-numeros.md`: matriz fonte→tela→semântica + catálogo D1–D8.

## Verificação

- `apps.seed` 7/7 OK; comando roda no banco de dev sinalizando a poluição
  ([AVISO] 34 ativos com os 12 listados) e confirmando as paridades
  (somas 60/52, financeiro 7,5M == 7,5M, 0 divergências lote×único).
- Regressão final abaixo antes do commit.
