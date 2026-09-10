# Retrofit visual — loops R0–R6

Spec: `docs/superpowers/specs/2026-09-10-retrofit-visual-design.md`
Planos: `docs/superpowers/plans/` · Evidências: `docs/retrofit/evidencias/`

| Loop | Escopo | Status |
|---|---|---|
| R0 | Foundation: deps, tokens QuIIN, fontes, assets vendorizados, primitivos, dark mode, `/dev/design-system/` | ✅ Concluído (2026-09-10) |
| R1 | Shell: base, sidebar colapsável, topbar, breadcrumbs, RBAC visual, navegação HTMX-boosted | ✅ Concluído (2026-09-10) |
| R2 | Dashboard executivo: 6 KPIs por pilar, gráficos, heatmap, destaques, avisos, drawer HTMX | ✅ Concluído (2026-09-10) |
| R3 | Operacional: lista/filtros, formulário com validação, kanban de status, timeline, modal de devolução, preview CSV | ✅ Concluído (2026-09-10) |
| R4 | CRM AT e Talentos: funil, pipeline, renovações, organograma, cards, busca por skill | ⏳ Pendente |
| R5 | Relatório A4 e Auditoria: capa, seções por pilar, impressão, timeline/paginação | ⏳ Pendente |
| R6 | Polish: skeletons, tooltips, animações, view transitions, a11y, bundle, remoção do CSS legado | ⏳ Pendente |

## R0 — resultado

**Decisões e entregas**

- Tailwind v4 (CLI standalone 4.3.3, sem Node), tokens QuIIN em
  `assets/styles/theme.css`, build em `static/css/tailwind.css`.
- Fontes self-hosted: Panton (trial, local), Myriad Pro (OTF→woff2 via
  `scripts/convert_fonts.py`), JetBrains Mono (OFL, versionada).
- Componentes primitivos em `templates/components/ui/`: `button`, `card`,
  `badge`, `input`, `select`, `table`, `icon` (+ sprite SVG).
- `base.html` com metas, fontes, Tailwind, HTMX/Alpine e dark mode persistido
  (sem FOUC); CSS legado isolado em `legado.css` (`layer(legado)`).
- Catálogo `GET /dev/design-system/` (DEBUG-only; 404 fora de DEBUG).
- Loaders explícitos cotton + template-partials (ver `docs/decisoes.md`).

**Testes**

- Django: 127 testes, OK (`python manage.py collectstatic --no-input --clear`
  antes, por causa do manifest do Whitenoise).
- Playwright: 18 testes, 18 verdes — inclui `design_system.spec.ts` com toggling
  de dark mode persistido e AxeBuilder (0 violações `critical`/`serious`).
- Correção aplicada no E2E pré-existente de auditoria (dependia de o primeiro
  `<details>` ter corpo não vazio; agora valida o atributo `open`).

**Métricas de bundle (gzip)**

| Arquivo | Gzip | Observação |
|---|---|---|
| `static/css/tailwind.css` | 4,88 KB | CSS completo do R0 |
| `static/css/fonts.css` | 0,31 KB | `@font-face` |
| `static/js/vendor/htmx.min.js` | 16,22 KB | global |
| `static/js/vendor/alpine.min.js` | 19,41 KB | global |
| `static/js/vendor/chart.umd.js` | 68,97 KB | carregado só em páginas com gráficos (a partir do R2) |

**Evidências**

- Antes: `docs/retrofit/evidencias/antes/` (10 páginas).
- Depois: `docs/retrofit/evidencias/R0-depois/` (11 páginas, inclui
  `design-system.png`).

**Comandos de validação**

```text
python manage.py check
python manage.py collectstatic --no-input --clear
python manage.py tailwind build
python manage.py test
npx playwright test
```

**Pendências conscientes**

- Lighthouse ≥ 95: depende de Chrome local; o gate automatizado adotado é o
  axe-core (R0) e será revisto no R6.
- Panton trial: uso local não publicado (risco registrado); antes de publicar,
  adquirir licença ou trocar por fonte livre.

## R1 — resultado

**Decisões e entregas**

- Backend aditivo: context processor `nav` agora expõe `periodos_nav`,
  `pendencias_nav` (ENVIADO para gestores; DEVOLVIDO para focais) e
  `total_pendencias`; nova rota `core:busca` (`/busca/?q=`) com partial HTMX e
  página completa como fallback, respeitando pilares visíveis.
- Shell em componentes cotton `layout/sidebar` e `layout/topbar`; sidebar
  agrupada (Visão geral, Operação, Pilares com badges por pilar, Programa,
  Gestão), colapsável no desktop (`localStorage`) e drawer no mobile.
- Topbar com busca global (`hx-get` + dropdown), seletor de período global
  (submete `?periodo=` no path atual), badge de papel com cores por perfil,
  tema e logout.
- Breadcrumbs (`partials/breadcrumbs.html` + `{% block breadcrumbs %}`) em
  todas as páginas internas.
- Navegação HTMX-boosted: `hx-boost` + `hx-target="#main"` +
  `hx-select="#main"` na sidebar; extensão `head-support` (vendorizada) mantém
  o `<title>` sincronizado; indicador de progresso no topo.
- Login e 403 redesenhados; CSS legado permanece em `layer(legado)` até o R6.
- Correções de infraestrutura: `vendor_assets.ps1` virou idempotente com
  download atômico (`.tmp` + move) após um htmx truncado; `hx-select` necessário
  para o boost não injetar a página inteira; contraste AA do `.nav-secao`.

**Testes**

- Django: **137 testes, OK**.
- Playwright: **24 testes, 24 verdes** (6 novos em `shell.spec.ts`; E2E antigos
  ajustados apenas em seletores afetados pelo seletor global de período e pelo
  container de mensagens).

**Evidências**

- `docs/retrofit/evidencias/R1-depois/` (11 páginas com o shell novo).

**Pendências conscientes**

- Conteúdo das páginas internas ainda é o legado (redesign por loop R2–R5).
- Busca global cobre indicadores, empresas e talentos; ampliar em loops futuros
  se necessário.

## R2 — resultado

**Decisões e entregas**

- `apps/core/dashboard.py`: helpers puros de KPI por pilar (média de execução por
  indicador, metas atingidas, pendentes), heatmap (verde/amarelo/vermelho/cinza),
  avisos críticos e serialização JSON dos gráficos.
- Dashboard (`/`) redesenhado: 6 cards KPI clicáveis (`data-kpi-card`), 3 cards
  financeiros, heatmap por pilar, destaques com filtro por pilar (HTMX),
  avisos, gráficos Chart.js (mensal e por pilar) e tabela consolidada.
- Drawer lateral via `GET /pilar/<pk>/drawer/` (parcial HTMX com guard de pilar,
  403 fora do RBAC).
- Filtro de período do dashboard atualiza os widgets via HTMX com `hx-select`
  (sem reload) e mantém `?periodo=` na URL; sem filtro, o portal passa a
  priorizar o **período aberto** (antes: o mais recente, que podia ser o
  planejado) — ajuste no helper compartilhado `periodo_selecionado`.
- Performance: `itens_do_periodo` (versão em lote de `meta_realizado_percentual`)
  e `papel_do_usuario` com cache por request; agregações em memória.
  **160 → 18 queries** no dashboard; teste trava o orçamento em ≤ 30.
- Chart.js carregado apenas no dashboard (`{% block scripts %}`), com
  destruição/reinicialização após swap HTMX.

**Testes**

- Django: **149 testes, OK** (10 novos de R2 + ajustes de contrato: limite de
  destaques 3 → 6).
- Playwright: **29 testes, 29 verdes** (5 novos em `dashboard_r2.spec.ts`:
  KPIs, filtro de período sem reload, drawer, filtro de destaques, tempo de
  resposta do servidor < 1000ms — medido ~450ms).

**Evidências**

- `docs/retrofit/evidencias/R2-depois/` (11 páginas; dashboard com KPIs,
  heatmap, gráficos e avisos).

**Pendências conscientes**

- Lighthouse Performance ≥ 90 segue previsto para o R6; no R2 o gate é o
  orçamento de queries + tempo de resposta do servidor.
- Gráficos usam cores fixas da marca (tema escuro dedicado no R6).

## R3 — resultado

**Decisões e entregas**

- **Lançamentos** (`/lancamentos/<periodo>/<pilar>/`): filtros por tipo
  (TODOS/QTD/MON/PER/TXT) com Alpine, validação em tempo real por campo
  (numérico e percentual ≤ 100), estado de período fechado somente leitura.
- **Aprovação** (`/aprovacao/<periodo>/`): kanban Rascunho → Enviado →
  Aprovado → Devolvido com contadores, modal de devolução com justificativa
  obrigatória e drawer de timeline (20 eventos de `AuditLog` por lançamento,
  endpoint `entries:lancamento_drawer`, restrito a gestores).
- **Importador financeiro**: preview client-side do CSV (cabeçalho, 6 colunas,
  tipo de recurso, numéricos) com destaque de erros e bloqueio do envio quando
  inválido; o backend atômico permanece inalterado.
- **Toasts globais** no `base.html` (canto superior direito, auto-dismiss 6s,
  `role="status"`), preservando `.messages .alert` para os testes existentes.
- Correção estrutural: blocos `{% block scripts %}` passam a ser carregados
  **antes** do Alpine, garantindo o registro de `Alpine.data` antes do start.

**Testes**

- Django: **155 testes, OK** (4 novos de entries R3, 1 de finance, 1 de toasts).
- Playwright: **34 testes, 34 verdes** (5 novos em `entries_r3.spec.ts`:
  fluxo rascunho→enviado→aprovado, devolução via modal, período fechado,
  filtro por tipo, preview CSV válido/inválido).

**Evidências**

- `docs/retrofit/evidencias/R3-depois/` (11 páginas com o novo fluxo).
