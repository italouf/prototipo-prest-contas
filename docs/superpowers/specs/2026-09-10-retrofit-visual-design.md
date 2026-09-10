# Retrofit Visual do Portal QuIIN — Design (spec)

Data: 2026-09-10
Branch: `feat-retrofit-visual`
Status: aprovado em conversa; execução por loops R0–R6
Escopo: front-end (Django Templates + Design System). Back-end, URLs e RBAC preservados.

## 1. Contexto e objetivo

O portal foi construído com foco em back-end; a UI atual é um CSS único
(`static/css/local.css`, 254 linhas) sem componentes, sem build e com identidade
visual provisória (navy `#0e2347` + dourado). Este retrofit substitui a camada
visual por um Design System interno com a marca QuIIN, servido localmente
(sem CDN em runtime, sem SPA, sem Node em runtime) e documentado para evolução.

Público: liderança C-Level do QuIIN e gestores EMBRAPII. Princípios: executivo,
técnico, sóbrio, data-dense sem poluição, micro-interações sutis, WCAG 2.1 AA.

## 2. Não-objetivos e invariantes

- Não migrar para SPA (React/Vue/Angular); Django SSR é a fonte da verdade.
- Não quebrar views/URLs/regras de negócio; mudanças de back-end são apenas
  aditivas (contexto de view/helpers de apresentação).
- Não remover RBAC; apenas melhorar a representação visual de papel/pilar.
- Sem CDN em produção/execução local; assets servidos pelo Whitenoise.
- Sem Node em runtime; Node apenas em devDependencies de QA (Playwright).
- Sem dados reais; base `seed_demo` fictícia.

## 3. Decisões

| Tema | Decisão | Observação |
|---|---|---|
| Build CSS | `django-tailwind-cli` 4.8.0 (Tailwind v4 standalone) | `manage.py tailwind build/watch/runserver`; binário em `.django_tailwind_cli/` |
| Componentes | `django-cotton` 2.7.2, `COTTON_DIR="components"` | sintaxe HTML `<c-ui.button>`; `COTTON_SNAKE_CASED_NAMES=False` para nomes kebab |
| Fragmentos | `django-template-partials` 25.3 | `{% partialdef %}` + `template.html#partial` nas views |
| HTMX | `django-htmx` 1.29.0 + HTMX 2.0.10 vendorizado | `request.htmx`, `hx-boost`, OOB |
| Micro-interações | Alpine.js 3.17.2 vendorizado | dark mode, dropdowns, modais, toasts |
| Gráficos | Chart.js 4.5.1 vendorizado | interativo; impressão com `animation:false` |
| Ícones | SVG sprite local + componente `ui/icon` | Heroicons/Lucide inline, sem JS |
| Tipografia | Panton Trial (local, risco aceito), Myriad Pro licenciada (OTF→woff2), JetBrains Mono (OFL) | `font/` fora do git; ver §5.2 |
| Source CSS | `assets/styles/input.css` (fora de `static/`) | evita `django_tailwind_cli.W001` e quebra do manifest storage |
| Output CSS | `static/css/tailwind.css` via `{% tailwind_css %}` | `TAILWIND_CLI_DIST_CSS="css/tailwind.css"` |
| Loops | Renomeados R0–R6 | não colidem com LOOP 0–6 do back-end (`docs/loops.md`) |

### 3.1 Decisão de licença tipográfica (registro)

Os arquivos de Panton no repositório são **trial/demo** (`Panton-Trial-*`,
`PantonDemo-*`, EULA de trial). O uso foi explicitamente aceito para este
protótipo **local, não publicado**, com risco assumido pelo solicitante. A pasta
`font/` é ignorada pelo git. Se o portal for publicado ou redistribuído, Panton
comercial deve ser adquirida ou substituída por alternativa livre.

## 4. Arquitetura

### 4.1 Pipeline de CSS

```
font/ (gitignored)                         assets/styles/input.css
  panton/WEB/*.woff2                          @import "tailwindcss";
  myriad-pro/*.otf  --convert-->              @source "../../templates";
  JetBrainsMono-2.304/...                     @source "../../apps";
        |                                     @import "./theme.css";
        v                                     @layer base/components/utilities
static/fonts/...                            assets/styles/theme.css
  (panton e myriad gitignored;                @theme { tokens QuIIN }
   jetbrains commitado)                      @custom-variant dark
        |                                            |
        +----------------------+---------------------+
                               v
                  manage.py tailwind build
                               v
                  static/css/tailwind.css  (Whitenoise)
```

Classes usadas somente por código Python (mapas de variantes) são garantidas por
mapas explícitos de classes completas no template/componente, nunca por
concatenação de strings (Tailwind só detecta classes literais).

### 4.2 Fontes

- `scripts/convert_fonts.py` (idempotente; `fonttools`+`brotli` em
  `requirements-dev.txt`): converte pesos selecionados para woff2 e copia
  Panton/JetBrains para `static/fonts/`.
- Pesos: Panton Light/Regular/SemiBold/Bold/Black; Myriad Pro Light/Regular/
  SemiBold/Bold; JetBrains Mono Regular/Medium/Bold.
- `@font-face` com `font-display: swap` em `static/css/fonts.css` (arquivo
  servido diretamente, não processado pelo Tailwind; URLs relativas
  `../fonts/...` resolvem tanto em `static/` quanto em `staticfiles/`).
- Deploy sem `font/` cai no fallback (`system-ui`); documentado em
  `docs/como-rodar.md`. Ver §5.2.

### 4.3 Assets JS vendorizados

`scripts/vendor_assets.ps1` baixa versões pinadas (executado uma vez; arquivos
commitados em `static/js/vendor/`):
HTMX 2.0.10 (+ extensão loading-states), Alpine 3.17.2, Chart.js 4.5.1.
Chart.js é carregado apenas em páginas com gráficos.

### 4.4 Componentização

```
templates/components/
  ui/         button, card, badge, input, select, table, icon
  layout/     sidebar, topbar, breadcrumbs (shell em templates/base.html, R1)
  patterns/   metric-card, status-pill, approval-flow, period-selector, filter-bar
  charts/     kpi-gauge, bar-comparison, trend-line
```

Uso: `<c-ui.button variant="primary">Salvar</c-ui.button>`,
`<c-patterns.metric-card :dados="card" />` (dot notation do cotton para
subpastas). Fragmentos HTMX com `{% partialdef %}`; views retornam
`template.html#partial` (django-template-partials).

Risco de integração: cotton e template-partials auto-configuram loaders de
template. Primeira verificação do R0: compor os dois; se necessário usar
`template_partials.apps.SimpleAppConfig` + `wrap_loaders("django")`.

### 4.5 Interação (HTMX + Alpine)

- Navegação `hx-boost` (SPA-like) com `hx-target="#main"`, `hx-push-url="true"`
  e barra de progresso (`htmx-indicator`); fallback: navegação normal.
- Filtros/period selector: `hx-get` para fragmento + OOB para KPIs.
- Formulários: `hx-post` com CSRF global (`hx-headers` no `<body>`);
  erros de validação re-renderizam o partial com 422; sucesso dispara toast.
- Toasts: partial OOB a partir de `django.contrib.messages` + Alpine.
- Sessão expirada: `HX-Redirect` para login (django-htmx).
- Sem JavaScript obrigatório para navegação principal (progressive enhancement).

### 4.6 RBAC visual

Papel ativo indicado no topbar por cor + rótulo (nunca só cor): Master=violet,
Admin=royal, PontoFocal=sky, Lideranca=blue, Auditor=slate/muted. Itens de
navegação seguem a matriz de permissões atual (context processor `nav`).

## 5. Design tokens

### 5.1 Paleta e tipografia (fonte: brand guidelines QuIIN)

| Token | Hex | Uso |
|---|---|---|
| `--color-quiin-navy` | `#04047E` | primária, CTAs, headers |
| `--color-quiin-deep-purple` | `#1B1641` | sidebar, fundos escuros |
| `--color-quiin-royal` | `#0F3B94` | links, ícones ativos |
| `--color-quiin-blue` | `#144FAD` | botões secundários |
| `--color-quiin-sky` | `#1D72B9` | acentos, hover |
| `--color-quiin-quantum-green` | `#2EBF7D` | sucesso, meta atingida |
| `--color-quiin-violet` | `#3B249C` | destaques, pilar PDI |
| `--color-quiin-mist` | `#DEDFE8` | bordas, divisores, fundos |

Semânticos (light/dark): `surface`, `surface-2`, `border`, `text`, `text-muted`,
`focus-ring`. Status: `rascunho` (slate), `enviado` (blue), `aprovado`
(quantum-green), `devolvido`/`pendente` (âmbar), `fechado` (quantum-green),
`aberto/reaberto` (royal), `planejado` (slate).

Cores por pilar: PDI=violet, Formação=blue, Startups=sky, AT=royal,
Infraestrutura=navy, Outras Fontes=quantum-green.

Tipografia: `--font-display: Panton`, `--font-sans: "Myriad Pro"`,
`--font-mono: "JetBrains Mono"` (números tabulares para KPIs/tabelas).
Escala: 12/13/14/16/18/24/30/38; pesos 300/400/600/700; line-height 1.5 corpo.

Espaçamento base 4px; raios 6/10/14px; sombras sutis; foco visível 2px com
offset 2px; dark mode class-based (`dark` no `<html>`, persistido em
`localStorage`, sem FOUC via script inline no `<head>`).

### 5.2 Fontes: arquivos e serving

`static/fonts/panton/**` e `static/fonts/myriad-pro/**` **não são commitados**
(licenças). O script gera os arquivos localmente; `docs/como-rodar.md` descreve
o passo. `static/fonts/jetbrains-mono/**` é commitado (OFL).

## 6. Inventário de componentes

### R0 — primitivos (`ui/`)

| Componente | Atributos/slots |
|---|---|
| `ui/button` | `variant` (primary/secondary/ghost/danger), `size` (sm/md/lg), `href`, `type`, `disabled`, `loading`, slot `icon`, `attrs` extras (ex.: `hx-*`) |
| `ui/card` | `variant` (metric/action/panel), slots `header`, `slot`, `footer` |
| `ui/badge` | `tone` (neutral/success/warn/danger/info/pillar), `pillar` (código), slot |
| `ui/input`/`ui/select` | `name`, `label`, `help`, `error`, `required`, `value`, `attrs` extras |
| `ui/table` | slots `head`, `body`; `caption` opcional; wrapper responsivo |
| `ui/icon` | `name` (sprite), `size` (16/20/24), `class` |

### Loops seguintes

- `layout/` (R1): sidebar colapsável agrupada por pilar com badges de
  pendência, topbar (busca, perfil, seletor de período, dark toggle),
  breadcrumbs, shell autenticado e login/403.
- `patterns/` (R2/R3): metric-card (meta × realizado × %), status-pill,
  approval-flow (timeline), period-selector, filter-bar, kanban-card.
- `charts/` (R2/R5): kpi-gauge, bar-comparison, trend-line; wrapper que lê
  JSON de `<script type="application/json">` e inicializa Chart.js.

## 7. Mapa de retrofit por template

| Template | Loop | Observações |
|---|---|---|
| `base.html` | R1 | shell final; R0 prepara metas/fontes/scripts/dark |
| `registration/login.html`, `403.html` | R1 | estados não autenticados |
| `home.html` (`/`) | R2 | dashboard executivo; rota preservada |
| `dashboard/pilar.html` | R2 | visão por pilar |
| `entries/lancamento.html`, `entries/aprovacao.html` | R3 | kanban + modal de devolução + timeline |
| `finance/importar.html`, `finance/consolidado.html` | R3 | preview CSV com validação visual |
| `crm_at/{funil,empresa_form,oportunidade_form}.html` | R4 | funil + pipeline + renovações |
| `talentos/{organograma,colaborador_form,alocacao_form}.html` | R4 | organograma interativo + banco de talentos |
| `reports/monthly.html` | R5 | A4/print; capa e seções por pilar |
| `audit/lista.html` | R5 | timeline + filtros + paginação |
| `dev/design_system.html` | R0 | catálogo interno (DEBUG-only) |

## 8. Acessibilidade e performance

- WCAG 2.1 AA: contraste ≥ 4.5:1 (texto), foco visível, navegação por teclado,
  landmarks, labels explícitas, `aria-live` para toasts, status nunca só por cor.
- Gate automatizado: `@axe-core/playwright` nas páginas-chave; Lighthouse
  (carregado via npx) como métrica complementar.
- Orçamentos (R6): CSS < 150KB gzip; JS < 200KB gzip; dashboard < 800ms de
  renderização; sem CLS perceptível; `prefers-reduced-motion` respeitado.

## 9. Testes e evidências

- Django: suíte atual permanece verde; novos testes unitários apenas para
  helpers de apresentação adicionados.
- Playwright E2E: um spec por loop em `tests/e2e/`; os 8 testes existentes
  devem continuar verdes (regressão obrigatória a cada loop).
- Convenção `data-testid`: `page-<slug>`, `kpi-card`, `kpi-<codigo>`,
  `period-selector`, `period-option-<YYYY-MM>`, `status-pill`, `dark-toggle`,
  `toast`, `drawer`, `kanban-col-<status>`, `btn-<variant>`.
- Evidências: screenshots antes/depois em `docs/retrofit/evidencias/<loop>/`;
  métricas de bundle no relatório de cada loop.
- Fluxo: TDD onde aplicável (helpers/scripts), execução dos testes ao final de
  cada loop, pausa para aprovação antes do loop seguinte.

## 10. Roadmap R0–R6

| Loop | Escopo | Critérios de saída |
|---|---|---|
| R0 | Foundation: deps, tokens, fontes, assets, primitivos, `/dev/design-system/`, dark mode | `tailwind build` sem erros; página dev renderiza primitivos; `design_system.spec.ts` verde; axe sem violações críticas; 8 E2E antigos verdes |
| R1 | Shell: base, sidebar, topbar, breadcrumbs, RBAC visual, hx-boost | sidebar mobile funcional; breadcrumbs em todas as páginas; E2E de navegação (5 páginas) |
| R2 | Dashboard executivo: 6 KPIs por pilar, chart financeiro, heatmap, destaques, avisos, drawer | dados reais do seed; filtro de período via HTMX; charts responsivos |
| R3 | Operacional: filtros de indicadores, form com validação, kanban, timeline, modal de devolução, CSV preview | fluxo Rascunho→Aprovado E2E; período fechado bloqueia; toasts; ARIA |
| R4 | CRM AT e Talentos: funil, pipeline, renovações, organograma, cards, busca por skill | dados reais do seed; hierarquia; busca funcional |
| R5 | Relatório A4 + Auditoria: capa, seções, gráficos de impressão, timeline/paginação | PDF A4 sem quebras; auditoria com 100+ eventos paginados |
| R6 | Polish: skeletons, tooltips, animações, view transitions, a11y, bundle | Lighthouse ≥ 90/95/95; teclado em todas as telas; screen reader nos KPIs |

## 11. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Conflito de loaders cotton × template-partials | validar no início do R0; fallback `SimpleAppConfig` + `wrap_loaders` |
| Classes dinâmicas não detectadas pelo Tailwind | mapas literais de classes; nunca interpolar strings |
| `W001` (source CSS dentro de `static/`) | source em `assets/styles/`, fora de `STATICFILES_DIRS` |
| Fontes licenciadas fora do git | fallback documentado; conversão local via script |
| Panton trial | registro de risco; local-only; substituição documentada |
| Lighthouse sem Chrome local | axe-core como gate primário; Lighthouse tentado e reportado |
| Python 3.14 | libs suportam 3.10+; validado na instalação do R0 |

## 12. Decisões abertas (para loops futuros)

- Kanban com drag-and-drop: R3 começa com botões acessíveis; drag como
  progressive enhancement se houver tempo/benefício.
- Gráficos no relatório: Chart.js com `animation:false` no R5; SVG server-side
  apenas se a impressão apresentar falhas.
- Publicação/deploy: fora do escopo deste retrofit (fontes e trial impedem
  deploy com marca; documentado).
