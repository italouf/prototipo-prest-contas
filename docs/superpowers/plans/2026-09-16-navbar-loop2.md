# Topbar Controls LOOP 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar toggles globais Operacional|Financeiro + seletor mensal pill + perfil real na navbar escura, com troca de escopo via HTMX sem reload.

**Architecture:** View `dashboard` lê `?escopo=operacional|financeiro` (default `operacional`, sanitizado, aditivo, sem mudar RBAC/querysets); repassa `escopo` ao template; `home.html` marca seções com `data-testid` e renderiza ambos os blocos mas oculta o inativo via `hidden` server-side; navbar ganha `<c-ui.scope-toggle>` (HTMX) + `<c-ui.period-selector>` (pill) + `<c-ui.user-profile>` (papel real + nome). Charts.js re-inicializa via `htmx:afterSwap` existente.

**Tech Stack:** Django 5.2 + Cotton + HTMX 2 (hx-get/target/select/push-url) + Alpine 3 + Chart.js vendorizado + Playwright.

**Spec:** `docs/superpowers/specs/2026-09-16-navbar-design.md` (seção 7, LOOP 2)

## Global Constraints

- BACKEND ADITIVO MÍNIMO no Loop 2: só ler `?escopo=` na `dashboard` view e expor `escopo` no contexto; nenhuma mudança em models, permissions, fluxo aprovação, fechamento período, querysets base.
- Paleta QuIIN sagrada: só tokens de `assets/styles/theme.css`; nenhuma cor nova.
- Fontes: só Montserrat + JetBrains Mono self-hosted; sem CDN.
- HTMX + Alpine first: toggle via `hx-get` sem reload; dropdowns/estado via Alpine.
- UTF-8: NUNCA `Get-Content -Raw` + `WriteAllText` round-trip; usar edit nativo.
- Python: `.venv/Scripts/python.exe manage.py ...`; shell PowerShell 5.1.

---

### Task 1: Escopo aditivo na dashboard view + testes

**Files:**
- Modify: `apps/core/views.py:24-43,104-126`
- Test: `apps/core/tests.py` (adicionar classe `DashboardEscopoTestes`)

**Interfaces:**
- Consumes: `request.GET.get("escopo")`, `periodo_selecionado(request)`.
- Produces: contexto `escopo` (`"operacional"` default | `"financeiro"`), preservando todas as chaves existentes.

- [ ] **Step 1: Escrever teste falhando**

```python
class DashboardEscopoTestes(TestCase):
    def setUp(self):
        from datetime import date
        from apps.accounts.models import User
        from apps.core.permissions import adicionar_grupo, garantir_grupos
        from apps.periods.models import Periodo
        from apps.pillars.models import Pilar
        garantir_grupos()
        self.erica = adicionar_grupo(User.objects.create_user(username="erica_escopo", password="x"), "Master")
        self.pdi = Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=1)
        self.periodo = Periodo.objects.create(competencia=date(2026, 6, 1), status="ABERTO", aberto_por=self.erica)

    def test_default_operacional(self):
        self.client.force_login(self.erica)
        r = self.client.get(reverse("core:dashboard"))
        self.assertEqual(r.context["escopo"], "operacional")
        self.assertContains(r, 'data-testid="escopo-operacional"')

    def test_financeiro_valido(self):
        self.client.force_login(self.erica)
        r = self.client.get(reverse("core:dashboard"), {"escopo": "financeiro"})
        self.assertEqual(r.context["escopo"], "financeiro")
        self.assertContains(r, 'data-testid="escopo-financeiro"')

    def test_escopo_invalido_cai_para_operacional(self):
        self.client.force_login(self.erica)
        r = self.client.get(reverse("core:dashboard"), {"escopo": "injetado'"})
        self.assertEqual(r.context["escopo"], "operacional")
```

- [ ] **Step 2: Rodar para falhar**

Run: `.venv/Scripts/python.exe manage.py test apps.core.tests.DashboardEscopoTestes -v 2`
Expected: FAIL (`KeyError 'escopo'` / `AssertionError`).

- [ ] **Step 3: Implementação mínima em `apps/core/views.py`**

No início de `dashboard(request)`, após `periodo, periodos = periodo_selecionado(request)`:
```python
escopo = request.GET.get("escopo", "operacional")
if escopo not in ("operacional", "financeiro"):
    escopo = "operacional"
```
Adicionar `"escopo": escopo,` ao dict `contexto` inicial (junto a `destaque_pilar`). Nada mais na view: NÃO filtrar pilares, NÃO mudar `fin_ytd`, `kpis`, `heatmap`, `status_counts`, RBAC.

- [ ] **Step 4: Rodar para passar**

Run: `.venv/Scripts/python.exe manage.py test apps.core.tests.DashboardEscopoTestes -v 2`
Expected: PASS 3/3.

- [ ] **Step 5: Commit**

```bash
git add apps/core/views.py apps/core/tests.py
git commit -m "feat(dashboard): escopo operacional|financeiro aditivo (default operacional)"
```

### Task 2: Componentes navbar (scope-toggle + period-selector + user-profile)

**Files:**
- Create: `templates/components/ui/scope_toggle.html`
- Create: `templates/components/ui/period_selector.html`
- Create: `templates/components/ui/user_profile.html`
- Modify: `templates/components/layout/navbar.html:24-51`
- Test: `apps/core/tests_frontend.py` (classe `NavbarControlesTestes` nova)

**Interfaces:**
- Consumes: `escopo` (string), `periodos_nav`, `periodo_aberto_nav`, `ultimo_periodo_nav`, `request.GET.periodo`, `request.path`, `papel`, `user.nome_exibicao`.
- Produces: `data-testid="scope-toggle"`, `data-testid="scope-operacional"`, `data-testid="scope-financeiro"`, `data-testid="period-selector"` (único no desktop; mobile usa nota textual existente), `data-testid="user-profile"`, `data-testid="papel-badge"` preservado.

- [ ] **Step 1: Criar `templates/components/ui/scope_toggle.html`**

```html
<c-vars escopo="operacional" periodo="" />
<div data-testid="scope-toggle" role="group" aria-label="Tipo de visão"
     class="inline-flex items-center gap-0.5 rounded-full border border-white/20 bg-white/10 p-0.5">
  <a href="{% url 'core:dashboard' %}?{% if periodo %}periodo={{ periodo }}&{% endif %}escopo=operacional"
     data-testid="scope-operacional" aria-pressed="{% if escopo == 'operacional' %}true{% else %}false{% endif %}"
     hx-get="{% url 'core:dashboard' %}?{% if periodo %}periodo={{ periodo }}&{% endif %}escopo=operacional"
     hx-target="#dashboard-conteudo" hx-select="#dashboard-conteudo" hx-swap="outerHTML" hx-push-url="true" hx-indicator="#progresso"
     class="rounded-full px-3 py-1 text-xs font-semibold {% if escopo == 'operacional' %}bg-white text-quiin-navy{% else %}text-white/70 hover:text-white{% endif %}">Operacional</a>
  <a href="{% url 'core:dashboard' %}?{% if periodo %}periodo={{ periodo }}&{% endif %}escopo=financeiro"
     data-testid="scope-financeiro" aria-pressed="{% if escopo == 'financeiro' %}true{% else %}false{% endif %}"
     hx-get="{% url 'core:dashboard' %}?{% if periodo %}periodo={{ periodo }}&{% endif %}escopo=financeiro"
     hx-target="#dashboard-conteudo" hx-select="#dashboard-conteudo" hx-swap="outerHTML" hx-push-url="true" hx-indicator="#progresso"
     class="rounded-full px-3 py-1 text-xs font-semibold {% if escopo == 'financeiro' %}bg-white text-quiin-navy{% else %}text-white/70 hover:text-white{% endif %}">Financeiro</a>
</div>
```

Regras: sem JS próprio (HTMX faz swap); `aria-pressed` reflete `escopo`; preserva `?periodo=` atual; fallback SSR via `href` real.

- [ ] **Step 2: Criar `templates/components/ui/period_selector.html`**

```html
<c-vars periodos="" periodo_aberto="" ultimo_periodo="" atual="" action="/" />
<form method="get" action="{{ action }}" class="flex items-center gap-2">
  <label for="periodo-global" class="sr-only">Período de competência</label>
  <select id="periodo-global" name="periodo" data-testid="period-selector" onchange="this.form.submit()"
          class="w-[6rem] rounded-full border border-white/20 bg-white/10 px-2 py-1.5 text-xs font-semibold text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-focus/60 sm:w-auto sm:px-3 sm:text-sm">
    {% for p in periodos %}
    <option value="{{ p.competencia|date:'Y-m-d' }}" class="text-text" {% if atual == p.competencia|date:'Y-m-d' %}selected{% elif not atual and periodo_aberto and p.pk == periodo_aberto.pk %}selected{% elif not atual and not periodo_aberto and p.pk == ultimo_periodo.pk %}selected{% endif %}>{{ p.rotulo }} — {{ p.get_status_display }}</option>
    {% endfor %}
  </select>
</form>
```

Pill `rounded-full` (mockup `select.yr`), mesma lógica de seleção da navbar atual, sem Ano 1-4.

- [ ] **Step 3: Criar `templates/components/ui/user_profile.html`**

```html
<c-vars papel="" nome="" />
<span data-testid="user-profile" title="{{ nome }} • {{ papel }}" class="hidden items-center gap-2 sm:flex">
  <span aria-hidden="true" class="inline-flex h-8 w-8 items-center justify-center rounded-full bg-white/15 text-xs font-bold text-white">{{ nome|default:"?"|slice:":1"|upper }}</span>
  <span class="hidden leading-tight xl:block">
    <span class="block max-w-[10rem] truncate text-sm font-semibold text-white">{{ nome }}</span>
    <span data-testid="papel-badge" class="block text-[11px] font-medium uppercase tracking-wide text-white/70">{{ papel }}</span>
  </span>
  <span data-testid="papel-badge-mobile" class="sr-only">{{ papel }}</span>
</span>
```

ATENÇÃO testid: manter UM `data-testid="papel-badge"` visível no desktop para E2E existente (`shell.spec.ts` espera texto Master). O span mobile usa testid diferente para não duplicar. Inicial = primeira letra do nome (sem foto; sem dados novos).

- [ ] **Step 4: Integrar na navbar (substituir bloco linhas 24-51)**

Substituir o `<form periodo>` + `<div papel/nome/dark/logout>` por:
```html
<c-ui.scope_toggle escopo="{{ escopo|default:'operacional' }}" periodo="{{ request.GET.periodo }}" />
<c-ui.period_selector periodos="{{ periodos_nav }}" periodo_aberto="{{ periodo_aberto_nav }}" ultimo_periodo="{{ ultimo_periodo_nav }}" atual="{{ request.GET.periodo }}" action="{{ request.path }}" />
<div class="flex items-center gap-1.5 sm:gap-2">
  <c-ui.user_profile papel="{{ papel }}" nome="{{ user.nome_exibicao }}" />
  ... (manter dark-toggle + logout idênticos) ...
</div>
```
Nota Cotton: passar objetos via atributos funciona (`periodos="{{ periodos_nav }}"`); se Cotton escapar, usar sintaxe de variável sem aspas duplas aninhadas conforme `button.html`/`badge.html`. Escopo vem do contexto da página (dashboard tem `escopo`; demais páginas usam default operacional — aceitável, toggle só aparece funcional no dashboard; nas demais, links levam ao dashboard com escopo).

- [ ] **Step 5: Teste Django + commit**

```python
class NavbarControlesTestes(TestCase):
    def test_navbar_tem_toggle_periodo_perfil(self):
        self.client.force_login(self.erica)
        r = self.client.get("/")
        self.assertContains(r, 'data-testid="scope-toggle"')
        self.assertContains(r, 'data-testid="scope-operacional"')
        self.assertContains(r, 'data-testid="scope-financeiro"')
        self.assertContains(r, 'data-testid="period-selector"')
        self.assertContains(r, 'data-testid="user-profile"')
        self.assertContains(r, 'Erica')
```

Run: `.venv/Scripts/python.exe manage.py test apps.core.tests_frontend.NavbarControlesTestes apps.core.tests.DashboardEscopoTestes -v 2`
Expected: PASS.

```bash
git add templates/components/ui/scope_toggle.html templates/components/ui/period_selector.html templates/components/ui/user_profile.html templates/components/layout/navbar.html apps/core/tests_frontend.py
git commit -m "feat(nav): toggle escopo + periodo pill + perfil real na navbar"
```

### Task 3: home.html escopo-aware + E2E

**Files:**
- Modify: `templates/home.html:5-30,60-110,109-176`
- Modify: `tests/e2e/shell.spec.ts` (adicionar suite escopo)
- Test: `tests/e2e/shell.spec.ts`

**Interfaces:**
- Consumes: `escopo` do contexto.
- Produces: `data-testid="dashboard-conteudo"`, `data-testid="escopo-operacional"`, `data-testid="escopo-financeiro"`, `data-testid="kpi-*"`, `data-testid="chart-mensal"`, `data-testid="chart-financeiro"` preservados.

- [ ] **Step 1: Marcar `home.html` com blocos de escopo (server-side hidden, sem mudar queries)**

1. No `<div id="dashboard-conteudo">` adicionar `data-escopo="{{ escopo }}"`.
2. Envolver seção KPIs + heatmap + destaques + status + consolidado em `<div data-testid="escopo-operacional" {% if escopo == 'financeiro' %}hidden{% endif %}>`.
3. Envolver seção cards financeiros + 2 gráficos em `<div data-testid="escopo-financeiro" {% if escopo == 'operacional' %}hidden{% endif %}>`.
4. Manter `periodo-dash` form: adicionar `<input type="hidden" name="escopo" value="{{ escopo }}">` para preservar escopo ao trocar período.
5. Manter `chart_mensal_json`/`chart_financeiro_json` + `static/js/charts.js` (`htmx:afterSwap` re-init já existe — não tocar).

Proibido: mudar `_chart_*`, `kpi_por_pilar`, `status_counts`, RBAC, `periodo_selecionado`.

- [ ] **Step 2: E2E escopo sem reload**

```ts
test('toggle operacional|financeiro troca KPIs sem reload', async ({ page }) => {
  await login(page);
  await page.goto('/?escopo=operacional');
  await expect(page.getByTestId('escopo-operacional')).toBeVisible();
  await page.getByTestId('scope-financeiro').click();
  await expect(page).toHaveURL(/escopo=financeiro/);
  await expect(page.getByTestId('escopo-financeiro')).toBeVisible();
  await expect(page.getByTestId('escopo-operacional')).toBeHidden();
  await page.getByTestId('scope-operacional').click();
  await expect(page.getByTestId('escopo-operacional')).toBeVisible();
});
```

- [ ] **Step 3: Rodar Django + E2E escopo**

Run: `.venv/Scripts/python.exe manage.py test apps.core.tests -v 1`
Expected: PASS.

Run: `npx playwright test shell --reporter=list`
Expected: verde (inclui novo teste).

- [ ] **Step 4: Commit**

```bash
git add templates/home.html tests/e2e/shell.spec.ts
git commit -m "feat(dashboard): secoes por escopo com swap HTMX sem reload"
```

### Task 4: Validação final LOOP 2

**Files:** nenhum (só evidência)

- [ ] **Step 1: check + collectstatic**

Run: `.venv/Scripts/python.exe manage.py check`
Expected: no issues.
Run: `.venv/Scripts/python.exe manage.py collectstatic --no-input --clear`
Expected: sem erro manifest/Whitenoise.

- [ ] **Step 2: Suite Django**

Run: `.venv/Scripts/python.exe manage.py test`
Expected: 193+ OK (190 baseline + 3 escopo + 1 navbar controles).

- [ ] **Step 3: Playwright + a11y**

Run: `npx playwright test shell a11y_r6 --reporter=list`
Expected: verde, 0 critical/serious com toggle presente.

- [ ] **Step 4: Gate**

`git status --short` só com artefatos esperados. Gate: toggle troca sem reload, URL com `?escopo=`, período preservado, perfil exibe `nome • papel` real (ex. Erica • Master), `collectstatic` verde. Aguardar validação humana antes do LOOP 3.

## Self-Review

1. Spec coverage: escopo aditivo → Task 1; scope-toggle/period/user-profile → Task 2; swap sem reload + E2E → Task 3; gates → Task 4. RBAC/fechamento inalterados.
2. Placeholder scan: sem TBD/TODO; códigos completos; comandos exatos; sem "similar à Task N".
3. Type consistency: `escopo` string literal `operacional|financeiro` em view, toggle, home, testes; testids únicos (`papel-badge` 1x desktop, `papel-badge-mobile` sr-only); `period-selector` único; `escopo-operacional/financeiro` blocos + toggle links coerentes.
