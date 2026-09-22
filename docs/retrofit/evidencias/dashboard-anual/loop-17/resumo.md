# L17 — Header coerente na navegação com boost (evidência)

Data: 2026-09-22 · TDD (teste falhou antes do fix com o sintoma exato do report).

## Bug

- Sidebar usa `hx-boost` com `hx-target="#main"` + `hx-select="#main"`: navegar
  trocava só o `#main` e o `<header>` (com `#dashboard-controls`, dependente da
  página) ficava obsoleto — toggle de base apontava para o pilar anterior
  (`/pilar/1/?ano=2026&base=fis` com a página em `/pilar/4/`; no `/` o tooltip
  mostrava `/pilar/1/...`).
- Troca manual da URL funcionava porque o full load renderiza o header certo.

## Fix (2 atributos, sem mexer em `#main`/scroll/listeners)

- `templates/components/layout/app_header.html`: `id="app-header"` no `<header>`.
- `templates/components/layout/sidebar.html`: `hx-select-oob="#app-header"` no
  `<nav>` (herdado pelos links do boost; htmx 2.0.10 processa OOB antes do
  `hx-select`, default `outerHTML`; alvo resolvido por `id` no DOM vivo).
- Decisão registrada (item 32); spec `specs/painel-pilar.md` ganha o P13.

## Verificação

- Novo `shell.spec.ts` L17: **falhou antes** (`href "/pilar/1/?ano=2026&base=fis"`
  com URL `/pilar/4/`) e **passa depois**.
- Django: **78/78 OK** (`tests_pilar_painel`, `tests_painel_anual`,
  `tests_frontend`, `tests_navegacao`, `tests_painel_pilar`,
  `tests_pilar_toolbar`, `tests_render`).
- e2e: **98/98** (`shell` 15, `pilar_anual` 12, `dashboard_anual` 32, `portal` 8,
  `fixes_r7` 8, `a11y_r6` 12, `dashboard` 6, `dashboard_r2` 5).
- Nota: navegar pela sidebar reseta os filtros (links sem query → padrão
  `ano=todos&base=fin`); comportamento pré-existente, mantido.
