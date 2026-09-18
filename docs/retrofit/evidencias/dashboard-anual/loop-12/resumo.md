# L12 — Serviço painel_pilar (evidência)

Data: 2026-09-17 · TDD: `apps/planning/tests_painel_pilar.py` (10 testes) → `services.painel_pilar`.

## Entregas
- `painel_pilar(pilar, ano, base)`: previsto/executado/saldo/pct/faixa do período,
  4 cards (Previsto, Executado, Saldo, % — formato compatível com `kpi-card`,
  exceto o card % que renderiza custom), séries 4 anos + acumulado,
  `rodape_pct/faixa`, tabela por ano (Ano 1..4 + Total), `rotulo_previsto`
  (Projetado/Captado), `unidade`, `rotulo_periodo`.
- Pilar sem linhas tolerado (zeros, pct None, faixa neutra); base/ano inválidos ⇒ ValueError.

## Verificação
- `manage.py test apps.planning.tests_painel_pilar` → 10/10 OK (PDI/AT/FCRH/Infra,
  FIN/FIS, ano específico, séries, tabela, cards, vazio, inválidos, ≤2 queries).
- Matriz §9.4 do SDD confirmada pelos testes (ex.: PDI FIN 29×21/72%; AT FIN 7,75×2/26%).
