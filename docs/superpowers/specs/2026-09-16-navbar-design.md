# Migração Sidebar → Navbar Executiva — Design (spec)

Data: 2026-09-16
Branch atual: `new-retrofit-mb` (spec original citava `feat-retrofit-visual`; alinhar alvo antes do merge)
Status: aprovado em conversa (navbar escura `bg-quiin-navy`); execução em 4 LOOPS, com validação do LOOP 1 antes do LOOP 2
Escopo: front-end (Django Templates + Cotton + HTMX + Alpine). Regras de ouro: backend intacto no Loop 1, paleta QuIIN sagrada, sem fontes CDN, HTMX+Alpine first.
Referência visual: `mockup/quiin-dashboard 1.html` (4 tabs estáticas, JS vanilla, Chart.js CDN, fontes Google) — usar como referência de layout, NÃO como arquitetura.

## 1. Contexto e objetivo

O shell atual (`templates/base.html`) usa sidebar lateral colapsável (`templates/components/layout/sidebar.html`) + topbar (`templates/components/layout/topbar.html`), com navegação `hx-boost + hx-target="#main" + hx-select="#main" + hx-push-url`. O objetivo é migrar para navbar horizontal executiva fixa no topo, no padrão do mockup (brand + controles + tabs), preservando RBAC, deep-linking, `head-support`, toasts, skeleton e dark mode.

Decisões travadas em conversa:
- Mockup em `mockup/quiin-dashboard 1.html` (não `relatorio.html`).
- Escopo Operacional/Financeiro: permitido toque mínimo aditivo na view do dashboard (`?escopo=`, sem mudar RBAC/queryset base) — LOOP 2.
- Período: manter seletor mensal `?periodo=YYYY-MM-DD` (`periodos_nav`); NÃO adotar Ano 1–4 / Total 42 meses do mockup.
- Talentos CLT vs Bolsistas: permitida migração de modelo (adicionar `vinculo`) — LOOP 3.
- Navbar escura `bg-quiin-navy` (reuso de `.nav-item`, melhor AA, menor diff).

## 2. Não-objetivos e invariantes (LOOP 1)

- Não alterar views, models, querysets, permissions, fluxo aprovação, fechamento período no LOOP 1. Mudança é só template + CSS + testes de shell.
- Não criar cores novas; usar `assets/styles/theme.css` (`quiin-navy`, `deep-purple`, `royal`, `blue`, `sky`, `quantum-green`, `violet`, `mist`, `surface`, `text`, `pillar-*`, `status-*`).
- Não reintroduzir Panton/Myriad Pro nem fontes CDN (Manrope/IBM Plex do mockup → Montserrat/JetBrains Mono self-hosted em `static/css/fonts.css`). Whitenoise continua.
- Não migrar para router client-side do mockup (`showView`); Django SSR + HTMX é a fonte da verdade.
- Não quebrar login (`login-shell` sem navbar) nem 403.

## 3. Mapeamento mockup → QuIIN (obrigatório)

| Mockup | QuIIN (adotar) | Motivo |
|---|---|---|
| `Manrope` / `IBM Plex Sans` | `Montserrat` (`--font-display`/`--font-sans`) | Pipeline fontes, sem CDN |
| `IBM Plex Mono` | `JetBrains Mono` (`--font-mono`, classe `.numerico`) | Idem |
| `--brand #2E3192` | `bg-quiin-navy #04047E` (navbar), `bg-quiin-deep-purple` nunca como fundo de tab ativa sem checar AA | Paleta sagrada |
| `--p-pdi #2a78d6` etc. | `pillar-pdi/formacao/startups/at/infra/outrasfontes` + `*-texto` | Tokens existentes |
| `select.yr Ano 1-4 + Total` | manter `select mensal periodos_nav` com estilo pill | Decisão período mensal |
| `role-note Diretoria` ilustrativo | `papel` + `user.nome_exibicao` reais do `nav` context | RBAC real |
| `tabnav` 4 tabs estáticas | 7 itens com guards RBAC (ver §4) | Não esconder Lançamentos/Aprovações/Sistema |
| `Chart.js CDN` | `static/js/vendor/chart.umd.js` + `static/js/charts.js` lazy | Vendorizado, sem CDN |
| `showView` JS | `hx-boost` no container nav | Preserva deep-linking/RBAC |

## 4. Arquitetura LOOP 1

### 4.1 Novos / alterados

- CRIAR `templates/components/layout/navbar.html` (Cotton, `COTTON_DIR="components"`, kebab-case):
  - `<header data-testid="navbar" class="sticky top-0 z-40 bg-quiin-navy text-white">`
  - Linha 1 (brand + controles herdados): logo `Q` + “Gestão QuIIN” (+ eyebrow curta opcional), busca global HTMX (mesmo `hx-get core:busca`), seletor mensal (`periodos_nav`, submit `?periodo=` no path atual), badge `papel`, nome usuário, dark-toggle, logout. Reuso literal de `topbar.html` adaptado para fundo escuro (inputs `bg-white/10 border-white/20 text-white placeholder:text-white/60`).
  - Linha 2 (tabs): `<nav aria-label="Navegação principal" hx-boost="true" hx-target="#main" hx-select="#main" hx-swap="innerHTML show:top" hx-push-url="true" hx-indicator="#progresso">` com:
    - `Geral` → `core:dashboard`
    - `Pilares ▾` (dropdown Alpine): `pilares_nav` com badges `pendencias_nav`; `aria-haspopup="true" aria-expanded`
    - `Lançamentos` → `entries:formulario periodo_aberto_nav.pk pilares_nav.0.pk` (só `{% if pode_lancar and periodo_aberto_nav and pilares_nav %}`)
    - `Aprovações` → `entries:aprovacao periodo_aberto_nav.pk` + badge `total_pendencias` (só `pode_aprovar`)
    - `Financeiro` NÃO é tab separada (é toggle do Loop 2); link `finance:consolidado` permanece acessível via Sistema ou tab? Decisão: manter `Financeiro` dentro de `Sistema ▾` no Loop 1 para não perder rota `pode_importar_financeiro` (mockup não tem; spec original pedia tab? manter acessível).
    - `Talentos` → `talentos:organograma` (só `pode_lancar ou pode_aprovar` como na sidebar — reavaliar: gestores/focais; liderança/auditor veem? manter mesma guard da sidebar: `{% if pode_lancar or pode_aprovar %}`)
    - `Gestão de Associados` → `crm_at:funil` (mesma guard; label nova, URL `funil/` mantida)
    - `Sistema ▾` (dropdown Alpine): Relatório Mensal (`reports:mensal ultimo_periodo_nav.pk`), Auditoria (`audit:lista` se `pode_ver_auditoria`), Admin `/admin/` (se Master/Admin)
  - Mobile: botão hamburger `lg:hidden` (`data-testid="navbar-toggle"`, `aria-expanded`, `aria-controls="navbar-tabs"`), painel vertical com mesmos links; dropdowns viram `<details>` ou accordion Alpine.
  - Estado Alpine no header: `x-data="{ mobileAberto:false, pilaresAberto:false, sistemaAberto:false }"`; fechar em `Escape` e em `htmx:afterSwap`; `@click.away` nos dropdowns.
- EDITAR `templates/base.html`: remover wrapper `x-data="{ aberto:false, recolhida... }"` + overlay mobile + `<c-layout.sidebar />`; inserir `<c-layout.navbar />` logo após skip-link; manter `#progresso`, `#toasts`, `#skeleton-global`, `<main id="main max-w-[1440px]">`, footer, scripts e `quiinAtivarNav` (estende para `[data-nav-link]` da navbar; `aria-current="page"`).
- EDITAR `assets/styles/input.css`: manter `.nav-item/.nav-item-ativo/.nav-secao` (fundo escuro); REMOVER bloco colapso `[data-recolhida]` + drawer `.sidebar translateX`; adicionar `.navbar-dropdown` se necessário (só tokens); print: trocar `.sidebar` por `[data-testid="navbar"]`.
- ATUALIZAR testes shell (não é backend): `apps/core/tests_frontend.py::ShellTestes` espera `sidebar` → trocar por `navbar`; E2E `tests/shell.spec.ts` idem.

### 4.2 Data flow

Nenhum endpoint novo. HTMX-boost preserva `GET página → swap #main → push-url → head-support atualiza <title>`. Badges vêm do `nav` context processor existente (1 query agregada por status). Sem `hx-vals` de escopo no Loop 1 (Loop 2).

### 4.3 Erro / edge cases

- Sem `periodo_aberto_nav`: Lançamentos/Aprovações ocultos (como hoje); Pilares/Sistema continuam.
- Sem `pilares_nav` (Liderança sem vínculo? na prática gestores veem todos): dropdown Pilares mostra “Sem pilares visíveis”.
- HTMX desabilitado/sem JS: links são `<a href>` reais → fallback SSR completo.
- Teclado/leitor: tabs são links nativos; dropdowns com `button[aria-expanded]` + lista `role="menu"` + itens `role="menuitem"`; `Escape` fecha e devolve foco ao botão.

## 5. Acessibilidade e performance

- Contraste: `text-white/70` sobre `bg-quiin-navy #04047E` já validado no R1 (`.nav-secao` AA); badge `quantum-green` com texto `deep-purple` mantido; dropdown em `bg-surface-2 text-text` (claro/escuro).
- `prefers-reduced-motion`: reutilizar `.anim-entrada` guard existente; view-transitions 0.18s mantidas.
- Bundle: +~2KB HTML, 0 JS novo (Alpine já global); CSS deve ficar <150KB gzip (gate `BundleTestes`).

## 6. Plano de validação LOOP 1

```text
python manage.py check
python manage.py tailwind build
python manage.py collectstatic --no-input --clear
python manage.py test
npx playwright test shell -–reporter=list
```

Axe em `/` autenticado (0 critical/serious), screenshots desktop 1440 + mobile 390 da navbar, Tab order manual, `collectstatic` verde. Critérios: sidebar sumiu (`data-testid="sidebar"` ausente), navbar presente, todos os links RBAC corretos, sem erro console.

## 7. Visão LOOPS 2–4 (não implementar agora)

- LOOP 2 (Topbar controls): `<c-ui.scope-toggle>` (Alpine + `hx-get core:dashboard hx-vals escopo` + `hx-target #dashboard-conteudo`) com mudança aditiva na `dashboard` view (ler `?escopo=operacional|financeiro`, default operacional; financeiro prioriza `cards/chart_mensal/chart_financeiro`, operacional prioriza KPIs/heatmap/destaques — sem mudar RBAC/fechamento); `<c-ui.period-selector>` mantém mensal com estilo pill; `<c-ui.user-profile>` com `papel` real. Gate: toggle sem reload, perfil RBAC correto.
- LOOP 3 (Talentos/Associados): Talentos — migração `Colaborador.vinculo` (`CLT/BOLSISTA/OUTRO` + migração + admin/form/filtro `?vinculo=` + abas Alpine/HTMX) + cards competências existentes + seção governança do mockup como bloco informativo (sem inventar nomes); Associados — mantém `funil.html` Kanban + KPIs `pipeline_open/renovacoes` + adiciona blocos informativos perfis (Demandante/Desenv./Parceiro) e tiers Bronze/Prata/Ouro/Diamante (estático, fonte Plano Anexo III), sem mudar `Oportunidade/Empresa`. Gate: views inalteradas salvo aditivo autorizado; só classes Tailwind/QuIIN.
- LOOP 4 (Polish/docs): WCAG AA, Playwright 5 abas, Lighthouse A11y ≥95, README (fim sidebar, filtros, fontes Montserrat/JetBrains + `tailwind build`), evidências `docs/retrofit/evidencias/navbar/`.

## 8. Self-review do spec

- Sem TBD/TODO: rotas, guards, arquivos e comandos explícitos. Risco `Financeiro` como tab vs item Sistema resolvido: fica em Sistema no Loop 1.
- Consistência: período mensal em todo o doc (não reintroduz Ano 1-4); escopo só no Loop 2; Talentos migração só Loop 3; backend intacto no Loop 1 respeitado.
- Escopo: Loop 1 cabe em um plano (3 arquivos + testes); Loops 2–4 separados com gates.
- Ambiguidade restante (1): eyebrow longa do mockup (“Centro de Competência EMBRAPII…”) na navbar escura pode quebrar em 1024px → decisão: eyebrow `hidden xl:block`, título curto sempre visível.
