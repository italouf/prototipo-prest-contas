# Navbar Executiva LOOP 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extinguir a sidebar lateral e entregar navbar horizontal escura fixa, com os mesmos links/guards RBAC e navegação HTMX-boosted, sem tocar em backend.

**Architecture:** Criar `templates/components/layout/navbar.html` (Cotton) fundindo sidebar+topbar em header sticky de 2 linhas (`bg-quiin-navy`); religar `templates/base.html`; limpar CSS lateral em `assets/styles/input.css`; atualizar testes de shell. Nenhuma view/model/permission alterada.

**Tech Stack:** Django 5.2 + django-cotton 2.7.2 (`COTTON_DIR="components"`, kebab-case) + django-tailwind-cli 4.3.3 (Tailwind v4 CSS-first) + django-htmx + Alpine.js 3 vendorizado + Playwright.

**Spec:** `docs/superpowers/specs/2026-09-16-navbar-design.md`

## Global Constraints

- BACKEND INTACTO no LOOP 1: nenhuma view, model, queryset, permission ou regra de negócio alterada; só templates/CSS/testes de shell.
- Paleta QuIIN sagrada: só tokens de `assets/styles/theme.css` (`quiin-navy #04047E`, `deep-purple`, `royal`, `blue`, `sky`, `quantum-green`, `violet`, `mist`, `surface`, `text`, `pillar-*`, `status-*`); nenhuma cor nova.
- Fontes: só Montserrat + JetBrains Mono self-hosted (`static/css/fonts.css`); nenhum Google Fonts/CDN; Whitenoise deve continuar verde.
- HTMX + Alpine first: links com `hx-boost + hx-target="#main" + hx-select="#main" + hx-swap="innerHTML show:top" + hx-push-url`; dropdowns/toggles em Alpine, sem reload.
- UTF-8: NUNCA editar arquivos com round-trip PowerShell `Get-Content -Raw` + `WriteAllText` (corrompe acentos, incidente R6); usar ferramenta de edit nativa UTF-8.
- Python: `.venv/Scripts/python.exe manage.py ...`; shell: Windows PowerShell 5.1.

---

### Task 1: Criar componente `layout/navbar`

**Files:**
- Create: `templates/components/layout/navbar.html`
- Test: `apps/core/tests_frontend.py` (classe `ShellTestes`, só leitura nesta task)
- Reference: `templates/components/layout/sidebar.html:1-82`, `templates/components/layout/topbar.html:1-53`, `apps/core/context_processors.py:8-60`, `mockup/quiin-dashboard 1.html:280-329` (só layout, não copiar cores/fontes/JS)

**Interfaces:**
- Consumes: contexto `nav` (`pilares_nav`, `periodo_aberto_nav`, `ultimo_periodo_nav`, `periodos_nav`, `pendencias_nav`, `total_pendencias`, `papel`, `pode_lancar`, `pode_aprovar`, `pode_importar_financeiro`, `pode_ver_auditoria`); `user.nome_exibicao`; rotas `core:dashboard`, `core:pilar`, `core:busca`, `entries:formulario`, `entries:aprovacao`, `finance:consolidado`, `talentos:organograma`, `crm_at:funil`, `reports:mensal`, `audit:lista`, `/admin/`.
- Produces: `<c-layout.navbar />` com `data-testid="navbar"`, `data-testid="navbar-toggle"`, `data-testid="busca-global"`, `data-testid="period-selector"`, `data-testid="papel-badge"`, `data-testid="dark-toggle"` (mesmos testids da topbar para não quebrar E2E de busca/período/papel).

- [ ] **Step 1: Escrever teste falhando (navbar existe, sidebar não)**

```python
# Adicionar TEMPORARIAMENTE em apps/core/tests_frontend.py não é nesta task.
# Nesta task, só criar o arquivo e validar via teste manual Django shell:
# O teste formal entra na Task 4. Aqui o gate é: arquivo existe e usa guards iguais à sidebar.
```

> Nota TDD: o teste automatizado formal está na Task 4 para não bloquear a criação do componente. O gate desta task é revisão do arquivo + `python manage.py check`.

- [ ] **Step 2: Criar `templates/components/layout/navbar.html` com o conteúdo exato abaixo**

```html
<header data-testid="navbar" class="sticky top-0 z-40 bg-quiin-navy text-white shadow-md"
        x-data="{ mobileAberto: false, pilaresAberto: false, sistemaAberto: false }"
        @keydown.escape.window="mobileAberto = false; pilaresAberto = false; sistemaAberto = false">
  <div class="mx-auto w-full max-w-[1440px] px-4 lg:px-8">
    <div class="flex items-center gap-3 py-2.5">
      <a href="{% url 'core:dashboard' %}" data-nav-link class="flex items-center gap-2 text-white">
        <span class="brand-mark">Q</span>
        <span class="font-display text-base font-bold">Gestão QuIIN</span>
      </a>
      <span class="hidden text-[11px] uppercase tracking-widest text-white/60 xl:inline">Portal QuIIN</span>
      <button type="button" data-testid="navbar-toggle" class="ml-auto rounded-md p-2 text-white/80 hover:bg-white/10 hover:text-white lg:hidden"
              @click="mobileAberto = !mobileAberto" :aria-expanded="mobileAberto" aria-controls="navbar-tabs" aria-label="Abrir menu">
        <c-ui.icon name="menu" size="18" />
      </button>
      <form method="get" action="{% url 'core:busca' %}" hx-get="{% url 'core:busca' %}" hx-target="#busca-resultados" hx-trigger="input changed delay:300ms, submit"
            class="relative ml-auto hidden w-full max-w-sm md:block" x-data="{ focado: false }" @focusin="focado = true" @focusout="setTimeout(() => focado = false, 200)">
        <label for="busca-global" class="sr-only">Busca global</label>
        <input id="busca-global" type="search" name="q" data-testid="busca-global" placeholder="Buscar indicador, empresa, talento…"
               class="w-full rounded-md border border-white/20 bg-white/10 px-3 py-2 pl-9 text-sm text-white placeholder:text-white/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-focus/60">
        <span class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-white/60"><c-ui.icon name="search" size="16" /></span>
        <div id="busca-resultados" x-show="focado" x-cloak class="absolute left-0 right-0 top-full z-40 mt-1 max-h-80 overflow-y-auto rounded-lg border border-border bg-surface-2 text-text shadow-lg"></div>
      </form>
      <form method="get" action="{{ request.path }}" class="hidden items-center gap-2 md:flex">
        <label for="periodo-global" class="sr-only">Período de competência</label>
        <select id="periodo-global" name="periodo" data-testid="period-selector" onchange="this.form.submit()"
                class="rounded-md border border-white/20 bg-white/10 px-2 py-2 text-sm text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-focus/60">
          {% for p in periodos_nav %}
          <option value="{{ p.competencia|date:'Y-m-d' }}" class="text-text" {% if request.GET.periodo == p.competencia|date:'Y-m-d' %}selected{% elif not request.GET.periodo and periodo_aberto_nav and p.pk == periodo_aberto_nav.pk %}selected{% elif not request.GET.periodo and not periodo_aberto_nav and p.pk == ultimo_periodo_nav.pk %}selected{% endif %}>
            {{ p.rotulo }} — {{ p.get_status_display }}
          </option>
          {% endfor %}
        </select>
      </form>
      <div class="hidden items-center gap-2 lg:flex">
        <c-ui.badge papel="{{ papel }}" class="hidden sm:inline-flex" data-testid="papel-badge">{{ papel }}</c-ui.badge>
        <span class="hidden text-sm font-medium xl:inline">{{ user.nome_exibicao }}</span>
        <button type="button" data-testid="dark-toggle" aria-label="Alternar tema" title="Alternar tema"
                class="inline-flex h-9 w-9 items-center justify-center rounded-md border border-white/20 bg-white/10 text-white"
                x-data="{ escuro: document.documentElement.classList.contains('dark') }"
                @click="escuro = !escuro; document.documentElement.classList.toggle('dark', escuro); localStorage.setItem('quiin-theme', escuro ? 'dark' : 'light')" :aria-pressed="escuro">
          <span x-show="!escuro"><c-ui.icon name="sun" size="18" /></span>
          <span x-show="escuro" x-cloak><c-ui.icon name="moon" size="18" /></span>
        </button>
        <form method="post" action="{% url 'accounts:logout' %}">
          {% csrf_token %}
          <button type="submit" aria-label="Sair" title="Sair" class="inline-flex h-9 w-9 items-center justify-center rounded-md border border-white/20 bg-white/10 text-white hover:bg-white/20">
            <c-ui.icon name="log-out" size="18" />
          </button>
        </form>
      </div>
    </div>
    <nav id="navbar-tabs" aria-label="Navegação principal" class="hidden lg:block"
         hx-boost="true" hx-target="#main" hx-select="#main" hx-swap="innerHTML show:top" hx-push-url="true" hx-indicator="#progresso">
      <ul class="flex items-center gap-1 pb-2">
        <li><a href="{% url 'core:dashboard' %}" data-nav-link class="nav-item">Geral</a></li>
        <li class="relative" @click.away="pilaresAberto = false">
          <button type="button" @click="pilaresAberto = !pilaresAberto" :aria-expanded="pilaresAberto" aria-haspopup="true" class="nav-item">
            Pilares do QuIIN <c-ui.icon name="chevron-down" size="14" />
          </button>
          <ul x-show="pilaresAberto" x-cloak role="menu" class="absolute left-0 top-full z-50 mt-1 w-64 rounded-lg border border-border bg-surface-2 p-1 text-text shadow-lg">
            {% for pilar in pilares_nav %}
            <li role="none"><a role="menuitem" href="{% url 'core:pilar' pilar.pk %}" data-nav-link class="flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-quiin-mist/40">{{ pilar.nome }}{% if pendencias_nav %}{% for pid, qtd in pendencias_nav.items %}{% if pid == pilar.pk %}<span class="ml-auto rounded-full bg-quiin-sky px-2 py-0.5 text-xs font-semibold text-white">{{ qtd }}</span>{% endif %}{% endfor %}{% endif %}</a></li>
            {% empty %}<li class="px-3 py-2 text-sm text-text-muted">Sem pilares visíveis.</li>{% endfor %}
          </ul>
        </li>
        {% if pode_lancar and periodo_aberto_nav and pilares_nav %}
        <li><a href="{% url 'entries:formulario' periodo_aberto_nav.pk pilares_nav.0.pk %}" data-nav-link class="nav-item">Lançamentos</a></li>
        {% endif %}
        {% if pode_aprovar and periodo_aberto_nav %}
        <li><a href="{% url 'entries:aprovacao' periodo_aberto_nav.pk %}" data-nav-link class="nav-item">Aprovações{% if total_pendencias %}<span class="ml-1 rounded-full bg-quiin-quantum-green px-2 py-0.5 text-xs font-semibold text-quiin-deep-purple">{{ total_pendencias }}</span>{% endif %}</a></li>
        {% endif %}
        {% if pode_lancar or pode_aprovar %}
        <li><a href="{% url 'talentos:organograma' %}" data-nav-link class="nav-item">Talentos</a></li>
        <li><a href="{% url 'crm_at:funil' %}" data-nav-link class="nav-item">Gestão de Associados</a></li>
        {% endif %}
        <li class="relative" @click.away="sistemaAberto = false">
          <button type="button" @click="sistemaAberto = !sistemaAberto" :aria-expanded="sistemaAberto" aria-haspopup="true" class="nav-item">Sistema <c-ui.icon name="chevron-down" size="14" /></button>
          <ul x-show="sistemaAberto" x-cloak role="menu" class="absolute left-0 top-full z-50 mt-1 w-56 rounded-lg border border-border bg-surface-2 p-1 text-text shadow-lg">
            {% if ultimo_periodo_nav %}<li role="none"><a role="menuitem" href="{% url 'reports:mensal' ultimo_periodo_nav.pk %}" data-nav-link class="block rounded-md px-3 py-2 text-sm hover:bg-quiin-mist/40">Relatório Mensal</a></li>{% endif %}
            {% if pode_importar_financeiro %}<li role="none"><a role="menuitem" href="{% url 'finance:consolidado' %}" data-nav-link class="block rounded-md px-3 py-2 text-sm hover:bg-quiin-mist/40">Financeiro</a></li>{% endif %}
            {% if pode_ver_auditoria %}<li role="none"><a role="menuitem" href="{% url 'audit:lista' %}" data-nav-link class="block rounded-md px-3 py-2 text-sm hover:bg-quiin-mist/40">Auditoria</a></li>{% endif %}
            {% if papel == 'Master' or papel == 'Admin' %}<li role="none"><a role="menuitem" href="/admin/" data-nav-link class="block rounded-md px-3 py-2 text-sm hover:bg-quiin-mist/40">Admin</a></li>{% endif %}
          </ul>
        </li>
      </ul>
    </nav>
    <div x-show="mobileAberto" x-cloak id="navbar-mobile" class="pb-3 lg:hidden"
         hx-boost="true" hx-target="#main" hx-select="#main" hx-swap="innerHTML show:top" hx-push-url="true" hx-indicator="#progresso" @click="mobileAberto = false">
      <ul class="space-y-1">
        <li><a href="{% url 'core:dashboard' %}" data-nav-link class="nav-item">Geral</a></li>
        {% for pilar in pilares_nav %}<li><a href="{% url 'core:pilar' pilar.pk %}" data-nav-link class="nav-item">{{ pilar.nome }}</a></li>{% endfor %}
        {% if pode_lancar and periodo_aberto_nav and pilares_nav %}<li><a href="{% url 'entries:formulario' periodo_aberto_nav.pk pilares_nav.0.pk %}" data-nav-link class="nav-item">Lançamentos</a></li>{% endif %}
        {% if pode_aprovar and periodo_aberto_nav %}<li><a href="{% url 'entries:aprovacao' periodo_aberto_nav.pk %}" data-nav-link class="nav-item">Aprovações</a></li>{% endif %}
        {% if pode_lancar or pode_aprovar %}<li><a href="{% url 'talentos:organograma' %}" data-nav-link class="nav-item">Talentos</a></li><li><a href="{% url 'crm_at:funil' %}" data-nav-link class="nav-item">Gestão de Associados</a></li>{% endif %}
        {% if ultimo_periodo_nav %}<li><a href="{% url 'reports:mensal' ultimo_periodo_nav.pk %}" data-nav-link class="nav-item">Relatório Mensal</a></li>{% endif %}
        {% if pode_ver_auditoria %}<li><a href="{% url 'audit:lista' %}" data-nav-link class="nav-item">Auditoria</a></li>{% endif %}
        {% if papel == 'Master' or papel == 'Admin' %}<li><a href="/admin/" data-nav-link class="nav-item">Admin</a></li>{% endif %}
      </ul>
    </div>
  </div>
</header>
```

- [ ] **Step 3: Rodar check do Django**

Run: `.venv/Scripts/python.exe manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 4: Commit**

```bash
git add templates/components/layout/navbar.html
git commit -m "feat(nav): cria navbar executiva escura (Cotton, Alpine, HTMX-boost)"
```

### Task 2: Religar `base.html` na navbar

**Files:**
- Modify: `templates/base.html:26-70`
- Reference: `templates/base.html:1-89`

**Interfaces:**
- Consumes: `<c-layout.navbar />` da Task 1.
- Produces: shell sem sidebar, com skip-link, `#progresso`, `#toasts`, `#skeleton-global`, `#main`, footer intactos.

- [ ] **Step 1: Editar `templates/base.html` — trocar o wrapper lateral por navbar**

Old (linhas 26-35):
```html
<div x-data="{ aberto: false, recolhida: localStorage.getItem('quiin-sidebar') === 'recolhida' }"
     :data-aberto="aberto" :data-recolhida="recolhida"
     class="min-h-screen {% if user.is_authenticated %}lg:flex{% endif %}">
  {% if user.is_authenticated %}
  <div x-show="aberto" x-cloak @click="aberto = false" class="fixed inset-0 z-30 bg-black/50 lg:hidden"></div>
  <c-layout.sidebar />
  {% endif %}
  <div class="{% if user.is_authenticated %}min-w-0 flex-1{% endif %}">
    {% if user.is_authenticated %}
    <c-layout.topbar />
```

New:
```html
<div class="min-h-screen">
  {% if user.is_authenticated %}
  <c-layout.navbar />
  {% endif %}
  <div class="{% if user.is_authenticated %}min-w-0 flex-1{% endif %}">
    {% if user.is_authenticated %}
```

Manter o restante (progresso, toasts, skeleton, main, footer, scripts, `quiinAtivarNav`) exatamente igual. Fechar uma `</div>` a menos: conferir que o bloco termina com `</div>` único antes dos `<script>`. Não mexer no bloco `{% if not user.is_authenticated %}data-testid="login-shell"`.

- [ ] **Step 2: Verificar que `sidebar`/`topbar` não são mais referenciados no base**

Run: `python -c "import pathlib; t=pathlib.Path('templates/base.html').read_text(encoding='utf-8'); assert 'layout.sidebar' not in t and 'layout.topbar' not in t and 'layout.navbar' in t; print('base ok')"`
Expected: `base ok`

- [ ] **Step 3: Commit**

```bash
git add templates/base.html
git commit -m "feat(nav): base usa navbar, remove sidebar e wrapper lateral"
```

### Task 3: Limpar CSS lateral

**Files:**
- Modify: `assets/styles/input.css:51-60,184-212`
- Reference: `assets/styles/theme.css` (tokens)

**Interfaces:**
- Consumes: classes `.nav-item`, `.nav-item-ativo` existentes (manter).
- Produces: sem `.sidebar`, sem `[data-recolhida]`/`[data-aberto]`; print oculta navbar.

- [ ] **Step 1: Remover bloco colapso desktop (linhas 184-198) e drawer mobile (201-212)**

Substituir por:
```css
/* Navbar executiva (LOOP 1): header escuro sticky; dropdowns usam x-cloak + bg-surface-2. */
#navbar-tabs .nav-item[aria-current="page"],
#navbar-mobile .nav-item[aria-current="page"] {
  background-color: rgb(255 255 255 / 0.14);
  color: #fff;
}
```

- [ ] **Step 2: Atualizar `@media print` — trocar `.sidebar` por `[data-testid="navbar"]`**

Old: `.topbar, .sidebar, .footer,` → New: `.topbar, [data-testid="navbar"], .footer,`

- [ ] **Step 3: Rebuild Tailwind + checar tokens**

Run: `.venv/Scripts/python.exe manage.py tailwind build`
Expected: build OK; `static/css/tailwind.css` contém `--color-quiin-navy` e `#04047e`.

- [ ] **Step 4: Commit**

```bash
git add assets/styles/input.css static/css/tailwind.css
git commit -m "style(nav): remove CSS da sidebar, navbar escura + print"
```

### Task 4: Atualizar testes de shell (Django + E2E)

**Files:**
- Modify: `apps/core/tests_frontend.py:135-156`
- Modify: `tests/e2e/shell.spec.ts:10-43`
- Test: `apps/core/tests_frontend.py`, `tests/e2e/shell.spec.ts`

**Interfaces:**
- Consumes: navbar da Task 1 com testids preservados.
- Produces: suite verde sem referência a `sidebar`.

- [ ] **Step 1: Escrever o teste Django falhando primeiro (atualizar `ShellTestes`)**

```python
def test_shell_autenticado_tem_navbar_sem_sidebar(self):
    self.client.force_login(self.erica)
    resposta = self.client.get("/")
    self.assertContains(resposta, 'data-testid="navbar"')
    self.assertContains(resposta, 'data-testid="navbar-toggle"')
    self.assertContains(resposta, 'data-testid="dark-toggle"')
    self.assertNotContains(resposta, 'data-testid="sidebar"')
    self.assertNotContains(resposta, 'data-testid="login-shell"')
```

Substituir `test_shell_autenticado_tem_sidebar_e_topbar` por este; em `test_pagina_publica_nao_tem_sidebar` trocar asserts para `navbar`; manter breadcrumbs.

- [ ] **Step 2: Rodar para ver falhar antes do fix (se ainda houver sidebar) / passar após Tasks 1-2**

Run: `.venv/Scripts/python.exe manage.py test apps.core.tests_frontend.ShellTestes -v 2`
Expected: PASS após Tasks 1–2 (se FAIL com `sidebar` ausente, significa que a Task 2 não foi aplicada — voltar).

- [ ] **Step 3: Atualizar `tests/e2e/shell.spec.ts` — trocar `sidebar` por `navbar`**

```ts
test('navega entre 5 paginas pela navbar com boost', async ({ page }) => {
  await login(page);
  await expect(page.getByTestId('navbar')).toBeVisible();
  // Lançamentos/Aprovações podem estar em dropdown mobile; usar navbar como escopo:
  await page.getByTestId('navbar').getByRole('link', { name: /^Geral/ }).click();
  await expect(page.getByRole('heading', { name: /dashboard executivo/i })).toBeVisible();
});

test('navbar mobile abre, navega e fecha', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  await page.getByTestId('navbar-toggle').click();
  await page.getByTestId('navbar').getByRole('link', { name: /Auditoria/ }).click();
  await expect(page.getByRole('heading', { name: /auditoria/i })).toBeVisible();
});
```

Manter os testes de busca global, período e papel (testids inalterados). Não fixar PKs (`/lancamentos/2/1/`) — usar regex de URL como já existe ou navegar via link.

- [ ] **Step 4: Commit**

```bash
git add apps/core/tests_frontend.py tests/e2e/shell.spec.ts
git commit -m "test(nav): shell espera navbar, remove sidebar"
```

### Task 5: Validação final LOOP 1

**Files:**
- Test: full suite + Playwright + Axe + screenshots

- [ ] **Step 1: Django check + collectstatic**

Run: `.venv/Scripts/python.exe manage.py check`
Expected: no issues.

Run: `.venv/Scripts/python.exe manage.py collectstatic --no-input --clear`
Expected: saída sem erro de manifest/Whitenoise.

- [ ] **Step 2: Suite Django completa**

Run: `.venv/Scripts/python.exe manage.py test`
Expected: todos OK (baseline ~190 testes R7 + ajustes ShellTestes).

- [ ] **Step 3: Playwright shell + a11y**

Run: `npx playwright test shell --reporter=list`
Expected: verde.

Run: `npx playwright test a11y_r6 --reporter=list`
Expected: 0 violações critical/serious na home com navbar.

- [ ] **Step 4: Screenshots desktop + mobile (evidência)**

Run: `npx playwright test screenshots --reporter=list`
Expected: `test-results/` com navbar visível; conferir manualmente 1440px e 390px, dropdown Pilares/Sistema abre com teclado (Tab + Enter + Escape).

- [ ] **Step 5: Commit de evidência (só se houver artefato versionado)**

```bash
git status --short
```

Se só `test-results/` ignorado, nenhum commit. Gate LOOP 1: sidebar sumiu, navbar escura com 7 itens + dropdowns Alpine, Tab/ARIA ok, `collectstatic` verde. Aguardar validação humana antes do LOOP 2.

## Self-Review

1. Spec coverage: §4.1 (navbar guards/RBAC/HTMX) → Tasks 1–2; §4.3 print/CSS → Task 3; §5 a11y/bundle → Task 5; §6 comandos → Task 5. Escopo/Período/Talentos (spec §7) propositalmente FORA deste plano (Loops 2–4).
2. Placeholder scan: nenhum TBD/TODO; todos os blocos de código completos; comandos com executável exato `.venv/Scripts/python.exe`; sem “similar à Task N”.
3. Type consistency: testids (`navbar`, `navbar-toggle`, `busca-global`, `period-selector`, `papel-badge`, `dark-toggle`) idênticos entre Tasks 1, 4, 5; rotas Django com namespace exato; `hx-*` idênticos sidebar→navbar.
