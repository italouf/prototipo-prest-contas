# Retrofit Visual QuIIN — R4 CRM AT & Talentos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesenhar o funil AT (etapas, pipeline de CNPJs, renovações separadas, meta 129 CNPJs) e o Banco de Talentos (cards com foto/Lattes/competências/disponibilidade, filtros HTMX e busca por skill em Alpine), sem alterar regras de negócio.

**Architecture:** Contexto aditivo nas views existentes (`FunilATView`, `OrganogramaView`) + partials HTMX (`talentos/_lista.html`); templates reescritos com componentes do design system; busca por skill client-side com Alpine sobre `data-busca` de cada card.

**Tech Stack:** Django 5.2, django-cotton, django-htmx, Alpine 3, Tailwind v4.

**Spec:** `docs/superpowers/specs/2026-09-10-retrofit-visual-design.md` (§7 R4)

## Global Constraints

- Preservar contexto/rotas atuais (`grupos`, `pipeline_open`, `renovacoes_qtd`, `renovacoes_total`, `pode_editar_crm`, `colaboradores`, `pilares`, `competencias`, filtros `?pilar=`/`?competencia=`).
- RN-007: renovações **não** contam para a meta de CNPJs novos (aparecerem em seção separada).
- Sem drag-and-drop nativo; alternativa acessível (links/botões), conforme spec.
- Testes Django/E2E existentes verdes; classes Tailwind literais; sem CDN.
- Gate final: regressão completa (155+ Django, 34+ E2E).

---

## Task 1: Backend R4

**Files:**
- Modify: `apps/crm_at/views.py`, `apps/crm_at/tests.py`
- Modify: `apps/talentos/views.py`, `apps/talentos/tests.py`
- Create: `apps/talentos/templates/talentos/_lista.html`

- [ ] **Step 1: Testes que falham**

Em `apps/crm_at/tests.py`:

```python
class FunilR4Testes(TestCase):
    def test_contexto_traz_funil_renovacoes_e_meta_cnpjs(self):
        # usar o mesmo setUp do teste de contexto existente; chamar self.client...
        resposta = self.client.get(reverse("crm_at:funil"))
        contexto = resposta.context
        self.assertIn("funil", contexto)
        self.assertIn("renovacoes", contexto)
        self.assertIn("meta_cnpjs", contexto)
        fases_funil = [g["fase"] for g in contexto["funil"]]
        self.assertNotIn("RENOVACAO", fases_funil)
        self.assertNotIn("PERDIDO", fases_funil)
```

(adaptar `setUp` existente para usuário com vínculo no pilar AT, como nos testes de `FunilATView`; usar fases/oportunidades já criadas.)

Em `apps/talentos/tests.py`:

```python
    def test_contexto_traz_horas_vigentes_e_disponibilidade(self):
        resposta = self.client.get(reverse("talentos:organograma"))
        colaborador = next(c for c in resposta.context["colaboradores"] if getattr(c, "alocacoes_vigentes", []))
        self.assertEqual(colaborador.horas_vigentes, sum(a.horas_semanais for a in colaborador.alocacoes_vigentes))
        self.assertEqual(colaborador.disponibilidade, max(0, 40 - colaborador.horas_vigentes))

    def test_htmx_renderiza_apenas_o_partial(self):
        resposta = self.client.get(reverse("talentos:organograma"), headers={"HX-Request": "true"})
        self.assertTemplateUsed(resposta, "talentos/_lista.html")
        self.assertNotContains(resposta, "Organograma")
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv\Scripts\python.exe manage.py test apps.crm_at apps.talentos -v 1`
Expected: FAIL

- [ ] **Step 3: Implementar o funil**

Em `apps/crm_at/views.py` (aditivo ao contexto):

```python
from apps.core.calculos import meta_realizado_percentual
from apps.core.utils import periodo_selecionado
from apps.indicators.models import Indicador
from .models import Empresa, Oportunidade
```

Dentro de `FunilATView.get`, após `grupos`/`pipeline_open`:

```python
        fases_funil = [f for f in Oportunidade.FASES if f[0] not in ("RENOVACAO", "PERDIDO")]
        funil = [
            {"fase": valor, "rotulo": rotulo, "oportunidades": [o for o in qs if o.fase == valor]}
            for valor, rotulo in fases_funil
        ]
        renovacoes = list(qs.filter(tipo="RENOVACAO").exclude(fase__in=_FASES_FECHADAS))
        perdidos = list(qs.filter(fase="PERDIDO"))
        periodo, _ = periodo_selecionado(request)
        meta_cnpjs = None
        if periodo is not None:
            indicador_cnpjs = Indicador.objects.filter(codigo="AT-CNPJ-NOVOS").first()
            if indicador_cnpjs is not None:
                meta_cnpjs = {
                    "indicador": indicador_cnpjs,
                    "dados": meta_realizado_percentual(indicador_cnpjs, periodo),
                    "periodo": periodo,
                }
```

Adicionar ao dicionário do `render`: `"funil": funil, "renovacoes": renovacoes, "perdidos": perdidos, "meta_cnpjs": meta_cnpjs, "empresas_associadas": Empresa.objects.filter(status="ASSOCIADA").count(), "prospects": Empresa.objects.filter(status="PROSPECT").count()`.

- [ ] **Step 4: Implementar o organograma**

Em `apps/talentos/views.py`, após montar `qs`:

```python
        colaboradores = list(qs)
        for colaborador in colaboradores:
            vigentes_colab = getattr(colaborador, "alocacoes_vigentes", [])
            colaborador.horas_vigentes = sum(a.horas_semanais for a in vigentes_colab)
            colaborador.disponibilidade = max(0, 40 - colaborador.horas_vigentes)
        contexto = {
            "colaboradores": colaboradores,
            "pilares": Pilar.objects.filter(ativo=True),
            "competencias": Competencia.objects.all(),
            "pilar_selecionado": pilar_selecionado,
            "competencia_selecionada": competencia_selecionada,
            "pode_editar_talentos": pode_lancar(request.user),
        }
        if request.htmx:
            return render(request, "talentos/_lista.html", contexto)
        return render(request, "talentos/organograma.html", contexto)
```

`templates/talentos/_lista.html`: grid de cards com `data-busca="{{ c.nome|lower }} {% for comp in c.competencias.all %}{{ comp.nome|lower }} {% endfor %}"` (só dentro do include, para não duplicar queries), avatar/iniciais, cargo, badge do pilar, competências, Lattes, disponibilidade (barra: `horas_vigentes`/40) e ações de edição quando permitido. Incluir `{% load core_extras %}`.

- [ ] **Step 5: Rodar testes e commit**

```powershell
.venv\Scripts\python.exe manage.py test apps.crm_at apps.talentos -v 1
git add apps/crm_at/views.py apps/crm_at/tests.py apps/talentos/views.py apps/talentos/tests.py apps/talentos/templates/talentos/_lista.html
git commit -m "feat(crm,talentos): contexto do funil e disponibilidade de talentos"
```

---

## Task 2: Redesenho do funil AT e do organograma

**Files:**
- Modify: `apps/crm_at/templates/crm_at/funil.html`
- Modify: `apps/talentos/templates/talentos/organograma.html`
- Modify: `apps/crm_at/templates/crm_at/oportunidade_form.html`, `empresa_form.html`, `apps/talentos/templates/talentos/colaborador_form.html`, `alocacao_form.html` (containers com o design system; widgets inalterados)

- [ ] **Step 1: Funil** — KPIs (`data-testid="funil-kpis"`): pipeline aberto, renovações (qtd/total), empresas associadas/prospects, meta CNPJs (`meta_cnpjs.dados` com meta × realizado × % e RN-007 explícito). Grid de colunas do funil (`data-testid="funil-coluna-<FASE>"`) com cards (`data-testid="oportunidade-<pk>"`: empresa, tipo, valor, observação, link editar). Seção separada "Renovações" (`data-testid="kanban-renovacoes"`, nota RN-007) e seção "Perdidos" (colapsável via `<details>`), preservando os textos/links dos testes existentes.

- [ ] **Step 2: Organograma** — filtros como formulário HTMX (`hx-get`, `hx-target="#talentos-lista"`, `hx-select="#talentos-lista"`, `hx-swap="outerHTML"`, `hx-push-url="true"`, `onchange="this.form.requestSubmit()"`, `hx-indicator="#progresso"`), busca por skill (`data-testid="busca-talento"`, Alpine `x-model="busca"`), e `<div id="talentos-lista" data-testid="talentos-lista">{% include "talentos/_lista.html" %}</div>`. Botão "+ Novo colaborador" preservado.

- [ ] **Step 3: Formulários** — envolver os forms em `c-ui.card`, botões `c-ui.button` (Salvar/Voltar), mantendo `{{ campo }}` e labels/erros.

- [ ] **Step 4: Build e regressão parcial**

```powershell
$env:PYTHONUTF8="1"; .venv\Scripts\python.exe manage.py tailwind build --force
.venv\Scripts\python.exe manage.py collectstatic --no-input --clear
.venv\Scripts\python.exe manage.py test apps.crm_at apps.talentos -v 1
npx playwright test tests/e2e/portal.spec.ts tests/e2e/shell.spec.ts --reporter=list
git add apps/crm_at/templates apps/talentos/templates static/css/tailwind.css
git commit -m "feat(crm,talentos): funil visual, cards de talentos e filtros HTMX"
```

---

## Task 3: E2E do R4, regressão, evidências e docs

- [ ] **Step 1: `tests/e2e/crm_talentos_r4.spec.ts`** cobrindo: KPIs do funil com meta de CNPJs; colunas do funil com cards; renovações separadas; filtro por pilar do organograma via HTMX sem reload (marcador `window`); busca por skill escondendo cards; disponibilidade visível.

- [ ] **Step 2: Rodar, evidências e regressão completa**

```powershell
npx playwright test tests/e2e/crm_talentos_r4.spec.ts --reporter=list
$env:EVIDENCIA_DIR="docs/retrofit/evidencias/R4-depois"; npx playwright test tests/e2e/screenshots.spec.ts
.venv\Scripts\python.exe manage.py test
npx playwright test
```

- [ ] **Step 3: `docs/retrofit/loops.md`** (R4 concluído; registrar que "hierarquia Valéria→Anderson→Líderes" não existe no modelo — organizamos por pilar, sem dados inventados) e commit final.

---

## Self-review (cobertura da spec R4)

- Funil visual por fases: Task 2. ✔
- Pipeline de CNPJs (cards) com meta 129: Tasks 1–2. ✔
- Renovações separadas (RN-007): Tasks 1–2. ✔
- Organograma com filtros por pilar/competência (HTMX): Tasks 1–2. ✔
- Cards com foto/Lattes/competências/disponibilidade: Tasks 1–2. ✔
- Banco de talentos com busca por skill (Alpine + HTMX): Task 2. ✔
- Regressão e evidências: Task 3. ✔
