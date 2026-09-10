# Retrofit Visual QuIIN — R5 Relatório & Auditoria Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox.

**Goal:** Relatório mensal em layout A4 com capa, gráficos (Chart.js sem animação) e assinatura de integridade; auditoria com filtros, timeline visual e paginação preservando os seletores testados.

**Spec:** `docs/superpowers/specs/2026-09-10-retrofit-visual-design.md` (§7 R5)

## Task 1: Backend do relatório

**Files:** `apps/reports/views.py`, `apps/reports/tests.py`

- Adicionar ao contexto (aditivo): `chart_dados_json` (captação/execução por pilar via `graficos_dados`), `assinatura` (sha256 de `periodo.pk`, totais, `gerado_em` — 16 hex, rotulada como integridade), e usar `itens_do_periodo` para as seções (menos queries).
- Teste: contexto traz `chart_dados_json` e `assinatura` (16 chars).

## Task 2: Template A4 + Chart.js

**Files:** `templates/reports/monthly.html`, `static/js/charts/relatorio.js`

- Capa A4 (`data-testid="report-capa"`): logo/marca, título, competência, status, gerado por/em, assinatura; botões `no-print` (Imprimir/Salvar PDF e Voltar).
- Seções por pilar (tabelas meta × realizado), financeiro consolidado com totais, gráficos (`data-testid="report-grafico-captacao"`, `"report-grafico-mensal"`).
- CSS `@page { size: A4; margin: 12mm }` + `@media print` (oculta `no-print`, evita quebra dentro de tabelas).
- `relatorio.js`: inicializa Chart.js (`animation: false`) lendo `#dados-financeiro-relatorio`.
- E2E com `emulateMedia({ media: 'print' })`: capa visível, topbar oculta, sem ações.

## Task 3: Auditoria redesenhada

**Files:** `templates/audit/lista.html`

- Filtros em card (preservar `.panel`, `p.muted.small`, `<strong>{{ total }}</strong>`, `select[name="acao"]`, botão "Filtrar").
- Timeline visual: rail com marcador colorido por `acao_classe`, evento + usuário + data; detalhes em `<details class="audit-detail">` com `.audit-detail-body` (preservados para o E2E).
- Paginação com `data-testid="paginacao-auditoria"` e contagem.

## Task 4: E2E R5, regressão, evidências, docs

- `tests/e2e/reports_r5.spec.ts`: relatório (capa, seções, assinatura, gráficos, print media), auditoria (filtro LOGIN, timeline, paginação).
- Evidências `R5-depois`, suíte completa, `docs/retrofit/loops.md` e commit.

## Self-review
- A4/print, capa, seções, gráficos embutidos, assinatura: Tasks 1–2. ✔
- Auditoria com filtros/timeline/paginação + 100+ eventos: Task 3–4. ✔
- Regressão e evidências: Task 4. ✔
