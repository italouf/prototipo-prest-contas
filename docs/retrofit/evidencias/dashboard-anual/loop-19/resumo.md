# L19 — Ocultar a barra do painel pelo topbar (evidência)

Data: 2026-09-22 · TDD (teste falhou antes do fix; botão inexistente).

## Mudança

- Botão-ícone 32px (`barra-toggle`, chevron-up novo no sprite, padrão L11)
  no topbar antes do tema, só nas páginas com painel; oculta
  `#dashboard-controls` por inteiro via `data-barra-oculta` no `<html>`.
- Estado em `localStorage['quiin-barra']`, aplicado antes do paint (sem
  flash) e reaplicado em `DOMContentLoaded` + `htmx:afterSettle` (sobrevive
  a swaps OOB, boost com `hx-select-oob` e back/forward); `aria-expanded` e
  rótulo ("Ocultar/Mostrar filtros e ações") atualizados por JS.
- Sem variante nova no design system; print/impressão inalterados (topbar e
  controles já são `display:none`).

## Achado de quebra (bug real pré-existente)

- O teste L19 revelou que todo swap de filtro substituía o
  `#dashboard-controls` vivo por `<div id="dashboard-controls">` sem
  classe/testid: os divs OOB de `_fragmento.html`/`_fragmento_pilar.html`
  não espelhavam os atributos do app_header (regressão visual silenciosa —
  padding e borda-topo perdidos após qualquer filtro — desde L3/L13).
- Fix no mesmo loop: OOBs com os mesmos atributos do app_header (+ aviso
  em comentário) e guarda `data-testid="dashboard-controls"` nos testes
  de fragmento de `tests_painel_anual.py` e `tests_pilar_painel.py`.
- Evidência do diagnóstico: dump do DOM num spec temporário (removido).

## Verificação

- Novo `shell.spec.ts` L19 + `test_toggle_da_barra_so_existe_com_painel`:
  RED antes, GREEN depois.
- e2e: **61/61** (`shell` 17, `pilar_anual` 12, `dashboard_anual` 32).
- Django: **79/79 OK** (core: pilar_painel, painel_anual, frontend,
  navegação; planning: painel_pilar, pilar_toolbar, render).
- `tailwind build --force` refeito; detector impeccable sem findings
  (`app_header.html`, `base.html`, `input.css`).
- Screenshots: `barra-oculta.png` (header só com identidade/busca/utilidades
  + chevron para baixo).
