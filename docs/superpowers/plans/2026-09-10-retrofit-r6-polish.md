# Retrofit Visual QuIIN — R6 Polish & Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or executing-plans.

**Goal:** Eliminar o CSS legado, migrar as últimas telas (pilar, financeiro consolidado, formulários, auditoria), e entregar polish: skeletons, tooltips, animações, view transitions, a11y completa, bundle dentro do orçamento e remoção de `local.css`.

**Spec:** §8 (a11y/perf) e R6.

## Task 1: Migração final + remoção do legado

- Redesenhar `templates/dashboard/pilar.html` e `templates/finance/consolidado.html` com Tailwind/cotton.
- Auditoria: trocar `.panel`/`.muted small` por utilitários (adicionar `data-testid="auditoria-total"`), `c-ui.badge` para a ação com `data-testid="badge-acao"`; atualizar o E2E do dashboard.
- Formulários (CRM/Talentos): `.field` → utilitários; `.alert alert-error` mantido (definir em `input.css`).
- Adicionar a `assets/styles/input.css`: componentes `.alert-*`, `.field input/select/textarea` base, `.report-secao`, `.table-report`, `.audit-detail(-body)`, `.skeleton`, `.anim-entrada`, `::view-transition-*`.
- Remover `<link legado.css>` do base, apagar `static/css/legado.css` e `static/css/local.css`.

## Task 2: Polish

- Skeletons: `#skeleton-dashboard` no dashboard e `#skeleton-drawer` genérico, exibidos via `hx-indicator`; `.skeleton` com pulse.
- Tooltips: `title` nos botões de ícone (tema, sair, recolher, fechar) e células do heatmap (já têm `title`).
- Animações: `.anim-entrada` (fade+slide, respeitando `prefers-reduced-motion`) em KPI cards, talent cards, kanban cards e seções do relatório.
- View transitions: `<meta name="htmx-config" content='{"globalViewTransitions": true}'>` no base + CSS de duração.
- A11y: `tests/e2e/a11y_r6.spec.ts` com AxeBuilder em 9 páginas autenticadas (0 critical/serious) + teste de teclado (skip link → Tab).
- Budget: teste Django com gzip (`gzip` stdlib): CSS ≤ 150KB, JS por página ≤ 200KB (htmx+alpine+chart).
- Lighthouse: tentar `npx lighthouse` headless; se indisponível, registrar fallback (axe-core).

## Task 3: Fechamento

- `tests/e2e/polish_r6.spec.ts` (skeletons visíveis em swap, animação presente, view transitions ativas, foco visível).
- Evidências `R6-depois`, suíte completa, `docs/retrofit/loops.md` (R6 concluído + métricas finais), commit final.

## Self-review
- Legado removido: Task 1. ✔ · Skeletons/tooltips/animações/transitions: Task 2. ✔
- A11y completa + budgets + Lighthouse: Task 2. ✔ · Regressão/evidências: Task 3. ✔
