# L18 — Header anual em 3 faixas + botões secundários brancos (evidência)

Data: 2026-09-22 · TDD + paridade com o mockup (`header-filters` acima de
`context-chips`; só "Editar dados" `.btn-primary`).

## Mudança

- `_controles.html` e `_controles_pilar.html`: chips saem da linha dos filtros
  e ganham faixa própria (`justify-end`) entre filtros e toolbar; Baixar
  dashboard, Baixar dados (CSV) e Imprimir passam de `primary` para `ghost`
  (brancos, como "Restaurar padrão"); sem variante nova no design system,
  sem mexer em `size="toolbar"`, alinhamento, OOB, print ou standalone.
- Decisão 33; SDD §8 item 11 e `specs/painel-pilar.md` (P14) atualizados.

## Verificação

- Novo `shell.spec.ts` L18 (`/` e `/pilar/1/`): **falhou antes** (chips na
  mesma linha dos filtros) e **passa depois** (só 1 botão navy `#04047E`).
- e2e: **60/60** (`shell` 16, `pilar_anual` 12, `dashboard_anual` 32) na
  segunda passada; na primeira, 59/60 com flake de carga no L8
  (`AbortError: Transition was skipped` em duplo swap rápido — verde isolado
  e na repassada; não é regressão do fix).
- Django: **78/78 OK** (core: pilar_painel, painel_anual, frontend,
  navegação; planning: painel_pilar, pilar_toolbar, render).
- `tailwind build --force` refeito; detector impeccable (engine v0.1.5,
  pós-update v4.3.1) sem findings nos 2 templates.
- Screenshots: `header-geral.png` (`/?ano=todos&base=fin`) e
  `header-pilar-at.png` (`/pilar/4/?ano=2026&base=fis`).
