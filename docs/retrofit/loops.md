# Retrofit visual — loops R0–R6

Spec: `docs/superpowers/specs/2026-09-10-retrofit-visual-design.md`
Planos: `docs/superpowers/plans/` · Evidências: `docs/retrofit/evidencias/`

| Loop | Escopo | Status |
|---|---|---|
| R0 | Foundation: deps, tokens QuIIN, fontes, assets vendorizados, primitivos, dark mode, `/dev/design-system/` | ✅ Concluído (2026-09-10) |
| R1 | Shell: base, sidebar colapsável, topbar, breadcrumbs, RBAC visual, navegação HTMX-boosted | ⏳ Pendente |
| R2 | Dashboard executivo: 6 KPIs por pilar, gráficos, heatmap, destaques, avisos, drawer HTMX | ⏳ Pendente |
| R3 | Operacional: lista/filtros, formulário com validação, kanban de status, timeline, modal de devolução, preview CSV | ⏳ Pendente |
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
