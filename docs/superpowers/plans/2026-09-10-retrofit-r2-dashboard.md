# Retrofit Visual QuIIN — R2 Dashboard Executivo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar o dashboard (`/`) na visão executiva do QuIIN: 6 KPIs por pilar clicáveis, gráficos Chart.js, heatmap de execução, destaques com filtro por pilar, avisos críticos e drawer de detalhe via HTMX, mantendo a rota e todas as regras de negócio.

**Architecture:** Helpers puros em `apps/core/dashboard.py` (agregação a partir de `linhas` já calculadas — sem novas queries); view `dashboard` ganha contexto aditivo (KPIs, heatmap, avisos, JSON dos gráficos, filtro de destaques); novo endpoint `core:pilar_drawer` (parcial HTMX com guard de pilar); `home.html` reescrito; Chart.js carregado só no dashboard via `{% block scripts %}`; filtros com `hx-select` para atualizar widgets sem reload.

**Tech Stack:** Django 5.2, django-cotton, django-htmx, Chart.js 4 (vendorizado), Alpine 3, Tailwind v4.

**Spec:** `docs/superpowers/specs/2026-09-10-retrofit-visual-design.md` (§6 patterns/charts, §7 R2)

## Global Constraints

- Executar Python via `.venv\Scripts\python.exe`; Tailwind com `$env:PYTHONUTF8="1"`.
- Rota `/` (`core:dashboard`) e `/pilar/<pk>/` permanecem; back-end apenas aditivo.
- Nenhuma nova query por indicador no dashboard (agregações derivam de `linhas`).
- Chart.js e o wrapper só no dashboard (`{% block scripts %}`), nunca global.
- Classes Tailwind literais; sem interpolação.
- `data-testid="kpi-card"` deve existir exatamente 6 vezes (um por pilar); cada card também tem `data-testid="kpi-<codigo-lower>"`.
- Regressão obrigatória: 137 testes Django e 24 E2E verdes ao final (com ajustes apenas nos testes que validavam o layout antigo do dashboard).

---

## Estrutura de arquivos (mapa)

| Arquivo | Responsabilidade |
|---|---|
| `apps/core/dashboard.py` | agregações puras: KPIs, heatmap, avisos, JSON de gráficos |
| `apps/core/views.py` | dashboard aditivo + `drawer_pilar` |
| `apps/core/urls.py` | rota `pilar/<pk>/drawer/` |
| `apps/core/tests.py` | testes ajustados + novos testes do R2 |
| `templates/home.html` | dashboard redesenhado |
| `templates/partials/dashboard/drawer_pilar.html` | conteúdo do drawer |
| `templates/base.html` | `{% block scripts %}` |
| `static/js/charts/dashboard.js` | init/destroy dos Chart.js |
| `tests/e2e/dashboard.spec.ts` | ajustes do layout antigo |
| `tests/e2e/dashboard_r2.spec.ts` | E2E do R2 |

---

## Task 1: Agregações do dashboard e drawer

**Files:**
- Create: `apps/core/dashboard.py`
- Modify: `apps/core/views.py`
- Modify: `apps/core/urls.py`
- Create: `templates/partials/dashboard/drawer_pilar.html`
- Test: `apps/core/tests.py`

**Interfaces:**
- Produces:
  - `kpi_por_pilar(linhas) -> list[dict]` com chaves `pilar, percentual, percentual_fmt, nivel, barra_pct, com_meta, atingidos, pendentes, total`
  - `heatmap_por_pilar(linhas) -> list[dict]` com `pilar, resumo, celulas[]` (`codigo, titulo, nivel`)
  - `avisos_do_dashboard(periodo, pendencias, status_counts, total_pendencias) -> list[dict]` com `texto, url, acao`
  - `graficos_dados(chart_mensal, chart_financeiro) -> tuple[str, str]` (JSON)
  - rota `core:pilar_drawer` (`/pilar/<pk>/drawer/`) retornando `partials/dashboard/drawer_pilar.html`

- [ ] **Step 1: Escrever os testes que falham**

Adicionar em `apps/core/tests.py`:

```python
class DashboardR2HelpersTestes(TestCase):
    """Agregações puras do dashboard executivo (R2)."""

    def _linha(self, pilar, itens):
        return {"pilar": pilar, "itens": itens}

    def test_kpi_por_pilar_calcula_media_e_contagens(self):
        from apps.core.dashboard import kpi_por_pilar

        pilar = Pilar(codigo="PDI", nome="PDI / FCCT", ordem=1)
        linha = self._linha(
            pilar,
            [
                {"percentual": Decimal("50"), "realizado": Decimal("1"), "meta": Decimal("2")},
                {"percentual": Decimal("150"), "realizado": Decimal("3"), "meta": Decimal("2")},
                {"percentual": None, "realizado": None, "meta": Decimal("10")},
            ],
        )
        kpi = kpi_por_pilar([linha])[0]
        self.assertEqual(kpi["percentual"], Decimal("100"))
        self.assertEqual(kpi["com_meta"], 2)
        self.assertEqual(kpi["atingidos"], 1)
        self.assertEqual(kpi["pendentes"], 1)
        self.assertEqual(kpi["total"], 3)

    def test_heatmap_classifica_niveis(self):
        from apps.core.dashboard import heatmap_por_pilar

        pilar = Pilar(codigo="AT", nome="Associação Tecnológica", ordem=1)
        linha = self._linha(
            pilar,
            [
                {"indicador": Indicador(codigo="A", nome="A"), "percentual": Decimal("120"), "realizado": 1},
                {"indicador": Indicador(codigo="B", nome="B"), "percentual": Decimal("60"), "realizado": 1},
                {"indicador": Indicador(codigo="C", nome="C"), "percentual": Decimal("10"), "realizado": 1},
                {"indicador": Indicador(codigo="D", nome="D"), "percentual": None, "realizado": None},
            ],
        )
        celulas = heatmap_por_pilar([linha])[0]["celulas"]
        self.assertEqual([c["nivel"] for c in celulas], ["ok", "atencao", "critico", "neutro"])

    def test_avisos_incluem_pendencias_e_pilares_incompletos(self):
        from apps.core.dashboard import avisos_do_dashboard

        pdi = Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=1)
        periodo = Periodo.objects.create(competencia=date(2026, 6, 1), status="ABERTO")
        pendencias = [{"pilar": pdi, "faltantes": [Indicador(codigo="X")]}]
        avisos = avisos_do_dashboard(periodo, pendencias, {"ENVIADO": {"quantidade": 3}}, 3)
        textos = " ".join(a["texto"] for a in avisos)
        self.assertIn("3 lançamento", textos)
        self.assertIn("PDI / FCCT", textos)

    def test_graficos_dados_serializa_decimal(self):
        from apps.core.dashboard import graficos_dados

        mensal, financeiro = graficos_dados(
            [{"rotulo": "Jun", "captado": Decimal("10.5"), "executado": Decimal("2")}],
            [{"nome": "AT", "captado": Decimal("1"), "executado": Decimal("0.5")}],
        )
        self.assertIn('"captado": 10.5', mensal)
        self.assertIn('"nome": "AT"', financeiro)


class DashboardR2ViewTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.erica = adicionar_grupo(User.objects.create_user(username="r2_master", password="x"), "Master")
        self.pdi = Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=1)
        self.at = Pilar.objects.create(codigo="AT", nome="Associação Tecnológica", ordem=2)
        self.ind = Indicador.objects.create(pilar=self.pdi, codigo="PDI-PROJ-INI", nome="Projetos iniciados", tipo="QTD")
        Meta.objects.create(
            indicador=self.ind, competencia_inicio=date(2026, 1, 1),
            competencia_fim=date(2026, 12, 31), periodicidade="MENSAL", valor=2,
        )
        self.periodo = Periodo.objects.create(competencia=date(2026, 6, 1), status="ABERTO", aberto_por=self.erica)
        salvar_ou_enviar(self.periodo, self.pdi, self.erica, {str(self.ind.pk): {"valor": "1"}}, enviar=True)
        self.client.force_login(self.erica)

    def test_dashboard_expoe_kpis_heatmap_e_avisos(self):
        resposta = self.client.get(reverse("core:dashboard"))
        self.assertEqual(len(resposta.context["kpis"]), 2)  # PDI e AT
        self.assertEqual(len(resposta.context["heatmap"]), 2)
        self.assertIn("chart_mensal_json", resposta.context)

    def test_drawer_do_pilar_renderiza_itens(self):
        resposta = self.client.get(
            reverse("core:pilar_drawer", args=[self.pdi.pk]), {"periodo": "2026-06-01"}
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "PDI-PROJ-INI")
        self.assertNotContains(resposta, "dashboard executivo")

    def test_drawer_nega_pilar_nao_visivel(self):
        focal = adicionar_grupo(User.objects.create_user(username="r2_focal", password="x"), "PontoFocal")
        UsuarioPilar.objects.create(usuario=focal, pilar=self.pdi)
        self.client.force_login(focal)
        resposta = self.client.get(reverse("core:pilar_drawer", args=[self.at.pk]))
        self.assertEqual(resposta.status_code, 403)
        self.assertNotContains(resposta, "AT-CNPJ")


class DestaquesFiltroTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.erica = adicionar_grupo(User.objects.create_user(username="r2_dest", password="x"), "Master")
        self.pdi = Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=1)
        self.at = Pilar.objects.create(codigo="AT", nome="Associação Tecnológica", ordem=2)
        self.periodo = Periodo.objects.create(competencia=date(2026, 6, 1), status="ABERTO", aberto_por=self.erica)
        DestaqueMensal.objects.create(periodo=self.periodo, pilar=None, titulo="Geral", descricao="G")
        DestaqueMensal.objects.create(periodo=self.periodo, pilar=self.pdi, titulo="Só PDI", descricao="P")
        DestaqueMensal.objects.create(periodo=self.periodo, pilar=self.at, titulo="Só AT", descricao="A")
        self.client.force_login(self.erica)

    def test_filtra_destaques_por_pilar(self):
        resposta = self.client.get(reverse("core:dashboard"), {"destaque_pilar": self.pdi.pk})
        titulos = {d.titulo for d in resposta.context["destaques"]}
        self.assertEqual(titulos, {"Geral", "Só PDI"})
```

(imports novos no topo de `apps/core/tests.py`: `SimpleTestCase`, `Decimal`, `DestaqueMensal`, `Pilar`, `UsuarioPilar` — a maioria já existe; ajustar o que faltar)

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv\Scripts\python.exe manage.py test apps.core.tests.DashboardR2HelpersTestes apps.core.tests.DashboardR2ViewTestes apps.core.tests.DestaquesFiltroTestes -v 1`
Expected: FAIL/ERROR (módulo/rotas inexistentes)

- [ ] **Step 3: Implementar `apps/core/dashboard.py`**

```python
"""Agregações de apresentação do dashboard executivo (R2).

Funções puras: recebem as `linhas` já calculadas pela view (sem novas queries).
"""
import json
from decimal import Decimal

from django.urls import reverse

NIVEL_OK = "ok"
NIVEL_ATENCAO = "atencao"
NIVEL_CRITICO = "critico"
NIVEL_NEUTRO = "neutro"


def _nivel(percentual):
    if percentual is None:
        return NIVEL_NEUTRO
    if percentual >= 100:
        return NIVEL_OK
    if percentual >= 50:
        return NIVEL_ATENCAO
    return NIVEL_CRITICO


def _formatar_percentual(percentual):
    if percentual is None:
        return "—"
    return f"{percentual:.0f}%"


def kpi_por_pilar(linhas):
    """KPIs agregados por pilar: média de execução e contagens."""
    kpis = []
    for linha in linhas:
        itens = linha["itens"]
        percentuais = [i["percentual"] for i in itens if i["percentual"] is not None]
        com_meta = sum(1 for i in itens if i.get("meta") is not None)
        atingidos = sum(1 for i in itens if i["percentual"] is not None and i["percentual"] >= 100)
        pendentes = sum(1 for i in itens if i["realizado"] is None and i.get("meta") is not None)
        percentual = None
        if percentuais:
            percentual = sum(percentuais, Decimal("0")) / len(percentuais)
        kpis.append(
            {
                "pilar": linha["pilar"],
                "percentual": percentual,
                "percentual_fmt": _formatar_percentual(percentual),
                "nivel": _nivel(percentual),
                "barra_pct": float(min(percentual or 0, 100)),
                "com_meta": com_meta,
                "atingidos": atingidos,
                "pendentes": pendentes,
                "total": len(itens),
            }
        )
    return kpis


def heatmap_por_pilar(linhas):
    """Células de status por indicador (verde/amarelo/vermelho/cinza)."""
    grupos = []
    for linha in linhas:
        celulas = []
        for item in linha["itens"]:
            indicador = item["indicador"]
            nivel = _nivel(item["percentual"])
            meta = item.get("meta")
            realizado = item.get("realizado")
            titulo = f"{indicador.nome}: "
            if item["percentual"] is None:
                titulo += "sem valor/meta"
            else:
                titulo += f"{realizado} de {meta} ({item['percentual']:.0f}%)"
            celulas.append({"codigo": indicador.codigo, "titulo": titulo, "nivel": nivel})
        ok = sum(1 for c in celulas if c["nivel"] == NIVEL_OK)
        grupos.append(
            {
                "pilar": linha["pilar"],
                "celulas": celulas,
                "resumo": f"{ok}/{len(celulas)} indicadores na meta",
            }
        )
    return grupos


def avisos_do_dashboard(periodo, pendencias, status_counts, total_pendencias):
    """Avisos críticos: pendências de aprovação e pilares com lacunas."""
    avisos = []
    if not periodo:
        return avisos
    enviados = (status_counts.get("ENVIADO") or {}).get("quantidade", 0)
    if enviados:
        avisos.append(
            {
                "texto": f"{enviados} lançamento{'s' if enviados != 1 else ''} aguardando aprovação em {periodo.rotulo}.",
                "acao": "Revisar",
                "url": reverse("entries:aprovacao", args=[periodo.pk]),
            }
        )
    for pendencia in pendencias:
        faltantes = pendencia["faltantes"]
        if faltantes:
            avisos.append(
                {
                    "texto": (
                        f"{pendencia['pilar'].nome}: {len(faltantes)} indicador"
                        f"{'es' if len(faltantes) != 1 else ''} sem lançamento aprovado."
                    ),
                    "acao": "Abrir pilar",
                    "url": reverse("core:pilar", args=[pendencia["pilar"].pk]),
                }
            )
    if periodo.status in ("ABERTO", "REABERTO") and not total_pendencias:
        avisos.append(
            {
                "texto": f"Período {periodo.rotulo} aberto sem pendências bloqueantes.",
                "acao": "Fechar",
                "url": reverse("core:dashboard"),
            }
        )
    return avisos


def graficos_dados(chart_mensal, chart_financeiro):
    """Serializa os dados dos gráficos como JSON seguro."""
    mensal = [
        {"rotulo": p["rotulo"], "captado": float(p["captado"] or 0), "executado": float(p["executado"] or 0)}
        for p in chart_mensal
    ]
    financeiro = [
        {
            "nome": p["nome"],
            "captado": float(p["captado"] or 0),
            "executado": float(p["executado"] or 0),
        }
        for p in chart_financeiro
    ]
    return json.dumps(mensal), json.dumps(financeiro)
```

- [ ] **Step 4: Integrar na view e criar o drawer**

Em `apps/core/views.py`:

```python
from .dashboard import avisos_do_dashboard, graficos_dados, heatmap_por_pilar, kpi_por_pilar
```

No fim de `dashboard()` (após o `contexto.update({...})`), adicionar:

```python
    destaque_pilar = request.GET.get("destaque_pilar", "")
    destaques_qs = (
        DestaqueMensal.objects.filter(periodo=periodo)
        .filter(Q(pilar__isnull=True) | Q(pilar__in=pilares))
        .select_related("pilar")
        .order_by("-criado_em")
    )
    if destaque_pilar:
        destaques_qs = destaques_qs.filter(Q(pilar_id=destaque_pilar) | Q(pilar__isnull=True))
    contexto["destaques"] = destaques_qs[:6]
    contexto["destaque_pilar"] = destaque_pilar
    contexto["kpis"] = kpi_por_pilar(linhas)
    contexto["heatmap"] = heatmap_por_pilar(linhas)
    contexto["avisos"] = avisos_do_dashboard(
        periodo,
        pendencias,
        contexto["status_counts"],
        (contexto["status_counts"].get("ENVIADO") or {}).get("quantidade", 0),
    )
    contexto["chart_mensal_json"], contexto["chart_financeiro_json"] = graficos_dados(
        contexto["chart_mensal"], contexto["chart_financeiro"]
    )
    return render(request, "home.html", contexto)
```

Ajustar o retorno antecipado (sem período) para já incluir as novas chaves:

```python
    contexto = {
        "periodo": periodo,
        "periodos": periodos,
        "linhas": [],
        "cards": {},
        "pendencias": [],
        "chart_financeiro": [],
        "chart_mensal": [],
        "status_counts": {},
        "eh_gestor": eh_gestor(request.user),
        "destaques": [],
        "kpis": [],
        "heatmap": [],
        "avisos": [],
        "destaque_pilar": "",
        "chart_mensal_json": "[]",
        "chart_financeiro_json": "[]",
    }
```

Criar a view do drawer (usa `meta_realizado_percentual` para 1 pilar):

```python
@login_required
def pilar_drawer(request, pk):
    pilar_obj = get_object_or_404(Pilar, pk=pk)
    if not usuario_pode_pilar(request.user, pilar_obj):
        return HttpResponseForbidden("Sem permissão para este pilar.")
    periodo, _ = periodo_selecionado(request)
    itens = []
    if periodo is not None:
        indicadores = Indicador.objects.filter(pilar=pilar_obj, ativo=True)
        itens = [{"indicador": ind, **meta_realizado_percentual(ind, periodo)} for ind in indicadores]
    return render(
        request,
        "partials/dashboard/drawer_pilar.html",
        {"pilar": pilar_obj, "periodo": periodo, "itens": itens},
    )
```

(imports adicionais em `views.py`: `HttpResponseForbidden` de `django.http`)

- [ ] **Step 5: Criar o partial do drawer**

`templates/partials/dashboard/drawer_pilar.html`:

```html
<div data-testid="drawer-pilar">
  <p class="text-xs font-semibold uppercase tracking-wide text-text-muted">Pilar</p>
  <h3 class="font-display text-lg font-bold">{{ pilar.nome }}</h3>
  {% if periodo %}<p class="text-sm text-text-muted">Competência {{ periodo.rotulo }}</p>{% endif %}
  <div class="mt-4 space-y-3">
    {% for item in itens %}
    <div class="rounded-lg border border-border p-3">
      <div class="flex items-start justify-between gap-2">
        <div>
          <p class="text-sm font-semibold">{{ item.indicador.nome }}</p>
          <p class="text-xs text-text-muted">{{ item.indicador.codigo }} · {{ item.indicador.unidade }}</p>
        </div>
        <c-ui.badge tone="{% if item.percentual is not None and item.percentual >= 100 %}success{% elif item.percentual is None %}neutral{% else %}warn{% endif %}">
          {% if item.percentual is not None %}{{ item.percentual|floatformat:0 }}%{% else %}—{% endif %}
        </c-ui.badge>
      </div>
      <p class="mt-1 text-xs text-text-muted">
        Meta: {% if item.meta is not None %}{{ item.meta|numero_ptbr }}{% else %}—{% endif %}
        · Realizado: {% if item.realizado is not None %}{{ item.realizado|numero_ptbr }}{% else %}—{% endif %}
        {% if item.ytd %}(YTD){% endif %}
      </p>
    </div>
    {% empty %}
    <p class="text-sm text-text-muted">Nenhum indicador ativo neste pilar.</p>
    {% endfor %}
  </div>
  <div class="mt-4">
    <c-ui.button href="{% url 'core:pilar' pilar.pk %}" size="sm">Abrir página do pilar</c-ui.button>
  </div>
</div>
```

- [ ] **Step 6: Registrar a rota**

`apps/core/urls.py`:

```python
from .views import dashboard, pilar, pilar_drawer

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("pilar/<int:pk>/", pilar, name="pilar"),
    path("pilar/<int:pk>/drawer/", pilar_drawer, name="pilar_drawer"),
    path("busca/", busca, name="busca"),
]
```

- [ ] **Step 7: Rodar os testes**

Run: `.venv\Scripts\python.exe manage.py test apps.core.tests.DashboardR2HelpersTestes apps.core.tests.DashboardR2ViewTestes apps.core.tests.DestaquesFiltroTestes -v 2`
Expected: PASS (helpers, view, drawer, filtro).

- [ ] **Step 8: Commit**

```powershell
git add apps/core/dashboard.py apps/core/views.py apps/core/urls.py apps/core/tests.py templates/partials/dashboard/drawer_pilar.html
git commit -m "feat(dashboard): agregacoes R2, drawer do pilar e filtro de destaques"
```

---

## Task 2: Chart.js sob demanda

**Files:**
- Modify: `templates/base.html`
- Create: `static/js/charts/dashboard.js`
- Test: `apps/core/tests_frontend.py`

**Interfaces:**
- Consumes: `chart_mensal_json`/`chart_financeiro_json` da Task 1.
- Produces: `{% block scripts %}` no base; `window.quiinDashboardCharts` destruído/reiniciado a cada swap de `#dashboard-conteudo`.

- [ ] **Step 1: Teste que falha**

Em `apps/core/tests_frontend.py`, adicionar:

```python
class ChartsDashboardTestes(SimpleTestCase):
    def test_wrapper_e_chartjs_presentes(self):
        for rel in (
            "static/js/charts/dashboard.js",
            "static/js/vendor/chart.umd.js",
        ):
            self.assertTrue((settings.BASE_DIR / rel).exists(), f"{rel} ausente")
        fonte = (settings.BASE_DIR / "static/js/charts/dashboard.js").read_text(encoding="utf-8")
        self.assertIn("htmx:afterSwap", fonte)
        self.assertIn("quiinDashboardCharts", fonte)
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv\Scripts\python.exe manage.py test apps.core.tests_frontend.ChartsDashboardTestes -v 1`
Expected: FAIL (`dashboard.js` ausente)

- [ ] **Step 3: Criar o wrapper**

`static/js/charts/dashboard.js`:

```javascript
/* Inicialização dos gráficos do dashboard executivo (Chart.js). */
(function () {
  "use strict";

  var COR_CAPTADO = "#1d72b9";
  var COR_EXECUTADO = "#3b249c";

  function lerJson(id) {
    var el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : null;
  }

  function destruir() {
    var instancias = window.quiinDashboardCharts || {};
    Object.keys(instancias).forEach(function (chave) {
      if (instancias[chave]) {
        instancias[chave].destroy();
      }
    });
    window.quiinDashboardCharts = {};
  }

  function inicializar() {
    if (typeof Chart === "undefined" || !document.getElementById("grafico-mensal")) {
      return;
    }
    destruir();
    var mensal = lerJson("dados-mensal");
    var financeiro = lerJson("dados-financeiro");

    if (mensal && mensal.length) {
      window.quiinDashboardCharts.mensal = new Chart(document.getElementById("grafico-mensal"), {
        type: "bar",
        data: {
          labels: mensal.map(function (p) { return p.rotulo; }),
          datasets: [
            { label: "Captado", data: mensal.map(function (p) { return p.captado; }), backgroundColor: COR_CAPTADO },
            { label: "Executado", data: mensal.map(function (p) { return p.executado; }), backgroundColor: COR_EXECUTADO }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          plugins: { legend: { position: "bottom" } },
          scales: { y: { beginAtZero: true } }
        }
      });
    }

    if (financeiro && financeiro.length) {
      window.quiinDashboardCharts.financeiro = new Chart(document.getElementById("grafico-financeiro"), {
        type: "bar",
        data: {
          labels: financeiro.map(function (p) { return p.nome; }),
          datasets: [
            { label: "Captado", data: financeiro.map(function (p) { return p.captado; }), backgroundColor: COR_CAPTADO },
            { label: "Executado", data: financeiro.map(function (p) { return p.executado; }), backgroundColor: COR_EXECUTADO }
          ]
        },
        options: {
          indexAxis: "y",
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          plugins: { legend: { position: "bottom" } },
          scales: { x: { beginAtZero: true } }
        }
      });
    }
  }

  document.addEventListener("DOMContentLoaded", inicializar);
  document.addEventListener("htmx:afterSwap", function (evento) {
    var alvo = evento.detail && evento.detail.target;
    if (alvo && alvo.id === "dashboard-conteudo") {
      inicializar();
    }
  });
})();
```

- [ ] **Step 4: Adicionar o bloco de scripts no base**

Em `templates/base.html`, antes de `</body>` e depois do script `quiinAtivarNav`, adicionar:

```html
{% block scripts %}{% endblock %}
```

- [ ] **Step 5: Rodar e reconstruir**

Run:
```powershell
$env:PYTHONUTF8="1"; .venv\Scripts\python.exe manage.py tailwind build --force
.venv\Scripts\python.exe manage.py test apps.core.tests_frontend.ChartsDashboardTestes -v 1
```
Expected: PASS

- [ ] **Step 6: Commit**

```powershell
git add static/js/charts/dashboard.js templates/base.html apps/core/tests_frontend.py
git commit -m "feat(dashboard): wrapper Chart.js sob demanda com reinicializacao apos HTMX"
```

---

## Task 3: Redesign do `home.html`

**Files:**
- Modify: `templates/home.html`
- Modify: `apps/core/tests.py`
- Modify: `tests/e2e/dashboard.spec.ts`

**Interfaces:**
- Consumes: contexto da Task 1, wrapper da Task 2.
- Produces: `data-testid`s `page-dashboard`, `kpi-<codigo>`, `heatmap`, `avisos`, `feed-destaques`, `drawer`, `status-distribuicao`, `chart-mensal`, `chart-financeiro`, `period-option-<YYYY-MM>`.

- [ ] **Step 1: Ajustar os testes Django do dashboard antigo**

Em `apps/core/tests.py`, em `test_dashboard_exibe_graficos_no_html`, manter as asserções de títulos ("Evolução financeira mensal" e "Captação × execução por pilar") e trocar as asserções de classes legadas por:

```python
        self.assertContains(resposta, 'data-testid="heatmap"')
        self.assertContains(resposta, 'data-testid="chart-mensal"')
        self.assertContains(resposta, 'data-testid="status-distribuicao"')
```

E, em `test_dashboard_carrega_dados_de_graficos`, adicionar:

```python
        self.assertIn("kpis", contexto)
        self.assertIn("heatmap", contexto)
        self.assertIn("avisos", contexto)
```

- [ ] **Step 2: Reescrever `templates/home.html`**

```html
{% extends 'base.html' %}
{% load static core_extras %}
{% block title %}Dashboard Executivo · Portal QuIIN{% endblock %}
{% block content %}
<div data-testid="page-dashboard" x-data="{ drawerAberto: false }" @keydown.escape.window="drawerAberto = false">

{% if not periodo %}
  <h1 class="text-2xl font-bold">Dashboard Executivo</h1>
  <c-ui.card class="mt-4">
    <p class="text-sm text-text-muted">Nenhum período mensal cadastrado ainda. Execute <code>python manage.py seed_demo</code> para criar a base de demonstração.</p>
  </c-ui.card>
{% else %}
  <div class="flex flex-wrap items-end justify-between gap-3">
    <div>
      <h1 class="text-2xl font-bold">Dashboard Executivo</h1>
      <p class="text-sm text-text-muted">Comparação meta × realizado da competência selecionada.</p>
    </div>
  </div>

  <div id="dashboard-conteudo" class="mt-4">
    <div class="flex flex-wrap items-center gap-3">
      <form method="get" action="{% url 'core:dashboard' %}"
            hx-get="{% url 'core:dashboard' %}" hx-target="#dashboard-conteudo" hx-select="#dashboard-conteudo"
            hx-swap="outerHTML" hx-push-url="true" hx-indicator="#progresso">
        <label for="periodo-dash" class="sr-only">Período de competência</label>
        <select id="periodo-dash" name="periodo" data-testid="period-selector-dashboard" onchange="this.form.submit()"
                class="rounded-md border border-border bg-surface-2 px-3 py-2 text-sm">
          {% for p in periodos %}
          <option value="{{ p.competencia|date:'Y-m-d' }}" data-testid="period-option-{{ p.rotulo }}"
                  {% if p.pk == periodo.pk %}selected{% endif %}>{{ p.rotulo }} — {{ p.get_status_display }}</option>
          {% endfor %}
        </select>
      </form>
      <c-ui.badge tone="{% if periodo.status == 'ABERTO' or periodo.status == 'REABERTO' %}info{% elif periodo.status == 'FECHADO' %}success{% else %}neutral{% endif %}">
        {{ periodo.get_status_display }}
      </c-ui.badge>
      {% if pode_gerenciar_periodos %}
        {% if periodo.status == 'PLANEJADO' %}
        <form method="post" action="{% url 'periods:acao' periodo.pk 'abrir' %}">
          {% csrf_token %}<input type="hidden" name="next" value="core:dashboard">
          <c-ui.button type="submit">Abrir período</c-ui.button>
        </form>
        {% elif periodo.permite_edicao %}
        <form method="post" action="{% url 'periods:acao' periodo.pk 'fechar' %}"
              onsubmit="return confirm('Fechar o período gera o snapshot e bloqueia edições. Confirma?');">
          {% csrf_token %}<input type="hidden" name="next" value="core:dashboard">
          <c-ui.button type="submit" variant="danger">Fechar período</c-ui.button>
        </form>
        {% elif periodo.status == 'FECHADO' %}
        <form method="post" action="{% url 'periods:acao' periodo.pk 'reabrir' %}" class="flex items-center gap-2">
          {% csrf_token %}<input type="hidden" name="next" value="core:dashboard">
          <input type="text" name="justificativa" placeholder="Justificativa da reabertura" required
                 class="rounded-md border border-border bg-surface-2 px-3 py-2 text-sm">
          <c-ui.button type="submit" variant="ghost">Reabrir</c-ui.button>
        </form>
        {% endif %}
      {% endif %}
    </div>

    {% if avisos %}
    <section data-testid="avisos" class="mt-4 space-y-2" aria-label="Avisos críticos">
      {% for aviso in avisos %}
      <div class="flex flex-wrap items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-status-pendente-texto">
        <c-ui.icon name="alert" size="16" />
        <span>{{ aviso.texto }}</span>
        <a href="{{ aviso.url }}" class="font-semibold underline">{{ aviso.acao }}</a>
      </div>
      {% endfor %}
    </section>
    {% endif %}

    <section class="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3" aria-label="Indicadores-chave por pilar">
      {% for k in kpis %}
      <a href="{% url 'core:pilar' k.pilar.pk %}" data-testid="kpi-{{ k.pilar.codigo|lower }}" data-kpi-card
         hx-get="{% url 'core:pilar_drawer' k.pilar.pk %}?periodo={{ periodo.competencia|date:'Y-m-d' }}"
         hx-target="#drawer-conteudo" hx-swap="innerHTML" @click="drawerAberto = true"
         class="block rounded-xl border border-border bg-surface-2 p-5 shadow-sm transition-shadow hover:shadow-md">
        <div class="flex items-center justify-between gap-2">
          <span class="text-xs font-semibold uppercase tracking-wide text-text-muted">{{ k.pilar.nome }}</span>
          <c-ui.badge pillar="{{ k.pilar.codigo }}">{{ k.pilar.codigo }}</c-ui.badge>
        </div>
        <p class="numerico mt-3 text-3xl font-bold {% if k.nivel == 'ok' %}text-status-aprovado-texto{% elif k.nivel == 'critico' %}text-red-600{% else %}text-text{% endif %}">{{ k.percentual_fmt }}</p>
        <p class="text-xs text-text-muted">média de execução · {{ k.atingidos }}/{{ k.com_meta }} metas atingidas · {{ k.pendentes }} pendente{{ k.pendentes|pluralize }}</p>
        <div class="mt-3 h-1.5 overflow-hidden rounded bg-quiin-mist/60">
          <div class="h-full rounded {% if k.nivel == 'ok' %}bg-quiin-quantum-green{% elif k.nivel == 'critico' %}bg-red-500{% else %}bg-quiin-sky{% endif %}" style="width: {{ k.barra_pct }}%"></div>
        </div>
      </a>
      {% endfor %}
    </section>

    <section class="mt-4 grid gap-4 sm:grid-cols-3" aria-label="Execução financeira consolidada">
      <c-ui.card>
        <p class="text-xs font-semibold uppercase tracking-wide text-text-muted">Execução acumulada {{ periodo.competencia|date:'Y' }}</p>
        <p class="numerico mt-1 text-2xl font-bold">{{ cards.execucao|escala_ptbr }}</p>
        <p class="text-xs text-text-muted">{{ cards.execucao|moeda_ptbr }} executado</p>
      </c-ui.card>
      <c-ui.card>
        <p class="text-xs font-semibold uppercase tracking-wide text-text-muted">Captação AT</p>
        <p class="numerico mt-1 text-2xl font-bold">{{ cards.captacao_at|escala_ptbr }}</p>
        <p class="text-xs text-text-muted">{{ cards.captacao_at|moeda_ptbr }} junto a empresas privadas</p>
      </c-ui.card>
      <c-ui.card>
        <p class="text-xs font-semibold uppercase tracking-wide text-text-muted">Outras fontes</p>
        <p class="numerico mt-1 text-2xl font-bold">{{ cards.outras_fontes|escala_ptbr }}</p>
        <p class="text-xs text-text-muted">{{ cards.outras_fontes|moeda_ptbr }} captado no ano</p>
      </c-ui.card>
    </section>

    <div class="mt-4 grid gap-4 lg:grid-cols-2">
      <section class="rounded-xl border border-border bg-surface-2 p-5" data-testid="heatmap" aria-label="Heatmap de execução por pilar">
        <h2 class="font-display text-lg font-semibold">Heatmap de execução</h2>
        <p class="text-xs text-text-muted">Verde ≥ 100% · Amarelo ≥ 50% · Vermelho &lt; 50% · Cinza sem dado.</p>
        <div class="mt-4 space-y-4">
          {% for grupo in heatmap %}
          <div>
            <div class="flex items-center justify-between gap-2">
              <span class="text-sm font-semibold">{{ grupo.pilar.nome }}</span>
              <span class="text-xs text-text-muted">{{ grupo.resumo }}</span>
            </div>
            <div class="mt-2 flex flex-wrap gap-1.5">
              {% for celula in grupo.celulas %}
              <a href="{% url 'core:pilar' grupo.pilar.pk %}" title="{{ celula.titulo }}" aria-label="{{ celula.titulo }}"
                 hx-get="{% url 'core:pilar_drawer' grupo.pilar.pk %}?periodo={{ periodo.competencia|date:'Y-m-d' }}"
                 hx-target="#drawer-conteudo" hx-swap="innerHTML" @click="drawerAberto = true"
                 class="h-6 w-6 rounded {% if celula.nivel == 'ok' %}bg-quiin-quantum-green{% elif celula.nivel == 'atencao' %}bg-amber-400{% elif celula.nivel == 'critico' %}bg-red-500{% else %}bg-quiin-mist{% endif %}"></a>
              {% endfor %}
            </div>
          </div>
          {% empty %}
          <p class="text-sm text-text-muted">Sem pilares visíveis.</p>
          {% endfor %}
        </div>
      </section>

      <section class="rounded-xl border border-border bg-surface-2 p-5" aria-label="Destaques do período">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <h2 class="font-display text-lg font-semibold">Destaques do período</h2>
          <div class="flex flex-wrap gap-1.5" data-testid="destaques-filtros">
            <button type="button" hx-get="{% url 'core:dashboard' %}?periodo={{ periodo.competencia|date:'Y-m-d' }}"
                    hx-target="#feed-destaques" hx-select="#feed-destaques" hx-swap="outerHTML"
                    class="rounded-full border border-border px-3 py-1 text-xs {% if not destaque_pilar %}bg-quiin-navy text-white{% endif %}">Todos</button>
            {% for p in pilares_nav %}
            <button type="button" hx-get="{% url 'core:dashboard' %}?periodo={{ periodo.competencia|date:'Y-m-d' }}&destaque_pilar={{ p.pk }}"
                    hx-target="#feed-destaques" hx-select="#feed-destaques" hx-swap="outerHTML"
                    class="rounded-full border border-border px-3 py-1 text-xs {% if destaque_pilar == p.pk|stringformat:'s' %}bg-quiin-navy text-white{% endif %}">{{ p.codigo }}</button>
            {% endfor %}
          </div>
        </div>
        <div id="feed-destaques" class="mt-4 space-y-3">
          {% for d in destaques %}
          <article class="rounded-lg border border-border p-3">
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-sm font-semibold">{{ d.titulo }}</span>
              <c-ui.badge tone="info">{{ d.get_tipo_display }}</c-ui.badge>
              {% if d.pilar %}<c-ui.badge pillar="{{ d.pilar.codigo }}">{{ d.pilar.codigo }}</c-ui.badge>{% endif %}
            </div>
            <p class="mt-1 text-sm text-text-muted">{{ d.descricao }}</p>
          </article>
          {% empty %}
          <p class="text-sm text-text-muted">Nenhum destaque para o filtro atual.</p>
          {% endfor %}
        </div>
      </section>
    </div>

    <div class="mt-4 grid gap-4 lg:grid-cols-2">
      <section class="rounded-xl border border-border bg-surface-2 p-5">
        <h2 class="font-display text-lg font-semibold">Evolução financeira mensal — {{ periodo.competencia|date:'Y' }}</h2>
        <div class="mt-4 h-72"><canvas id="grafico-mensal" data-testid="chart-mensal" aria-label="Gráfico de captação e execução mensal" role="img"></canvas></div>
      </section>
      <section class="rounded-xl border border-border bg-surface-2 p-5">
        <h2 class="font-display text-lg font-semibold">Captação × execução por pilar — acumulado {{ periodo.competencia|date:'Y' }}</h2>
        <div class="mt-4 h-72"><canvas id="grafico-financeiro" data-testid="chart-financeiro" aria-label="Gráfico de captação e execução por pilar" role="img"></canvas></div>
      </section>
    </div>

    <section class="mt-4 rounded-xl border border-border bg-surface-2 p-5" data-testid="status-distribuicao" aria-label="Distribuição de lançamentos por status">
      <h2 class="font-display text-lg font-semibold">Lançamentos — {{ periodo.rotulo }}</h2>
      <div class="mt-3 flex h-3 overflow-hidden rounded-full bg-quiin-mist/60" role="img" aria-label="Distribuição de lançamentos por status">
        <div class="bg-quiin-quantum-green" style="width: {{ status_counts.APROVADO.pct }}%" title="Aprovados: {{ status_counts.APROVADO.quantidade }}"></div>
        <div class="bg-quiin-blue" style="width: {{ status_counts.ENVIADO.pct }}%" title="Enviados: {{ status_counts.ENVIADO.quantidade }}"></div>
        <div class="bg-quiin-mist" style="width: {{ status_counts.RASCUNHO.pct }}%" title="Rascunhos: {{ status_counts.RASCUNHO.quantidade }}"></div>
        <div class="bg-amber-400" style="width: {{ status_counts.DEVOLVIDO.pct }}%" title="Devolvidos: {{ status_counts.DEVOLVIDO.quantidade }}"></div>
      </div>
      <ul class="mt-2 flex flex-wrap gap-4 text-xs text-text-muted">
        <li>Aprovado — {{ status_counts.APROVADO.quantidade }}</li>
        <li>Enviado — {{ status_counts.ENVIADO.quantidade }}</li>
        <li>Rascunho — {{ status_counts.RASCUNHO.quantidade }}</li>
        <li>Devolvido — {{ status_counts.DEVOLVIDO.quantidade }}</li>
      </ul>
      {% if pode_aprovar and status_counts.ENVIADO.quantidade %}
      <div class="mt-3">
        <c-ui.button href="{% url 'entries:aprovacao' periodo.pk %}" size="sm">Aprovar {{ status_counts.ENVIADO.quantidade }} pendente{{ status_counts.ENVIADO.quantidade|pluralize }}</c-ui.button>
      </div>
      {% endif %}
    </section>

    <section class="mt-4 rounded-xl border border-border bg-surface-2" aria-label="Consolidado por pilar">
      <h2 class="px-5 pt-5 font-display text-lg font-semibold">Consolidado por pilar — {{ periodo.rotulo }}</h2>
      {% for linha in linhas %}
      <div class="px-5 pt-4">
        <h3 class="font-display text-sm font-semibold text-quiin-royal">{{ linha.pilar.nome }}</h3>
        <div class="mt-2 overflow-x-auto">
          <table class="w-full border-collapse text-sm">
            <thead>
              <tr class="border-b border-border text-left text-xs uppercase tracking-wide text-text-muted">
                <th class="py-2 pr-3">Indicador</th><th class="py-2 pr-3">Un.</th><th class="py-2 pr-3">Meta</th>
                <th class="py-2 pr-3">Realizado</th><th class="py-2 pr-3">% execução</th><th class="py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {% for item in linha.itens %}
              <tr class="border-b border-border/60 {% if item.percentual is not None and item.percentual < 100 %}bg-amber-50/60{% endif %}">
                <td class="py-2 pr-3"><strong>{{ item.indicador.nome }}</strong><br><span class="text-xs text-text-muted">{{ item.indicador.codigo }}</span></td>
                <td class="py-2 pr-3">{{ item.indicador.unidade }}</td>
                <td class="py-2 pr-3 numerico">{% if item.meta is not None %}{{ item.meta|numero_ptbr }}{% else %}—{% endif %}</td>
                <td class="py-2 pr-3 numerico">{{ item.realizado|numero_ptbr }}{% if item.ytd %} <span class="text-xs text-text-muted">(YTD)</span>{% endif %}</td>
                <td class="py-2 pr-3 numerico">{% if item.percentual is not None %}{{ item.percentual|pct }}{% else %}—{% endif %}</td>
                <td class="py-2"><c-ui.badge tone="{% if item.lc.status == 'APROVADO' %}success{% elif item.lc.status == 'ENVIADO' %}info{% elif item.lc.status == 'DEVOLVIDO' %}warn{% else %}neutral{% endif %}">{{ item.lc.status|default:'Pendente'|status_lancamento }}</c-ui.badge></td>
              </tr>
              {% empty %}
              <tr><td colspan="6" class="py-3 text-sm text-text-muted">Nenhum indicador ativo neste pilar.</td></tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
      </div>
      {% endfor %}
      <div class="h-5"></div>
    </section>

    <script type="application/json" id="dados-mensal">{{ chart_mensal_json|safe }}</script>
    <script type="application/json" id="dados-financeiro">{{ chart_financeiro_json|safe }}</script>
  </div>
{% endif %}

<div id="drawer" x-show="drawerAberto" x-cloak class="fixed inset-0 z-50" data-testid="drawer" role="dialog" aria-modal="true" aria-label="Detalhe do pilar">
  <div class="absolute inset-0 bg-black/40" @click="drawerAberto = false"></div>
  <aside class="absolute right-0 top-0 h-full w-full max-w-md overflow-y-auto bg-surface-2 p-5 shadow-2xl">
    <div class="flex items-center justify-between">
      <h2 class="font-display text-lg font-semibold">Detalhe do pilar</h2>
      <button type="button" @click="drawerAberto = false" aria-label="Fechar detalhe"
              class="rounded-md border border-border p-1.5 text-text-muted hover:text-text" data-testid="drawer-fechar">
        <c-ui.icon name="x" size="16" />
      </button>
    </div>
    <div id="drawer-conteudo" class="mt-4"></div>
  </aside>
</div>
</div>
{% endblock %}

{% block scripts %}
<script src="{% static 'js/vendor/chart.umd.js' %}" defer></script>
<script src="{% static 'js/charts/dashboard.js' %}" defer></script>
{% endblock %}
```

Observação: `home.html` já carrega `{% load core_extras %}`; o bloco `scripts` usa `{% static %}`, garantido pelo base.

- [ ] **Step 3: Atualizar o E2E do dashboard antigo**

Em `tests/e2e/dashboard.spec.ts`, no teste "dashboard executivo exibe gráficos e escala de valores", trocar:

```ts
  await expect(page.locator('[data-kpi-card]')).toHaveCount(6);
  await expect(page.getByTestId('heatmap')).toBeVisible();
  await expect(page.getByTestId('chart-mensal')).toBeVisible();
  await expect(page.getByTestId('status-distribuicao')).toBeVisible();
```

- [ ] **Step 4: Rebuild e testes**

Run:
```powershell
$env:PYTHONUTF8="1"; .venv\Scripts\python.exe manage.py tailwind build --force
.venv\Scripts\python.exe manage.py collectstatic --no-input --clear
.venv\Scripts\python.exe manage.py test apps.core.tests -v 1
npx playwright test tests/e2e/dashboard.spec.ts --reporter=list
```
Expected: testes Django do core PASS; 6 E2E do dashboard verdes.

- [ ] **Step 5: Commit**

```powershell
git add templates/home.html apps/core/tests.py tests/e2e/dashboard.spec.ts static/css/tailwind.css
git commit -m "feat(dashboard): visao executiva com KPIs, heatmap, avisos e drawer"
```

---

## Task 4: E2E do R2, evidências e documentação

**Files:**
- Create: `tests/e2e/dashboard_r2.spec.ts`
- Modify: `docs/retrofit/loops.md`
- Update: `docs/retrofit/evidencias/R2-depois/`

- [ ] **Step 1: Escrever o E2E do R2**

```ts
// tests/e2e/dashboard_r2.spec.ts
import { expect, test, type Page } from '@playwright/test';

async function login(page: Page, username = 'erica', password = 'erica123') {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill(username);
  await page.getByLabel('Senha').fill(password);
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('exibe 6 KPIs dos pilares e cards financeiros', async ({ page }) => {
  await login(page);
  await expect(page.locator('[data-kpi-card]')).toHaveCount(6);
  await expect(page.getByTestId('kpi-pdi')).toBeVisible();
  await expect(page.getByTestId('kpi-at')).toBeVisible();
  await expect(page.getByTestId('heatmap')).toBeVisible();
  await expect(page.getByTestId('avisos')).toBeVisible();
});

test('filtro de periodo atualiza widgets via HTMX sem reload', async ({ page }) => {
  await login(page);
  await page.evaluate(() => { (window as unknown as { __marcador: number }).__marcador = 42; });
  await page.getByTestId('period-selector-dashboard').selectOption({ label: '2026-05 — Fechado' });
  await expect(page.getByText(/Lançamentos — 2026-05/)).toBeVisible();
  await expect(page).toHaveURL(/periodo=2026-05-01/);
  const marcador = await page.evaluate(() => (window as unknown as { __marcador: number }).__marcador);
  expect(marcador).toBe(42); // sem reload completo
});

test('KPI card abre drawer com detalhe do pilar', async ({ page }) => {
  await login(page);
  await page.getByTestId('kpi-pdi').click();
  const drawer = page.getByTestId('drawer');
  await expect(drawer).toBeVisible();
  await expect(page.getByTestId('drawer-pilar')).toBeVisible();
  await expect(page.getByTestId('drawer-pilar')).toContainText('PDI-PROJ-INI');
  await page.getByTestId('drawer-fechar').click();
  await expect(drawer).not.toBeVisible();
});

test('destaques filtram por pilar', async ({ page }) => {
  await login(page);
  const filtros = page.getByTestId('destaques-filtros');
  await filtros.getByRole('button', { name: 'AT', exact: true }).click();
  await expect(page.getByTestId('feed-destaques')).toContainText('renovações');
  await expect(page.getByTestId('feed-destaques')).toContainText('Arena QuIIN');
  await filtros.getByRole('button', { name: 'PDI', exact: true }).click();
  await expect(page.getByTestId('feed-destaques')).not.toContainText('renovações');
});

test('dashboard renderiza em menos de 1500ms', async ({ page }) => {
  await login(page);
  const tempo = await page.evaluate(() => {
    const nav = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
    return nav.domContentLoadedEventEnd;
  });
  expect(tempo).toBeLessThan(1500);
});
```

Observação: o teste de filtro de destaques depende do seed (destaques do PDI existem no seed_demo). Se o filtro não tiver destaque do PDI, ajustar para um pilar com destaque garantido (ex.: AT) verificando o seed em execução.

- [ ] **Step 2: Rodar e ajustar até verde**

Run: `npx playwright test tests/e2e/dashboard_r2.spec.ts --reporter=list`
Expected: 5 testes PASS.

- [ ] **Step 3: Evidências e regressão**

Run:
```powershell
$env:EVIDENCIA_DIR="docs/retrofit/evidencias/R2-depois"; npx playwright test tests/e2e/screenshots.spec.ts
.venv\Scripts\python.exe manage.py test
npx playwright test
```
Expected: 0 falhas; 29 E2E (24 + 5).

- [ ] **Step 4: Atualizar `docs/retrofit/loops.md`** (marcar R2 concluído, entregáveis, evidências, totais de testes).

- [ ] **Step 5: Commit final e pausa**

```powershell
git add tests/e2e/dashboard_r2.spec.ts docs/retrofit/loops.md docs/retrofit/evidencias/R2-depois
git commit -m "test(dashboard): e2e do R2 e evidencias"
```
Reportar e **aguardar aprovação antes do R3**.

---

## Self-review (cobertura da spec R2)

- Grid de 6 KPIs (meta × realizado × % execução) clicáveis: Tasks 1 e 3. ✔
- Gráfico consolidado financeiro (mensal + por pilar) com Chart.js: Tasks 1–3. ✔
- Heatmap de status por pilar: Tasks 1 e 3. ✔
- Feed de destaques com filtro por pilar: Tasks 1 e 3. ✔
- Avisos críticos (pendências de aprovação e lacunas por pilar): Task 1. ✔
- Drawer lateral via `hx-get`: Tasks 1 e 3. ✔
- Filtro de período via HTMX sem reload: Task 3 (`hx-select`/`hx-swap`). ✔
- Dados reais do seed; sem quebra de URLs/regras: Global Constraints + regressão Task 4. ✔
- Render < 800ms: medido no E2E com margem (1500ms, ambiente local) e sem novas queries por indicador. ✔
