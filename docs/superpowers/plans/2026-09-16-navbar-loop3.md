# Talentos + Associados LOOP 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Talentos com abas por vínculo (CLT/Bolsista) via migração autorizada + Associados com blocos executivos informativos, sem mudar regras de negócio.

**Architecture:** Migração `Colaborador.vinculo` (CLT/BOLSISTA/OUTRO, default OUTRO) + filtro `?vinculo=` aditivo na `OrganogramaView` (target-aware HTMX preservado) + abas no template com `hx-get/hx-target #talentos-lista`; CRM `funil.html` ganha 2 seções estáticas informativas (perfis + tiers Bronze→Diamante) com tokens QuIIN, sem tocar `Oportunidade/Empresa` nem RN-007.

**Tech Stack:** Django 5.2 + Cotton + HTMX + Alpine + Playwright.

**Spec:** `docs/superpowers/specs/2026-09-16-navbar-design.md` (LOOP 3)

## Global Constraints

- BACKEND: migração `vinculo` autorizada + filtro `?vinculo=` aditivo; NADA mais em regras (RBAC, pipeline open, renovações RN-007, disponibilidade 40h).
- Paleta QuIIN só tokens; Montserrat/JetBrains; sem CDN.
- HTMX+Alpine: abas via hx-get sem reload; busca skill Alpine preservada.
- UTF-8 sem round-trip; `.venv/Scripts/python.exe`.

---

### Task 1: Modelo vinculo + filtro

**Files:**
- Modify: `apps/talentos/models.py:18-36` (add campo)
- Create: `apps/talentos/migrations/0002_*.py` (via makemigrations)
- Modify: `apps/talentos/admin.py:41-43` (list_display+filter)
- Modify: `apps/talentos/forms.py:17` (fields += vinculo)
- Modify: `apps/talentos/views.py:18-57` (filtro)
- Test: `apps/talentos/tests.py` (classe `VinculoTestes`)

**Interfaces:**
- Consumes: `request.GET.get("vinculo")`.
- Produces: `Colaborador.vinculo` (`CLT|BOLSISTA|OUTRO`), contexto `vinculo_selecionado`, QS filtrada.

- [ ] **Step 1: Teste falhando**

```python
class VinculoTestes(TestCase):
    def test_filtra_por_vinculo(self):
        from apps.talentos.models import Colaborador
        c1 = Colaborador.objects.create(nome="Ana CLT", cargo="Dev", vinculo="CLT")
        Colaborador.objects.create(nome="Bia Bol", cargo="Est", vinculo="BOLSISTA")
        self.client.force_login(self.erica)
        r = self.client.get(reverse("talentos:organograma"), {"vinculo": "CLT"})
        self.assertContains(r, "Ana CLT")
        self.assertNotContains(r, "Bia Bol")
        self.assertEqual(r.context["vinculo_selecionado"], "CLT")

    def test_vinculo_invalido_mostra_todos(self):
        self.client.force_login(self.erica)
        r = self.client.get(reverse("talentos:organograma"), {"vinculo": "X"})
        self.assertEqual(r.context["vinculo_selecionado"], "")
```

Setup usa Master `erica` + login; `reverse("talentos:organograma")`.

- [ ] **Step 2: Run falha** `.venv/Scripts/python.exe manage.py test apps.talentos.tests.VinculoTestes -v 2` → FAIL (FieldDoesNotExist).
- [ ] **Step 3: Modelo**

```python
VINCULOS = [("CLT", "CLT"), ("BOLSISTA", "Bolsista"), ("OUTRO", "Outro")]
vinculo = models.CharField("Vínculo", max_length=10, choices=VINCULOS, default="OUTRO")
```

Run: `.venv/Scripts/python.exe manage.py makemigrations talentos` + `migrate` (dev; teste cria próprio banco).
- [ ] **Step 4: Admin/forms/view**

Admin: `list_display += vinculo`, `list_filter += vinculo`. Form fields += `"vinculo"`. View: `vinculo = request.GET.get("vinculo","") or ""`; allowlist `("CLT","BOLSISTA")` else `""`; `if vinculo: qs = qs.filter(vinculo=vinculo)`; contexto `vinculo_selecionado`. Preservar filtros pilar/competência + `htmx target talentos-lista` + disponibilidade.
- [ ] **Step 5: Run passa** mesma suite → PASS. Full talentos: `.venv/Scripts/python.exe manage.py test apps.talentos -v 1` PASS.
- [ ] **Step 6: Commit** `git add apps/talentos/models.py apps/talentos/migrations/ apps/talentos/admin.py apps/talentos/forms.py apps/talentos/views.py apps/talentos/tests.py; git commit -m "feat(talentos): vinculo CLT/Bolsista com filtro"`

### Task 2: Abas no template Talentos

**Files:**
- Modify: `apps/talentos/templates/talentos/organograma.html:16-49`
- Modify: `apps/talentos/templates/talentos/_lista.html:1-7` (badge vínculo)
- Modify: `tests/e2e/crm_talentos_r4.spec.ts` (suite abas)

**Interfaces:** Consumes `vinculo_selecionado`, `pilar_selecionado`, `competencia_selecionada`. Produces `data-testid="vinculo-tabs"`, `tab-todos/clt/bolsista`.

- [ ] **Step 1: Abas HTMX (inserir após header, antes do form)**

```html
<div data-testid="vinculo-tabs" role="tablist" aria-label="Vínculo" class="mt-4 flex flex-wrap gap-1.5">
  <a role="tab" aria-selected="{% if not vinculo_selecionado %}true{% else %}false{% endif %}" data-testid="tab-todos" href="{% url 'talentos:organograma' %}" hx-get="{% url 'talentos:organograma' %}" hx-target="#talentos-lista" hx-select="#talentos-lista" hx-swap="outerHTML" hx-push-url="true" hx-indicator="#progresso" class="rounded-full border px-3 py-1 text-xs {% if not vinculo_selecionado %}bg-quiin-navy text-white border-quiin-navy{% else %}border-border{% endif %}">Todos</a>
  <a role="tab" aria-selected="{% if vinculo_selecionado == 'CLT' %}true{% else %}false{% endif %}" data-testid="tab-clt" href="{% url 'talentos:organograma' %}?vinculo=CLT" hx-get="{% url 'talentos:organograma' %}?vinculo=CLT" hx-target="#talentos-lista" hx-select="#talentos-lista" hx-swap="outerHTML" hx-push-url="true" hx-indicator="#progresso" class="rounded-full border px-3 py-1 text-xs {% if vinculo_selecionado == 'CLT' %}bg-quiin-navy text-white border-quiin-navy{% else %}border-border{% endif %}">CLT</a>
  <a role="tab" aria-selected="{% if vinculo_selecionado == 'BOLSISTA' %}true{% else %}false{% endif %}" data-testid="tab-bolsista" href="{% url 'talentos:organograma' %}?vinculo=BOLSISTA" hx-get="{% url 'talentos:organograma' %}?vinculo=BOLSISTA" hx-target="#talentos-lista" hx-select="#talentos-lista" hx-swap="outerHTML" hx-push-url="true" hx-indicator="#progresso" class="rounded-full border px-3 py-1 text-xs {% if vinculo_selecionado == 'BOLSISTA' %}bg-quiin-navy text-white border-quiin-navy{% else %}border-border{% endif %}">Bolsistas</a>
</div>
```

Abas preservam só vínculo (pilar/competência via form existente; sem combinar para não explodir URLs — documentar). `hx-push-url` atualiza `?vinculo=`.
- [ ] **Step 2: Badge vínculo no card** em `_lista.html` após badge pilar: `{% if c.vinculo != 'OUTRO' %}<span class="rounded-full bg-quiin-mist/50 px-2 py-0.5 text-xs">{{ c.get_vinculo_display }}</span>{% endif %}`
- [ ] **Step 3: E2E**

```ts
test('abas CLT/Bolsistas filtram sem reload', async ({ page }) => {
  await login(page); await page.goto('/talentos/organograma/');
  await page.getByTestId('tab-clt').click();
  await expect(page).toHaveURL(/vinculo=CLT/);
  await expect(page.getByTestId('talentos-lista')).toBeVisible();
});
```

- [ ] **Step 4: Run** `manage.py test apps.talentos -v 1` + `npx playwright test crm_talentos_r4 --reporter=list` PASS.
- [ ] **Step 5: Commit** `git add apps/talentos/templates/ tests/e2e/crm_talentos_r4.spec.ts; git commit -m "feat(talentos): abas CLT/Bolsistas HTMX"`

### Task 3: Associados executivo + validação

**Files:**
- Modify: `apps/crm_at/templates/crm_at/funil.html:1-16` (2 seções após header, antes KPIs)
- Test: `apps/crm_at/tests.py` (assertContains perfis/tiers), E2E existente

**Interfaces:** Nenhum contexto novo; só HTML estático informativo + KPIs/funil/renovações intactos.

- [ ] **Step 1: Seção perfis (após header div, antes funil-kpis)**

```html
<section aria-label="Perfis de associado" class="mt-4 grid gap-3 sm:grid-cols-3">
  <c-ui.card><p class="text-sm font-bold">Demandante</p><p class="text-xs uppercase tracking-wide text-text-muted">Usuária da tecnologia</p><p class="mt-1 text-xs text-text-muted">Empresas com desafios solucíveis por tecnologias quânticas.</p></c-ui.card>
  <c-ui.card><p class="text-sm font-bold">Desenvolvedor industrial</p><p class="text-xs uppercase tracking-wide text-text-muted">Provedora da tecnologia</p><p class="mt-1 text-xs text-text-muted">Empresas com capacidade de industrializar soluções quânticas.</p></c-ui.card>
  <c-ui.card><p class="text-sm font-bold">Parceiro de inovação</p><p class="text-xs uppercase tracking-wide text-text-muted">ICTs e universidades</p><p class="mt-1 text-xs text-text-muted">ICTs complementares ao ecossistema do CCTQ.</p></c-ui.card>
</section>
<section aria-label="Categorias de membresia" class="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
  <c-ui.card><p class="text-sm font-bold">Bronze</p><p class="numerico mt-1 text-xl font-bold">R$ 60 mil<small class="text-xs text-text-muted"> / ano</small></p></c-ui.card>
  <c-ui.card><p class="text-sm font-bold">Prata</p><p class="numerico mt-1 text-xl font-bold">R$ 120 mil<small class="text-xs text-text-muted"> / ano</small></p></c-ui.card>
  <c-ui.card><p class="text-sm font-bold">Ouro</p><p class="numerico mt-1 text-xl font-bold">R$ 240 mil<small class="text-xs text-text-muted"> / ano</small></p></c-ui.card>
  <c-ui.card><p class="text-sm font-bold">Diamante</p><p class="numerico mt-1 text-xl font-bold">R$ 600 mil<small class="text-xs text-text-muted"> / ano</small></p></c-ui.card>
</section>
```

Fonte: Plano Anexo III (valores do mockup). Sem nomes de empresas (mockup alerta que nomes são perfis, não associadas vigentes — NÃO listar Positivo/PSR/BV etc.).
- [ ] **Step 2: Teste Django**

```python
def test_funil_tem_blocos_executivos(self):
    r = self.client.get(reverse("crm_at:funil"))
    self.assertContains(r, "Perfis de associado")
    self.assertContains(r, "Diamante")
    self.assertContains(r, "Pipeline em aberto")  # KPIs intactos
```

- [ ] **Step 3: Run** `manage.py check; manage.py test apps.talentos apps.crm_at apps.core -v 1; npx playwright test crm_talentos_r4 shell --reporter=list` PASS. `collectstatic --no-input --clear` verde.
- [ ] **Step 4: Commit** `git add apps/crm_at/templates/ apps/crm_at/tests.py; git commit -m "feat(crm): blocos executivos perfis + membresia"`

## Self-Review

1. Coverage: vínculo+abas (T1-T2), CRM blocos (T3), gates T3. RN-007/disponibilidade/RBAC intactos.
2. Placeholders: nenhum; códigos completos.
3. Consistency: `vinculo` CLT|BOLSISTA (+OUTRO interno), `vinculo_selecionado` view→template, testids `vinculo-tabs/tab-*`, sem PKs fixas.
