# Portal QuIIN — prototipo-prest-contas

Branch ativo: `new-retrofit-mb`.

Portal Django local de gestao e prestacao de contas (dados ficticios de demonstracao).

## 1. Navegacao (navbar, sem sidebar)

Sidebar removida do shell autenticado. `templates/base.html` renderiza apenas
`c-layout.navbar` (`templates/components/layout/navbar.html`).
`templates/components/layout/sidebar.html` e `topbar.html` seguem no repo como
legado deferido, sem uso no shell.

Navbar escura (`bg-quiin-navy`, `text-white`), sticky, 2 linhas, `max-w-[1440px]`:

- Linha 1: marca QuIIN, toggle mobile, busca global, toggle Operacional|Financeiro,
  seletor de periodo, perfil real, alternador de tema, logout.
- Linha 2 (`#navbar-tabs`, desktop `lg+`): Geral, dropdown Pilares do QuIIN,
  Lancamentos, Aprovacoes, Talentos, Gestao de Associados, dropdown Sistema.
  Dropdowns via Alpine (`x-show` + `x-cloak`, `aria-haspopup`, `aria-expanded`,
  fecha com Escape/click-away/`htmx:afterSwap`).
- Mobile (`#navbar-mobile`, `<lg`): lista plana com todos os destinos + papel e
  periodo; abre/fecha via `navbar-toggle` (`aria-expanded`, `aria-controls`).
- Navegacao com `hx-boost` (`hx-target="#main"`, `hx-select="#main"`,
  `hx-swap="innerHTML show:top"`, `hx-push-url="true"`); aba ativa via
  `quiinAtivarNav()` (`nav-item-ativo` + `aria-current="page"`, CSS em
  `assets/styles/input.css`).

Testids principais: `navbar`, `navbar-toggle`, `busca-global`, `busca-lista`,
`scope-toggle`, `scope-operacional`, `scope-financeiro`, `period-selector`,
`period-selector-dashboard`, `user-profile`, `papel-badge`, `breadcrumbs`,
`page-dashboard`, `page-pilar`, `page-talentos`, `page-funil`, `page-auditoria`,
`escopo-operacional`, `escopo-financeiro`, `drawer`.

## 2. Filtros globais

- Toggle Operacional|Financeiro (`templates/components/ui/scope_toggle.html`):
  links aditivos `?escopo=` com default `operacional` (invalido cai para
  `operacional` em `apps/core/views.py:dashboard`). No dashboard troca via HTMX
  (`hx-target="#dashboard-conteudo"`, `hx-push-url`) com `aria-current="page"`
  no ativo (`bg-white text-quiin-navy`). Sync OOB via
  `#scope-toggle-wrap`/`#scope-toggle-oob-template` em `templates/home.html`.
  Fora do dashboard faz fallback para full navigation ate `/?escopo=...`
  (`onclick` quando `#dashboard-conteudo` nao existe). Secoes alternadas em
  `escopo-operacional` / `escopo-financeiro`.
- Seletor mensal (`templates/components/ui/period_selector.html` +
  `#period-selector-dashboard` no dashboard): query `?periodo=YYYY-MM-DD`.
  Preservacao cruzada: seletor carrega `escopo` hidden; toggle carrega
  `periodo`; form do dashboard carrega `escopo` hidden. Contexto global em
  `apps/core/context_processors.py:nav` (`periodos_nav`, `periodo_aberto_nav`,
  `ultimo_periodo_nav`, `pilares_nav`, `papel`, permissoes).
- Perfil real (`templates/components/ui/user_profile.html`): `nome • papel`
  (`title="{{ nome }} • {{ papel }}"`), inicial, `user.nome_exibicao` +
  `papel-badge` (Master/Admin/PontoFocal/Lideranca/Auditor).

## 3. Fontes e CSS

- Fontes 100% self-hosted: Montserrat Variable + JetBrains Mono
  (Regular/Medium/Bold) em `static/fonts/`, declaradas em
  `static/css/fonts.css`, geradas por `scripts/convert_fonts.py`.
- Tokens em `assets/styles/theme.css` (Tailwind v4 CSS-first:
  `quiin-*`, `surface*`, `text*`, `status-*`, `pillar-*`, `font-display/sans/mono`).
  Entrada em `assets/styles/input.css`, saida em `static/css/tailwind.css`.
- Sem referencia a Panton/Myriad/CDN/Google Fonts no portal
  (`static/css/fonts.css`, `assets/styles/theme.css` e `templates/` nao citam;
  `font/` guarda fontes originais e `static/fonts/myriad-pro/` segue ignorado
  pelo git sem uso; restos em `relatorio.html`/`mockup/` sao artefatos fora do app).
- Comandos:

  ```powershell
  .venv/Scripts/python.exe manage.py tailwind build
  .venv/Scripts/python.exe manage.py collectstatic --clear --noinput
  ```

## 4. Validacao

```powershell
.venv/Scripts/python.exe manage.py check
.venv/Scripts/python.exe manage.py tailwind build   # se CSS em assets/ tocado
.venv/Scripts/python.exe manage.py collectstatic --clear --noinput
.venv/Scripts/python.exe manage.py test --parallel 4
npx playwright test shell crm_talentos_r4 a11y_r6 fixes_r7 reports_r5
```

A11y: `tests/e2e/a11y_r6.spec.ts` roda axe-core (`wcag2a`/`wcag2aa`) em 12 rotas e
falha apenas em `critical`/`serious`. E2E shell cobre navbar/boost, 5 abas
(Geral, Pilares via dropdown sem PK hardcoded, Talentos, Gestao de Associados,
Sistema->Auditoria), mobile, breadcrumbs, busca, periodo, papel e toggle.
