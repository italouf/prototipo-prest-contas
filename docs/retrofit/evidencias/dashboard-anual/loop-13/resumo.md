# L13 — Componentes + view do pilar (evidência)

Data: 2026-09-17 · TDD: view (7 testes) antes dos templates.

## Entregas
- `core.views.pilar`: painel anual sempre (defaults `todos`+`fin`), alias ⇒ 302
  canônico, inválido ⇒ 302 (preserva `periodo` validado), HX ⇒ `_fragmento_pilar`
  (`#painel-pilar` + OOB `#dashboard-controls`); seção mensal intacta; banner
  `contexto-anual` removido (chips assumem).
- Templates: `tabela-anual-pilar` (linhas por ano + Total + legenda),
  `painel-pilar` (3× `kpi-card` + card %/farol custom + `chart-fonte` +
  tabela + `modal-farol`), `_controles_pilar` (filtros+chips, sem toolbar —
  L15), `_fragmento_pilar`; `app_header` com ramo `painel_pilar`.
- DTO ganhou chave `grafico` (formato do `chart-fonte`); tabela mostra todos
  os anos + Total acumulado com destaque no ano filtrado (como o gráfico).

## Verificação
- Django: 7 view-tests + 11 service-tests verdes.
- e2e `pilar_anual`: 7/7 (P01–P06 + P11). P11 congela animações antes do axe
  (flake `anim-entrada`: opacity parcial derruba o contraste — estado final OK).
- Evidência visual: `pilar-pdi.png`, `pilar-at-2026-fis.png`.
