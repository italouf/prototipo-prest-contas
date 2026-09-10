# Retrofit Visual QuIIN — R3 Operacional Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesenhar o fluxo operacional (lançamento → aprovação → financeiro) com kanban de status, validação em tempo real, modal de devolução, timeline de auditoria e preview de CSV, mantendo views/URLs/regras e os E2E existentes verdes.

**Architecture:** Backend aditivo (kanban no contexto de aprovação e endpoint de timeline reaproveitando `AuditLog`); UX com Alpine data components em arquivos estáticos (`entries/lancamento.js`, `entries/aprovacao.js`, `finance/importar.js`); toasts globais no `base.html` preservando `.messages .alert`; templates reescritos com os nomes/roles existentes preservados.

**Tech Stack:** Django 5.2, django-cotton, django-htmx, Alpine 3, Tailwind v4.

**Spec:** `docs/superpowers/specs/2026-09-10-retrofit-visual-design.md` (§6 patterns, §7 R3)

## Global Constraints

- Python via `.venv\Scripts\python.exe`; Tailwind com `$env:PYTHONUTF8="1"`.
- Preservar: `input[name="valor_3"]`, botões "Salvar rascunho"/"Enviar para validação", heading "Painel de aprovação", botão "Aprovar", `main select[name="periodo"]`, `input[type="file"]`, botão "Importar", `.messages .alert`.
- Serviços (`salvar_ou_enviar`, `aprovar`, `devolver`) não mudam; validação de servidor continua sendo a fonte da verdade.
- Período fechado permanece bloqueado no backend e refletido na UI.
- Sem CDN; classes Tailwind literais.
- Regressão final: Django (149+) e Playwright (29+) verdes.

---

## Task 1: Backend R3 (kanban + timeline)

**Files:**
- Modify: `apps/entries/views.py`, `apps/entries/urls.py`, `apps/entries/tests.py`
- Create: `templates/partials/entries/drawer_lancamento.html`

**Interfaces:**
- Produces: contexto `kanban` (`{"RASCUNHO": [...], "ENVIADO": [...], "APROVADO": [...], "DEVOLVIDO": [...]}`) em `aprovacao`; rota `entries:lancamento_drawer` (`/aprovacao/lancamento/<pk>/drawer/`) com timeline de `AuditLog`.

- [ ] **Step 1: Testes que falham**

Adicionar em `apps/entries/tests.py`:

```python
class AprovacaoR3Testes(TestCase):
    def setUp(self):
        from datetime import date

        from apps.audit.models import AuditLog
        from apps.core.permissions import adicionar_grupo, garantir_grupos
        from apps.indicators.models import Indicador, Meta
        from apps.periods.models import Periodo
        from apps.pillars.models import Pilar

        garantir_grupos()
        self.erica = adicionar_grupo(User.objects.create_user(username="r3_master", password="x"), "Master")
        self.pilar = Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=1)
        self.ind = Indicador.objects.create(pilar=self.pilar, codigo="PDI-PROJ-INI", nome="Projetos iniciados", tipo="QTD")
        Meta.objects.create(
            indicador=self.ind, competencia_inicio=date(2026, 1, 1),
            competencia_fim=date(2026, 12, 31), periodicidade="MENSAL", valor=2,
        )
        self.periodo = Periodo.objects.create(competencia=date(2026, 6, 1), status="ABERTO", aberto_por=self.erica)
        salvar_ou_enviar(self.periodo, self.pilar, self.erica, {str(self.ind.pk): {"valor": "1"}}, enviar=True)
        self.lc = Lancamento.objects.get(periodo=self.periodo)
        self.client.force_login(self.erica)

    def test_aprovacao_expoe_kanban_por_status(self):
        kanban = self.client.get(reverse("entries:aprovacao", args=[self.periodo.pk])).context["kanban"]
        self.assertEqual(list(kanban.keys()), ["RASCUNHO", "ENVIADO", "APROVADO", "DEVOLVIDO"])
        self.assertEqual(len(kanban["ENVIADO"]), 1)

    def test_timeline_do_lancamento_mostra_auditoria(self):
        self.client.post(reverse("entries:aprovacao", args=[self.periodo.pk]), {"lancamento_id": self.lc.pk, "aprovar": "1"})
        resposta = self.client.get(reverse("entries:lancamento_drawer", args=[self.lc.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Lançamento aprovado")
        self.assertNotContains(resposta, "Painel de aprovação")

    def test_timeline_requer_gestor(self):
        from apps.core.permissions import adicionar_grupo

        auditor = adicionar_grupo(User.objects.create_user(username="r3_auditor", password="x"), "Auditor")
        self.client.force_login(auditor)
        resposta = self.client.get(reverse("entries:lancamento_drawer", args=[self.lc.pk]))
        self.assertEqual(resposta.status_code, 403)
```

(garantir imports existentes: `User`, `Lancamento`, `salvar_ou_enviar`, `reverse`, `TestCase`)

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv\Scripts\python.exe manage.py test apps.entries.tests.AprovacaoR3Testes -v 1`
Expected: FAIL (sem `kanban`, sem rota)

- [ ] **Step 3: Implementar kanban + timeline**

Em `apps/entries/views.py`:

```python
from django.http import HttpResponseForbidden

from apps.audit.models import AuditLog
from apps.core.permissions import pode_aprovar, pode_lancar, sem_permissao, usuario_pode_pilar
```

Na view `aprovacao`, antes do `return render(...)`:

```python
    todos = list(
        periodo.lancamentos.select_related(
            "indicador", "indicador__pilar", "usuario_criacao", "usuario_aprovacao"
        ).order_by("indicador__pilar__ordem", "indicador__codigo")
    )
    kanban = {status: [] for status in ("RASCUNHO", "ENVIADO", "APROVADO", "DEVOLVIDO")}
    for lc in todos:
        kanban.setdefault(lc.status, []).append(lc)
    return render(
        request,
        "entries/aprovacao.html",
        {"periodo": periodo, "enviados": kanban["ENVIADO"], "kanban": kanban},
    )
```

Nova view:

```python
@login_required
def lancamento_drawer(request, pk):
    """Timeline de auditoria de um lançamento (drawer HTMX)."""
    if not pode_aprovar(request.user):
        return HttpResponseForbidden("Sem permissão para revisar este lançamento.")
    lc = get_object_or_404(
        Lancamento.objects.select_related(
            "indicador", "indicador__pilar", "usuario_criacao", "usuario_aprovacao"
        ),
        pk=pk,
    )
    eventos = (
        AuditLog.objects.filter(entidade="Lancamento", registro_id=str(lc.pk))
        .select_related("usuario")
        .order_by("-data_hora")[:20]
    )
    return render(
        request,
        "partials/entries/drawer_lancamento.html",
        {"lc": lc, "eventos": eventos},
    )
```

`apps/entries/urls.py`:

```python
from .views import aprovacao, formulario, lancamento_drawer

urlpatterns = [
    path("lancamentos/<int:periodo_pk>/<int:pilar_pk>/", formulario, name="formulario"),
    path("aprovacao/lancamento/<int:pk>/drawer/", lancamento_drawer, name="lancamento_drawer"),
    path("aprovacao/<int:periodo_pk>/", aprovacao, name="aprovacao"),
]
```

`templates/partials/entries/drawer_lancamento.html`:

```html
{% load core_extras %}
<div data-testid="drawer-lancamento">
  <p class="text-xs font-semibold uppercase tracking-wide text-text-muted">{{ lc.indicador.pilar.codigo }} · {{ lc.periodo.rotulo }}</p>
  <h3 class="font-display text-lg font-bold">{{ lc.indicador.nome }}</h3>
  <p class="text-xs text-text-muted">{{ lc.indicador.codigo }}</p>
  <dl class="mt-3 grid grid-cols-2 gap-2 text-sm">
    <div><dt class="text-xs text-text-muted">Valor</dt><dd class="numerico">{{ lc.valor_numerico|numero_ptbr }}{{ lc.valor_texto }}</dd></div>
    <div><dt class="text-xs text-text-muted">Status</dt><dd>{{ lc.status|status_lancamento }}</dd></div>
    <div class="col-span-2"><dt class="text-xs text-text-muted">Comentário</dt><dd>{{ lc.comentario|default:'—' }}</dd></div>
  </dl>
  <h4 class="mt-5 text-sm font-semibold">Timeline de aprovação</h4>
  <ol class="mt-2 space-y-3 border-l border-border pl-4" data-testid="timeline-lancamento">
    {% for evento in eventos %}
    <li class="relative">
      <span class="absolute -left-[21px] top-1.5 h-2.5 w-2.5 rounded-full bg-quiin-sky"></span>
      <p class="text-sm font-medium">{{ evento.acao|acao_amigavel }}</p>
      <p class="text-xs text-text-muted">
        {{ evento.data_hora|date:'d/m/Y H:i' }}{% if evento.usuario %} · {{ evento.usuario.nome_exibicao }}{% endif %}
      </p>
      {% if evento.valor_novo %}<p class="text-xs text-text-muted">Novo: {{ evento.valor_novo }}</p>{% endif %}
      {% if evento.justificativa %}<p class="text-xs text-status-pendente-texto">Justificativa: {{ evento.justificativa }}</p>{% endif %}
    </li>
    {% empty %}
    <li class="text-sm text-text-muted">Sem eventos registrados.</li>
    {% endfor %}
  </ol>
</div>
```

- [ ] **Step 4: Rodar os testes e commit**

```powershell
.venv\Scripts\python.exe manage.py test apps.entries -v 1
git add apps/entries/views.py apps/entries/urls.py apps/entries/tests.py templates/partials/entries/drawer_lancamento.html
git commit -m "feat(entries): kanban de status e timeline de auditoria no backend"
```

---

## Task 2: Toasts + lançamento com filtros e validação em tempo real

**Files:**
- Modify: `templates/base.html`, `templates/entries/lancamento.html`
- Create: `static/js/entries/lancamento.js`
- Test: `apps/core/tests_frontend.py`, `apps/entries/tests.py`

- [ ] **Step 1: Toasts globais no base**

Substituir o bloco de mensagens dentro de `<main>` do `base.html` por um bloco de toasts fixo (fora do `<main>`, após `</main>` do fluxo autenticado não é necessário: usar slot global antes de `{% block content %}`):

```html
{% if messages %}
<div class="messages pointer-events-none fixed right-4 top-4 z-[70] w-80 space-y-2" role="status" aria-live="polite">
  {% for message in messages %}
  <div x-data="{ visivel: true }" x-show="visivel" x-init="setTimeout(() => visivel = false, 6000)" x-transition.opacity
       class="alert alert-{{ message.tags|default:'info' }} pointer-events-auto shadow-lg">
    {{ message }}
  </div>
  {% endfor %}
</div>
{% endif %}
```

(Manter `.messages` e `.alert` para os E2E existentes; o container fica no layout autenticado e também no anônimo se necessário — colocar logo antes de `{% block content %}` dentro do `<main>` com classes `fixed`.)

- [ ] **Step 2: Teste de presença dos componentes**

Em `apps/core/tests_frontend.py`:

```python
class ToastsTestes(TestCase):
    def test_toasts_aparecem_com_mensagem(self):
        from django.contrib.auth.models import Group

        from apps.accounts.models import User

        grupo, _ = Group.objects.get_or_create(name="Master")
        user = User.objects.create_user(username="toast_user", password="x")
        user.groups.add(grupo)
        self.client.force_login(user)
        resposta = self.client.get("/")
        self.assertContains(resposta, "messages pointer-events-none fixed")
```

Em `apps/entries/tests.py`, teste do filtro/validação no HTML:

```python
    def test_formulario_tem_filtros_e_campos_de_validacao(self):
        resposta = self.client.get(reverse("entries:formulario", args=[self.periodo.pk, self.pilar.pk]))
        self.assertContains(resposta, 'data-testid="filtro-tipo-TODOS"')
        self.assertContains(resposta, 'data-testid="filtro-tipo-QTD"')
        self.assertContains(resposta, 'x-data="campoValor(')
```

- [ ] **Step 3: Criar `static/js/entries/lancamento.js`**

```javascript
/* Alpine components do formulário de lançamentos (R3). */
document.addEventListener("alpine:init", function () {
  Alpine.data("filtroIndicadores", function () {
    return {
      tipo: "TODOS",
      mostra: function (t) {
        return this.tipo === "TODOS" || this.tipo === t;
      },
      selecionar: function (t) {
        this.tipo = t;
      },
    };
  });

  Alpine.data("campoValor", function (inicial, tipo) {
    return {
      valor: inicial,
      erro: "",
      validar: function () {
        this.erro = "";
        if (this.valor === "" || this.valor === null) return;
        if (tipo === "TXT") return;
        var texto = String(this.valor).replace(/\./g, "").replace(",", ".");
        var numero = parseFloat(texto);
        if (isNaN(numero) || !isFinite(texto)) {
          this.erro = "Valor numérico inválido.";
          return;
        }
        if (tipo === "PER" && numero > 100) {
          this.erro = "Percentual não pode passar de 100.";
        }
      },
      init: function () {
        var self = this;
        this.$watch("valor", function () {
          self.validar();
        });
      },
    };
  });
});
```

- [ ] **Step 4: Reescrever `templates/entries/lancamento.html`**

Estrutura (mantendo nomes de campos e botões):

```html
{% extends 'base.html' %}
{% load static core_extras %}
{% block title %}Lançamentos · {{ pilar.nome }} · Portal QuIIN{% endblock %}
{% block breadcrumbs %}{% include "partials/breadcrumbs.html" with atual="Lançamentos mensais" %}{% endblock %}
{% block content %}
<div x-data="filtroIndicadores" data-testid="page-lancamentos">
  <div class="flex flex-wrap items-end justify-between gap-3">
    <div>
      <h1 class="text-2xl font-bold">Lançamentos mensais</h1>
      <p class="text-sm text-text-muted">Período <strong>{{ periodo.rotulo }}</strong> ({{ periodo.get_status_display }}) · Pilar <strong>{{ pilar.nome }}</strong></p>
    </div>
    <div class="flex flex-wrap gap-1.5">
      <a class="rounded-md border border-border px-3 py-1.5 text-sm {% if p.pk == pilar.pk %}bg-quiin-navy text-white{% endif %}"
         href="{% url 'entries:formulario' periodo.pk p.pk %}">{{ p.codigo }}</a>
    </div>
  </div>

  {% if bloqueado %}
  <div class="mt-4 flex items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-status-pendente-texto" data-testid="periodo-bloqueado">
    <c-ui.icon name="alert" size="16" /> Período fechado: dados somente leitura (RN-010).
  </div>
  {% endif %}

  <div class="mt-4 flex flex-wrap gap-1.5" role="group" aria-label="Filtrar por tipo de indicador">
    <button type="button" data-testid="filtro-tipo-TODOS" @click="selecionar('TODOS')" :aria-pressed="tipo === 'TODOS'"
            :class="tipo === 'TODOS' ? 'bg-quiin-navy text-white' : 'border border-border'"
            class="rounded-full px-3 py-1 text-xs">Todos</button>
    {% for tipo, rotulo in tipos %}
    <button type="button" data-testid="filtro-tipo-{{ tipo }}" @click="selecionar('{{ tipo }}')" :aria-pressed="tipo === '{{ tipo }}'"
            :class="tipo === '{{ tipo }}' ? 'bg-quiin-navy text-white' : 'border border-border'"
            class="rounded-full px-3 py-1 text-xs">{{ rotulo }}</button>
    {% endfor %}
  </div>

  <form method="post" class="mt-4">
    {% csrf_token %}
    <div class="overflow-x-auto rounded-xl border border-border bg-surface-2">
      <table class="w-full border-collapse text-sm">
        <thead>
          <tr class="border-b border-border text-left text-xs uppercase tracking-wide text-text-muted">
            <th class="px-4 py-3">Indicador</th><th class="px-4 py-3">Un.</th><th class="px-4 py-3">Valor</th>
            <th class="px-4 py-3">Comentário</th><th class="px-4 py-3">Status</th>
          </tr>
        </thead>
        <tbody>
          {% for ind in indicadores %}
          {% with info=existentes|lancamento_info:ind.pk %}
          <tr x-show="mostra('{{ ind.tipo }}')" data-tipo="{{ ind.tipo }}" class="border-b border-border/60 align-top" data-testid="linha-indicador-{{ ind.codigo }}">
            <td class="px-4 py-3"><strong>{{ ind.nome }}</strong><br><span class="text-xs text-text-muted">{{ ind.codigo }} · {{ ind.get_tipo_display }}</span></td>
            <td class="px-4 py-3">{{ ind.unidade }}</td>
            <td class="px-4 py-3">
              <div x-data="campoValor('{{ info.valor|escapejs }}', '{{ ind.tipo }}')" class="min-w-[10rem]">
                {% if ind.tipo == 'TXT' %}
                <textarea name="valor_{{ ind.pk }}" rows="2" {% if bloqueado %}disabled{% endif %} x-model="valor"
                          class="w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm"></textarea>
                {% else %}
                <input type="text" name="valor_{{ ind.pk }}" inputmode="decimal" placeholder="0,00" value="{{ info.valor }}"
                       x-model="valor" {% if bloqueado %}disabled{% endif %}
                       :class="erro ? 'border-red-500' : 'border-border'"
                       class="w-full rounded-md border bg-surface px-2 py-1.5 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-focus/60">
                <p x-show="erro" x-text="erro" class="mt-1 text-xs text-red-600" role="alert"></p>
                {% endif %}
              </div>
            </td>
            <td class="px-4 py-3">
              <input type="text" name="comentario_{{ ind.pk }}" value="{{ info.comentario }}" placeholder="Observação do mês"
                     {% if bloqueado %}disabled{% endif %}
                     class="w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm">
              {% if info.revisao %}<p class="mt-1 text-xs text-status-pendente-texto">Revisão: {{ info.revisao }}</p>{% endif %}
            </td>
            <td class="px-4 py-3">
              <c-ui.badge tone="{% if info.status == 'APROVADO' %}success{% elif info.status == 'ENVIADO' %}info{% elif info.status == 'DEVOLVIDO' %}warn{% else %}neutral{% endif %}">
                {{ info.status|default:'Pendente'|status_lancamento }}
              </c-ui.badge>
            </td>
          </tr>
          {% endwith %}
          {% empty %}
          <tr><td colspan="5" class="px-4 py-3 text-sm text-text-muted">Nenhum indicador ativo neste pilar.</td></tr>
          {% endfor %}
        </tbody>
      </table>
    </div>

    {% if not bloqueado %}
    <div class="mt-4 flex gap-2">
      <c-ui.button type="submit" name="salvar" value="1" variant="ghost">Salvar rascunho</c-ui.button>
      <c-ui.button type="submit" name="enviar" value="1">Enviar para validação</c-ui.button>
    </div>
    {% endif %}
  </form>
</div>
{% endblock %}
{% block scripts %}
<script src="{% static 'js/entries/lancamento.js' %}" defer></script>
{% endblock %}
```

Contexto da view `formulario` ganha `"tipos": Indicador.TIPOS` (verificar choices no modelo; se não houver atributo, usar constante `[("QTD","QTD"),("MON","MON"),("PER","PER"),("TXT","TXT")]`).

- [ ] **Step 5: Testes e commit**

```powershell
$env:PYTHONUTF8="1"; .venv\Scripts\python.exe manage.py tailwind build --force
.venv\Scripts\python.exe manage.py collectstatic --no-input --clear
.venv\Scripts\python.exe manage.py test apps.entries apps.core.tests_frontend -v 1
npx playwright test tests/e2e/portal.spec.ts --reporter=list
git add templates/base.html templates/entries/lancamento.html static/js/entries/lancamento.js apps/entries/views.py apps/entries/tests.py apps/core/tests_frontend.py static/css/tailwind.css
git commit -m "feat(entries): lancamento com filtros, validacao Alpine e toasts globais"
```

---

## Task 3: Painel de aprovação com kanban, modal de devolução e drawer

**Files:**
- Modify: `templates/entries/aprovacao.html`
- Create: `static/js/entries/aprovacao.js`

- [ ] **Step 1: Criar `static/js/entries/aprovacao.js`**

```javascript
/* Alpine component do painel de aprovação (R3). */
document.addEventListener("alpine:init", function () {
  Alpine.data("painelAprovacao", function () {
    return {
      drawerAberto: false,
      devolver: { aberto: false, id: null, codigo: "" },
      abrirDevolucao: function (id, codigo) {
        this.devolver = { aberto: true, id: id, codigo: codigo };
        this.$nextTick(function () {
          var campo = document.getElementById("motivo-devolucao");
          if (campo) campo.focus();
        });
      },
      fecharDevolucao: function () {
        this.devolver = { aberto: false, id: null, codigo: "" };
      },
      abrirTimeline: function () {
        this.drawerAberto = true;
      },
    };
  });
});
```

- [ ] **Step 2: Reescrever `templates/entries/aprovacao.html`**

Estrutura: título "Painel de aprovação"; kanban 4 colunas (`data-testid="kanban-coluna-<STATUS>"`); cards com `data-testid="kanban-card-<pk>"`; botões Aprovar (form) e Devolver (modal); botão Timeline com `hx-get`; modal com `name="comentario_revisao"` obrigatório e hidden `lancamento_id`; drawer lateral. Manter `{% csrf_token %}` em cada form; o modal tem um único form com `:action` não necessário (mesma URL) e hidden `:value="devolver.id"`.

Pontos-chave do markup:

```html
{% extends 'base.html' %}
{% load static core_extras %}
{% block title %}Aprovação · {{ periodo.rotulo }} · Portal QuIIN{% endblock %}
{% block breadcrumbs %}{% include "partials/breadcrumbs.html" with atual="Aprovação" %}{% endblock %}
{% block content %}
<div x-data="painelAprovacao" data-testid="page-aprovacao">
  <h1 class="text-2xl font-bold">Painel de aprovação</h1>
  <p class="text-sm text-text-muted">Período <strong>{{ periodo.rotulo }}</strong> ({{ periodo.get_status_display }})</p>

  <div class="mt-4 grid gap-4 lg:grid-cols-4">
    {% for status, cartoes in kanban.items %}
    <section class="rounded-xl border border-border bg-surface-2 p-3" data-testid="kanban-coluna-{{ status }}" aria-label="Coluna {{ status|status_lancamento }}">
      <header class="flex items-center justify-between px-1 pb-2">
        <h2 class="text-sm font-semibold">{{ status|status_lancamento }}</h2>
        <span class="rounded-full bg-quiin-mist/50 px-2 py-0.5 text-xs">{{ cartoes|length }}</span>
      </header>
      <div class="space-y-2">
        {% for lc in cartoes %}
        <article class="rounded-lg border border-border bg-surface p-3" data-testid="kanban-card-{{ lc.pk }}">
          ... indicador, pilar, valor, autor ...
          {% if status == 'ENVIADO' %}
          <div class="mt-2 flex flex-wrap gap-2">
            <form method="post">{% csrf_token %}<input type="hidden" name="lancamento_id" value="{{ lc.pk }}">
              <c-ui.button type="submit" size="sm" name="aprovar" value="1">Aprovar</c-ui.button>
            </form>
            <c-ui.button type="button" size="sm" variant="danger" @click="abrirDevolucao({{ lc.pk }}, '{{ lc.indicador.codigo }}')">Devolver</c-ui.button>
          </div>
          {% endif %}
          <button type="button" class="mt-2 text-xs text-quiin-royal underline"
                  hx-get="{% url 'entries:lancamento_drawer' lc.pk %}" hx-target="#drawer-conteudo" hx-swap="innerHTML"
                  @click="abrirTimeline()" data-testid="timeline-{{ lc.pk }}">Ver timeline</button>
        </article>
        {% empty %}
        <p class="px-1 text-xs text-text-muted">Nenhum lançamento.</p>
        {% endfor %}
      </div>
    </section>
    {% endfor %}
  </div>

  <!-- modal devolução -->
  <div x-show="devolver.aberto" x-cloak class="fixed inset-0 z-50" data-testid="modal-devolucao" role="dialog" aria-modal="true" aria-labelledby="titulo-devolucao">
    <div class="absolute inset-0 bg-black/40" @click="fecharDevolucao()"></div>
    <div class="absolute left-1/2 top-1/2 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-xl bg-surface-2 p-5 shadow-2xl">
      <h2 id="titulo-devolucao" class="font-display text-lg font-semibold">Devolver <span class="numerico" x-text="devolver.codigo"></span></h2>
      <form method="post" class="mt-3">
        {% csrf_token %}
        <input type="hidden" name="lancamento_id" :value="devolver.id">
        <label for="motivo-devolucao" class="mb-1 block text-sm font-semibold">Justificativa (obrigatória)</label>
        <textarea id="motivo-devolucao" name="comentario_revisao" rows="3" required data-testid="motivo-devolucao"
                  class="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm"></textarea>
        <div class="mt-4 flex justify-end gap-2">
          <c-ui.button type="button" variant="ghost" @click="fecharDevolucao()">Cancelar</c-ui.button>
          <c-ui.button type="submit" variant="danger" name="devolver" value="1">Confirmar devolução</c-ui.button>
        </div>
      </form>
    </div>
  </div>

  <!-- drawer timeline -->
  <div x-show="drawerAberto" x-cloak class="fixed inset-0 z-40" data-testid="drawer-timeline" role="dialog" aria-modal="true" aria-label="Timeline do lançamento">
    <div class="absolute inset-0 bg-black/40" @click="drawerAberto = false"></div>
    <aside class="absolute right-0 top-0 h-full w-full max-w-md overflow-y-auto bg-surface-2 p-5 shadow-2xl">
      <div class="flex items-center justify-between">
        <h2 class="font-display text-lg font-semibold">Timeline</h2>
        <button type="button" @click="drawerAberto = false" aria-label="Fechar timeline" class="rounded-md border border-border p-1.5" data-testid="drawer-timeline-fechar">
          <c-ui.icon name="x" size="16" />
        </button>
      </div>
      <div id="drawer-conteudo" class="mt-4"></div>
    </aside>
  </div>
</div>
{% endblock %}
{% block scripts %}
<script src="{% static 'js/entries/aprovacao.js' %}" defer></script>
{% endblock %}
```

- [ ] **Step 3: Testes e commit**

```powershell
$env:PYTHONUTF8="1"; .venv\Scripts\python.exe manage.py tailwind build --force
.venv\Scripts\python.exe manage.py test apps.entries -v 1
npx playwright test tests/e2e/portal.spec.ts --reporter=list
git add templates/entries/aprovacao.html static/js/entries/aprovacao.js static/css/tailwind.css
git commit -m "feat(entries): kanban de aprovacao com modal de devolucao e timeline"
```

---

## Task 4: Importador CSV com preview e validação visual

**Files:**
- Modify: `templates/finance/importar.html`
- Create: `static/js/finance/importar.js`
- Test: `apps/finance/tests.py`

- [ ] **Step 1: Teste que falha**

Adicionar em `apps/finance/tests.py` um teste de presença:

```python
    def test_pagina_importar_tem_componente_de_preview(self):
        self.client.force_login(self.gestor)
        resposta = self.client.get(reverse("finance:importar"))
        self.assertContains(resposta, 'x-data="previewCsv"')
        self.assertContains(resposta, 'data-testid="preview-csv"')
```

- [ ] **Step 2: Criar `static/js/finance/importar.js`**

```javascript
/* Alpine component do preview de CSV (R3). */
document.addEventListener("alpine:init", function () {
  var CABECALHO = "competencia,pilar,tipo_recurso,valor_captado,valor_executado,observacao";
  var TIPOS = ["EMBRAPII", "AT", "OUTRAS_FONTES"];

  function validarLinha(colunas, numero) {
    var erros = [];
    if (colunas.length !== 6) return ["Colunas: esperado 6, encontrado " + colunas.length + "."];
    var competencia = (colunas[0] || "").trim();
    if (!/^\d{4}-\d{2}/.test(competencia)) erros.push("Competência deve ser AAAA-MM.");
    if (!(colunas[1] || "").trim()) erros.push("Pilar vazio.");
    if (TIPOS.indexOf((colunas[2] || "").trim()) === -1) erros.push("Tipo deve ser EMBRAPII, AT ou OUTRAS_FONTES.");
    [3, 4].forEach(function (i) {
      var valor = (colunas[i] || "").trim();
      if (valor !== "" && isNaN(parseFloat(valor))) erros.push("Coluna " + (i + 1) + " deve ser numérica.");
    });
    return erros;
  }

  Alpine.data("previewCsv", function () {
    return {
      nomeArquivo: "",
      linhas: [],
      errosTotais: 0,
      valido: false,
      ler: function (evento) {
        var arquivo = evento.target.files[0];
        this.linhas = [];
        this.errosTotais = 0;
        this.valido = false;
        if (!arquivo) return;
        this.nomeArquivo = arquivo.name;
        var self = this;
        arquivo.text().then(function (texto) {
          var linhas = texto.split(/\r?\n/).filter(function (l) { return l.trim() !== ""; });
          var cabecalho = (linhas.shift() || "").trim();
          var erroCabecalho = cabecalho !== CABECALHO ? "Cabeçalho inesperado." : "";
          self.linhas = linhas.map(function (linha, indice) {
            var colunas = linha.split(",");
            var erros = validarLinha(colunas, indice + 2);
            self.errosTotais += erros.length;
            return { numero: indice + 2, colunas: colunas, erros: erros, valida: erros.length === 0 };
          });
          if (erroCabecalho) self.errosTotais += 1;
          self.valido = self.errosTotais === 0 && self.linhas.length > 0;
        });
      },
    };
  });
});
```

- [ ] **Step 3: Reescrever `templates/finance/importar.html`**

Estrutura: manter `main select[name="periodo"]`, `input[type="file"] name="arquivo"` (com `@change="ler($event)"`), botão `Importar` (`:disabled="nomeArquivo && !valido"`), painel de layout, e nova seção `data-testid="preview-csv"` com tabela de linhas + erros; histórico redesenhado com `c-ui.table`/badges. Incluir `<script src="{% static 'js/finance/importar.js' %}" defer></script>` em `{% block scripts %}` e `{% load static %}`.

- [ ] **Step 4: Testes e commit**

```powershell
$env:PYTHONUTF8="1"; .venv\Scripts\python.exe manage.py tailwind build --force
.venv\Scripts\python.exe manage.py collectstatic --no-input --clear
.venv\Scripts\python.exe manage.py test apps.finance -v 1
npx playwright test tests/e2e/portal.spec.ts --reporter=list
git add templates/finance/importar.html static/js/finance/importar.js apps/finance/tests.py static/css/tailwind.css
git commit -m "feat(finance): importador com preview e validacao visual de CSV"
```

---

## Task 5: E2E do R3, regressão, evidências e docs

**Files:**
- Create: `tests/e2e/entries_r3.spec.ts`
- Modify: `docs/retrofit/loops.md`
- Update: `docs/retrofit/evidencias/R3-depois/`

- [ ] **Step 1: Escrever o E2E**

Cobrir: fluxo completo Rascunho → Enviado → Aprovado (focal_pdi salva rascunho → envia; erica aprova no kanban), devolução via modal com justificativa, período fechado sem botões de ação, preview CSV (válido sem erros, inválido com erros), toast visível.

- [ ] **Step 2: Rodar até verde; evidências e regressão**

```powershell
npx playwright test tests/e2e/entries_r3.spec.ts --reporter=list
$env:EVIDENCIA_DIR="docs/retrofit/evidencias/R3-depois"; npx playwright test tests/e2e/screenshots.spec.ts
.venv\Scripts\python.exe manage.py test
npx playwright test
```

- [ ] **Step 3: Atualizar `docs/retrofit/loops.md`** (R3 concluído, entregáveis, totais) e commit:

```powershell
git add tests/e2e/entries_r3.spec.ts docs/retrofit/loops.md docs/retrofit/evidencias/R3-depois
git commit -m "test(entries): e2e do R3 e evidencias"
```

---

## Self-review (cobertura da spec R3)

- Lista de indicadores com filtros QTD/MON/PER/TXT: Task 2. ✔
- Formulário com validação em tempo real (Alpine): Task 2. ✔
- Kanban Rascunho/Enviado/Aprovado/Devolvido (sem drag, botões acessíveis): Task 3. ✔
- Timeline de aprovação (auditoria): Tasks 1 e 3. ✔
- Modal de devolução com justificativa obrigatória: Task 3. ✔
- Importador com preview e validação visual: Task 4. ✔
- Período fechado bloqueado (UI + backend): Tasks 2 e 5. ✔
- Toasts consistentes: Task 2. ✔
- URLs/regras/labels preservados + regressão: Global Constraints e Task 5. ✔
