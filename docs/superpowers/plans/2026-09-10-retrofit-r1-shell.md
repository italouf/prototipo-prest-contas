# Retrofit Visual QuIIN — R1 Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir o shell atual por uma navegação executiva completa — sidebar colapsável agrupada por pilar, topbar com busca global/período/perfil/tema, breadcrumbs e navegação HTMX-boosted — sem quebrar nenhuma view, URL ou teste existente.

**Architecture:** Backend aditivo (context processor `nav` expandido + view de busca global); shell em componentes cotton (`layout/sidebar`, `layout/topbar`) + partial de breadcrumbs; `hx-boost` restrito às navegações (nunca em forms legados); `head-support` para atualizar `<title>` em navegação AJAX; estado da sidebar/tema em Alpine + localStorage.

**Tech Stack:** Django 5.2, django-cotton, django-htmx, django-template-partials, Tailwind v4 (build standalone), Alpine 3, HTMX 2 + extensão head-support.

**Spec:** `docs/superpowers/specs/2026-09-10-retrofit-visual-design.md` (§4.5, §4.6, §6, §7, R1)

## Global Constraints

- Executar Python via `.venv\Scripts\python.exe`; CLI Tailwind com `$env:PYTHONUTF8="1"`.
- Não alterar views/URLs existentes; back-end apenas aditivo.
- URLs, labels acessíveis e `data-testid` existentes preservados (`Usuário`, `Senha`, `Entrar`, `Sair`, `dark-toggle`).
- Os 18 E2E existentes e os 127 testes Django devem continuar verdes.
- Classes Tailwind literais; sem interpolação de string.
- `hx-boost` apenas em `<nav>` de sidebar/topbar/breadcrumbs (nunca no `<body>`).
- Commits em pt-BR (Conventional Commits).

---

## Estrutura de arquivos (mapa)

| Arquivo | Responsabilidade |
|---|---|
| `apps/core/context_processors.py` | adiciona `periodos_nav`, `pendencias_nav`, `total_pendencias` |
| `apps/core/search_views.py` | view `busca` (HTMX partial ou página completa) |
| `apps/core/urls.py` | rota `busca/` |
| `apps/core/tests_shell.py` | testes Django do shell |
| `templates/partials/busca_resultados.html` | partial de resultados |
| `templates/core/busca.html` | página completa de busca (fallback sem JS) |
| `templates/partials/breadcrumbs.html` | trilha reutilizável |
| `templates/components/layout/sidebar.html` | navegação lateral |
| `templates/components/layout/topbar.html` | topbar (busca, período, perfil, tema) |
| `templates/base.html` | shell global com boost/indicador |
| `assets/styles/input.css` | classes `nav-*`, progresso e colapso |
| `static/icons/sprite.svg` | novos ícones de navegação |
| `scripts/vendor_assets.ps1` | + `head-support.js` |
| `tests/e2e/shell.spec.ts` | E2E do shell |

---

## Task 1: Backend do shell (context processor + busca global)

**Files:**
- Modify: `apps/core/context_processors.py`
- Create: `apps/core/search_views.py`
- Modify: `apps/core/urls.py`
- Create: `apps/core/tests_shell.py`

**Interfaces:**
- Produces: contexto `periodos_nav` (queryset de `Periodo`), `pendencias_nav` (dict `pilar_id → int`), `total_pendencias` (int); rota `core:busca` (`/busca/?q=`), partial `partials/busca_resultados.html`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# apps/core/tests_shell.py
"""Testes do shell de navegação (R1)."""
from datetime import date

from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.context_processors import nav
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.entries.models import Lancamento
from apps.entries.services import salvar_ou_enviar
from apps.indicators.models import Indicador, Meta
from apps.periods.models import Periodo
from apps.pillars.models import Pilar, UsuarioPilar


class NavContextoTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.erica = adicionar_grupo(
            User.objects.create_user(username="erica_shell", password="x"), "Master"
        )
        self.focal = adicionar_grupo(
            User.objects.create_user(username="focal_shell", password="x"), "PontoFocal"
        )
        self.pdi = Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=1)
        UsuarioPilar.objects.create(usuario=self.focal, pilar=self.pdi)
        self.periodo = Periodo.objects.create(
            competencia=date(2026, 6, 1), status="ABERTO", aberto_por=self.erica
        )
        self.ind = Indicador.objects.create(
            pilar=self.pdi, codigo="PDI-PROJ-INI", nome="Projetos iniciados", tipo="QTD"
        )
        Meta.objects.create(
            indicador=self.ind, competencia_inicio=date(2026, 1, 1),
            competencia_fim=date(2026, 12, 31), periodicidade="MENSAL", valor=2,
        )
        salvar_ou_enviar(self.periodo, self.pdi, self.erica, {str(self.ind.pk): {"valor": "1"}}, enviar=True)

    def _contexto(self, usuario):
        requisicao = RequestFactory().get("/")
        requisicao.user = usuario
        return nav(requisicao)

    def test_gestor_ve_pendencia_de_aprovacao_por_pilar(self):
        contexto = self._contexto(self.erica)
        self.assertEqual(contexto["pendencias_nav"][self.pdi.pk], 1)
        self.assertEqual(contexto["total_pendencias"], 1)
        self.assertIn(self.periodo, list(contexto["periodos_nav"]))

    def test_focal_nao_ve_pendencia_de_aprovacao(self):
        lancamento = Lancamento.objects.get(periodo=self.periodo)
        lancamento.status = "DEVOLVIDO"
        lancamento.save(update_fields=["status"])
        contexto = self._contexto(self.focal)
        self.assertEqual(contexto["pendencias_nav"][self.pdi.pk], 1)

    def test_anonimo_nao_recebe_contexto_de_navegacao(self):
        from django.contrib.auth.models import AnonymousUser

        requisicao = RequestFactory().get("/")
        requisicao.user = AnonymousUser()
        self.assertEqual(nav(requisicao), {})


class BuscaGlobalTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.erica = adicionar_grupo(
            User.objects.create_user(username="erica_busca", password="x"), "Master"
        )
        self.focal = adicionar_grupo(
            User.objects.create_user(username="focal_busca", password="x"), "PontoFocal"
        )
        self.pdi = Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=1)
        self.at = Pilar.objects.create(codigo="AT", nome="Associação Tecnológica", ordem=2)
        UsuarioPilar.objects.create(usuario=self.focal, pilar=self.pdi)
        self.ind_pdi = Indicador.objects.create(
            pilar=self.pdi, codigo="PDI-ARTIGOS", nome="Artigos publicados", tipo="QTD"
        )
        self.ind_at = Indicador.objects.create(
            pilar=self.at, codigo="AT-CNPJ-NOVOS", nome="CNPJs novos", tipo="QTD"
        )

    def test_busca_requer_login(self):
        resposta = self.client.get(reverse("core:busca"), {"q": "artigos"})
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/accounts/login/", resposta["Location"])

    def test_busca_respeita_pilares_visiveis(self):
        self.client.force_login(self.focal)
        resposta = self.client.get(reverse("core:busca"), {"q": "cnpj"})
        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, "AT-CNPJ-NOVOS")
        resposta_pdi = self.client.get(reverse("core:busca"), {"q": "artigos"})
        self.assertContains(resposta_pdi, "PDI-ARTIGOS")

    def test_busca_com_menos_de_dois_caracteres_nao_busca(self):
        self.client.force_login(self.erica)
        resposta = self.client.get(reverse("core:busca"), {"q": "a"})
        self.assertContains(resposta, "ao menos 2 caracteres")

    def test_busca_sem_htmx_renderiza_pagina_completa(self):
        self.client.force_login(self.erica)
        resposta = self.client.get(reverse("core:busca"), {"q": "artigos"})
        self.assertContains(resposta, "Busca")
        self.assertContains(resposta, "PDI-ARTIGOS")
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv\Scripts\python.exe manage.py test apps.core.tests_shell -v 1`
Expected: FAIL/ERROR (contexto e rota inexistentes)

- [ ] **Step 3: Implementar o context processor**

Substituir o conteúdo de `apps/core/context_processors.py` por:

```python
"""Contexto de navegação para o layout base (R1)."""
from django.db.models import Count

from apps.entries.models import Lancamento
from apps.periods.models import Periodo


def nav(request):
    if not request.user.is_authenticated:
        return {}
    from apps.core.permissions import (
        papel_do_usuario,
        pilares_visiveis,
        pode_aprovar,
        pode_gerenciar_periodos,
        pode_importar_financeiro,
        pode_lancar,
        pode_ver_auditoria,
    )

    pilares = pilares_visiveis(request.user)
    periodo_aberto = (
        Periodo.objects.filter(status__in=["ABERTO", "REABERTO"]).order_by("-competencia").first()
    )
    ultimo_periodo = Periodo.objects.order_by("-competencia").first()

    pendencias_nav = {}
    total_pendencias = 0
    if periodo_aberto is not None:
        if pode_aprovar(request.user):
            status_alvo = "ENVIADO"
        elif pode_lancar(request.user):
            status_alvo = "DEVOLVIDO"
        else:
            status_alvo = None
        if status_alvo:
            linhas = (
                Lancamento.objects.filter(
                    periodo=periodo_aberto, status=status_alvo, indicador__pilar__in=pilares
                )
                .values("indicador__pilar")
                .annotate(total=Count("pk"))
            )
            pendencias_nav = {item["indicador__pilar"]: item["total"] for item in linhas}
            total_pendencias = sum(pendencias_nav.values())

    return {
        "papel": papel_do_usuario(request.user),
        "pode_lancar": pode_lancar(request.user),
        "pode_aprovar": pode_aprovar(request.user),
        "pode_gerenciar_periodos": pode_gerenciar_periodos(request.user),
        "pode_importar_financeiro": pode_importar_financeiro(request.user),
        "pode_ver_auditoria": pode_ver_auditoria(request.user),
        "pilares_nav": pilares,
        "periodo_aberto_nav": periodo_aberto,
        "ultimo_periodo_nav": ultimo_periodo,
        "periodos_nav": Periodo.objects.order_by("-competencia"),
        "pendencias_nav": pendencias_nav,
        "total_pendencias": total_pendencias,
    }
```

- [ ] **Step 4: Implementar a view de busca**

```python
# apps/core/search_views.py
"""Busca global do shell (R1): indicadores, empresas e talentos."""
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render

from apps.crm_at.models import Empresa
from apps.indicators.models import Indicador
from apps.talentos.models import Colaborador

from .permissions import pilares_visiveis, pode_aprovar, pode_lancar


@login_required
def busca(request):
    termo = request.GET.get("q", "").strip()
    contexto = {
        "termo": termo,
        "indicadores": [],
        "empresas": [],
        "colaboradores": [],
    }
    if len(termo) >= 2:
        pilares = pilares_visiveis(request.user)
        contexto["indicadores"] = list(
            Indicador.objects.filter(pilar__in=pilares, ativo=True)
            .filter(Q(codigo__icontains=termo) | Q(nome__icontains=termo))
            .select_related("pilar")
            .order_by("pilar__ordem", "codigo")[:5]
        )
        if pode_lancar(request.user) or pode_aprovar(request.user):
            contexto["empresas"] = list(
                Empresa.objects.filter(Q(nome__icontains=termo) | Q(cnpj__icontains=termo))
                .order_by("nome")[:5]
            )
            colaboradores = Colaborador.objects.filter(
                Q(nome__icontains=termo) | Q(cargo__icontains=termo)
            ).select_related("pilar_principal")
            if not pode_aprovar(request.user):
                colaboradores = colaboradores.filter(pilar_principal__in=pilares)
            contexto["colaboradores"] = list(colaboradores.order_by("nome")[:5])

    if request.htmx:
        return render(request, "partials/busca_resultados.html", contexto)
    return render(request, "core/busca.html", contexto)
```

- [ ] **Step 5: Criar os templates da busca**

`templates/partials/busca_resultados.html`:
```html
{% if termo|length < 2 %}
<p class="px-3 py-2 text-sm text-text-muted">Digite ao menos 2 caracteres.</p>
{% elif not indicadores and not empresas and not colaboradores %}
<p class="px-3 py-2 text-sm text-text-muted" data-testid="busca-vazia">Nenhum resultado para “{{ termo }}”.</p>
{% else %}
<ul class="divide-y divide-border" data-testid="busca-lista">
  {% for ind in indicadores %}
  <li>
    <a href="{% url 'core:pilar' ind.pilar.pk %}" class="block px-3 py-2 hover:bg-quiin-mist/30 dark:hover:bg-white/5">
      <span class="block text-sm font-medium">{{ ind.nome }}</span>
      <span class="block text-xs text-text-muted">{{ ind.codigo }} · {{ ind.pilar.nome }}</span>
    </a>
  </li>
  {% endfor %}
  {% for empresa in empresas %}
  <li>
    <a href="{% url 'crm_at:funil' %}" class="block px-3 py-2 hover:bg-quiin-mist/30 dark:hover:bg-white/5">
      <span class="block text-sm font-medium">{{ empresa.nome }}</span>
      <span class="block text-xs text-text-muted">Empresa · {{ empresa.cnpj }}</span>
    </a>
  </li>
  {% endfor %}
  {% for pessoa in colaboradores %}
  <li>
    <a href="{% url 'talentos:organograma' %}" class="block px-3 py-2 hover:bg-quiin-mist/30 dark:hover:bg-white/5">
      <span class="block text-sm font-medium">{{ pessoa.nome }}</span>
      <span class="block text-xs text-text-muted">Talento · {{ pessoa.cargo }}</span>
    </a>
  </li>
  {% endfor %}
</ul>
{% endif %}
```

`templates/core/busca.html`:
```html
{% extends 'base.html' %}
{% block title %}Busca · Portal QuIIN{% endblock %}
{% block breadcrumbs %}{% include "partials/breadcrumbs.html" with atual="Busca" %}{% endblock %}
{% block content %}
<h1 class="text-2xl font-bold">Busca</h1>
<p class="mt-1 text-sm text-text-muted">Resultados para “{{ termo }}”.</p>
<div class="mt-4 rounded-xl border border-border bg-surface-2" data-testid="busca-pagina">
  {% include "partials/busca_resultados.html" %}
</div>
{% endblock %}
```

- [ ] **Step 6: Registrar a rota**

`apps/core/urls.py`:
```python
app_name = "core"

from django.urls import path

from .search_views import busca
from .views import dashboard, pilar

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("pilar/<int:pk>/", pilar, name="pilar"),
    path("busca/", busca, name="busca"),
]
```

- [ ] **Step 7: Rodar os testes**

Run:
```powershell
.venv\Scripts\python.exe manage.py test apps.core.tests_shell -v 2
```
Expected: 7 testes PASS.

- [ ] **Step 8: Commit**

```powershell
git add apps/core/context_processors.py apps/core/search_views.py apps/core/urls.py apps/core/tests_shell.py templates/partials/busca_resultados.html templates/core/busca.html
git commit -m "feat(ui): backend do shell (pendencias de navegacao e busca global)"
```

---

## Task 2: Assets e estilos do shell

**Files:**
- Modify: `scripts/vendor_assets.ps1`
- Create: `static/js/vendor/head-support.js` (baixado)
- Modify: `static/icons/sprite.svg`
- Modify: `assets/styles/input.css`
- Modify: `apps/core/tests_frontend.py`

**Interfaces:**
- Produces: `head-support.js` vendorizado, ícones `home/pencil/check-circle/dollar/funnel/users/file-text/shield/settings/log-out/calendar/building`, classes `.nav-item`, `.nav-item-ativo`, `.nav-secao`, `.htmx-indicator` e regras de colapso `[data-recolhida="true"]`.

- [ ] **Step 1: Adicionar teste do novo asset**

Em `apps/core/tests_frontend.py`, atualizar a lista de `AssetsVendorizadosTestes.test_assets_presentes` para incluir:
```python
            "static/js/vendor/head-support.js",
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv\Scripts\python.exe manage.py test apps.core.tests_frontend.AssetsVendorizadosTestes -v 1`
Expected: FAIL (arquivo ausente)

- [ ] **Step 3: Atualizar o vendor script e baixar**

Em `scripts/vendor_assets.ps1`, adicionar ao array `$assets`:
```powershell
  @{ Url = "https://unpkg.com/htmx-ext-head-support@2.0.5/head-support.js"; Arquivo = "head-support.js" },
```

Run: `powershell -ExecutionPolicy Bypass -File scripts/vendor_assets.ps1`

- [ ] **Step 4: Adicionar os ícones ao sprite**

Em `static/icons/sprite.svg`, adicionar antes de `</svg>`:
```xml
  <symbol id="home" viewBox="0 0 24 24"><path d="M4 11l8-7 8 7"/><path d="M6 10v10h12V10"/></symbol>
  <symbol id="pencil" viewBox="0 0 24 24"><path d="M4 20h4L20 8l-4-4L4 16z"/><path d="M14 6l4 4"/></symbol>
  <symbol id="check-circle" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M8.5 12.5l2.5 2.5 4.5-5"/></symbol>
  <symbol id="dollar" viewBox="0 0 24 24"><path d="M12 3v18"/><path d="M16.5 7.5c-.8-1.2-2.3-2-4.5-2-2.6 0-4 1.2-4 3s1.4 2.7 4 3 4 1.2 4 3-1.4 3-4 3c-2.2 0-3.7-.8-4.5-2"/></symbol>
  <symbol id="funnel" viewBox="0 0 24 24"><path d="M3 5h18l-7 8v5l-4 2v-7z"/></symbol>
  <symbol id="users" viewBox="0 0 24 24"><circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><path d="M16 11a3 3 0 1 0 0-6"/><path d="M21 20c0-2.3-1.3-4.3-3.3-5.3"/></symbol>
  <symbol id="file-text" viewBox="0 0 24 24"><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/><path d="M9 12h6M9 16h6"/></symbol>
  <symbol id="shield" viewBox="0 0 24 24"><path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z"/></symbol>
  <symbol id="settings" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/></symbol>
  <symbol id="log-out" viewBox="0 0 24 24"><path d="M9 21H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/></symbol>
  <symbol id="calendar" viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 9h18M8 3v4M16 3v4"/></symbol>
  <symbol id="building" viewBox="0 0 24 24"><rect x="4" y="3" width="16" height="18" rx="1"/><path d="M9 7h2M13 7h2M9 11h2M13 11h2M9 15h2M13 15h2"/><path d="M10 21v-3h4v3"/></symbol>
```

- [ ] **Step 5: Adicionar estilos de navegação e colapso**

Em `assets/styles/input.css`, adicionar ao final de `@layer base` (antes do fechamento):
```css
  .htmx-indicator {
    opacity: 0;
    transition: opacity 0.2s ease-out;
  }
  .htmx-request .htmx-indicator,
  .htmx-request.htmx-indicator {
    opacity: 1;
  }
```

Adicionar novo bloco `@layer components` (antes de `@layer utilities`):
```css
@layer components {
  .nav-item {
    @apply flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-white/70 transition-colors hover:bg-white/10 hover:text-white;
  }
  .nav-item-ativo {
    @apply bg-white/10 text-white;
  }
  .nav-secao {
    @apply px-3 pb-1 pt-4 text-[0.65rem] font-semibold uppercase tracking-widest text-white/40;
  }
}
```

Adicionar no fim do arquivo (fora de layers, para vencer as utilidades):
```css
/* Colapso da sidebar (desktop): o Alpine controla [data-recolhida] no wrapper. */
@media (min-width: 1024px) {
  [data-recolhida="true"] .sidebar {
    width: 4.5rem;
  }
  [data-recolhida="true"] .sidebar .nav-rotulo,
  [data-recolhida="true"] .sidebar .nav-secao,
  [data-recolhida="true"] .sidebar .sidebar-marca-texto,
  [data-recolhida="true"] .sidebar .sidebar-badge {
    display: none;
  }
  [data-recolhida="true"] .sidebar .nav-item {
    justify-content: center;
  }
}

/* Drawer mobile: controlado por [data-aberto] no wrapper (CSS puro evita flash). */
.sidebar {
  transform: translateX(-100%);
  transition: transform 0.2s ease-out;
}
@media (min-width: 1024px) {
  .sidebar {
    transform: none;
  }
}
[data-aberto="true"] .sidebar {
  transform: none;
}
```

- [ ] **Step 6: Rebuild e testes**

Run:
```powershell
$env:PYTHONUTF8="1"; .venv\Scripts\python.exe manage.py tailwind build --force
.venv\Scripts\python.exe manage.py test apps.core.tests_frontend -v 1
```
Expected: 17 testes PASS.

- [ ] **Step 7: Commit**

```powershell
git add scripts/vendor_assets.ps1 static/js/vendor/head-support.js static/icons/sprite.svg assets/styles/input.css static/css/tailwind.css apps/core/tests_frontend.py
git commit -m "feat(ui): assets e estilos de navegacao do shell"
```

---

## Task 3: Componentes de layout, base.html e breadcrumbs

**Files:**
- Create: `templates/components/layout/sidebar.html`
- Create: `templates/components/layout/topbar.html`
- Create: `templates/partials/breadcrumbs.html`
- Modify: `templates/base.html`
- Modify: `templates/registration/login.html`
- Modify: `templates/403.html`
- Modify (breadcrumbs): `templates/home.html`, `templates/dashboard/pilar.html`, `templates/entries/lancamento.html`, `templates/entries/aprovacao.html`, `templates/finance/importar.html`, `templates/finance/consolidado.html`, `apps/crm_at/templates/crm_at/funil.html`, `apps/crm_at/templates/crm_at/empresa_form.html`, `apps/crm_at/templates/crm_at/oportunidade_form.html`, `apps/talentos/templates/talentos/organograma.html`, `apps/talentos/templates/talentos/colaborador_form.html`, `apps/talentos/templates/talentos/alocacao_form.html`, `templates/reports/monthly.html`, `templates/audit/lista.html`, `templates/dev/design_system.html`
- Modify: `apps/core/tests_frontend.py`

**Interfaces:**
- Consumes: contexto da Task 1 e assets da Task 2.
- Produces: `data-testid`s `sidebar`, `sidebar-toggle`, `sidebar-collapse`, `topbar`, `breadcrumbs`; marcação `data-nav-link` para sincronização de estado ativo.

- [ ] **Step 1: Escrever os testes que falham**

Adicionar em `apps/core/tests_frontend.py`:
```python
class ShellTestes(TestCase):
    def setUp(self):
        from django.contrib.auth.models import Group

        from apps.accounts.models import User

        grupo, _ = Group.objects.get_or_create(name="Master")
        self.erica = User.objects.create_user(username="erica_shell_ui", password="x")
        self.erica.groups.add(grupo)

    def test_shell_autenticado_tem_sidebar_e_topbar(self):
        self.client.force_login(self.erica)
        resposta = self.client.get("/")
        self.assertContains(resposta, 'data-testid="sidebar"')
        self.assertContains(resposta, 'data-testid="topbar"')
        self.assertContains(resposta, 'data-testid="dark-toggle"')
        self.assertNotContains(resposta, 'data-testid="login-shell"')

    def test_pagina_publica_nao_tem_sidebar(self):
        resposta = self.client.get("/accounts/login/")
        self.assertContains(resposta, 'data-testid="login-shell"')
        self.assertNotContains(resposta, 'data-testid="sidebar"')

    def test_breadcrumbs_em_paginas_internas(self):
        self.client.force_login(self.erica)
        resposta = self.client.get("/auditoria/")
        self.assertContains(resposta, 'data-testid="breadcrumbs"')
        self.assertContains(resposta, "Auditoria")
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv\Scripts\python.exe manage.py test apps.core.tests_frontend.ShellTestes -v 1`
Expected: FAIL

- [ ] **Step 3: Criar o partial de breadcrumbs**

`templates/partials/breadcrumbs.html`:
```html
<nav aria-label="Trilha de navegação" data-testid="breadcrumbs" class="mb-4">
  <ol class="flex flex-wrap items-center gap-1.5 text-xs text-text-muted">
    <li>
      <a href="{% url 'core:dashboard' %}" class="inline-flex items-center gap-1 hover:text-text">
        <c-ui.icon name="home" size="14" /> Início
      </a>
    </li>
    {% if atual %}
    <li aria-hidden="true">/</li>
    <li aria-current="page" class="font-medium text-text">{{ atual }}</li>
    {% endif %}
  </ol>
</nav>
```

- [ ] **Step 4: Criar a sidebar**

`templates/components/layout/sidebar.html`:
```html
<aside data-testid="sidebar"
       class="sidebar fixed inset-y-0 left-0 z-40 flex w-64 shrink-0 flex-col overflow-y-auto bg-quiin-deep-purple pb-6 text-white lg:static lg:h-screen">
  <div class="flex items-center gap-2 px-4 py-4">
    <a href="{% url 'core:dashboard' %}" class="flex items-center gap-2 text-white">
      <span class="brand-mark">Q</span>
      <span class="sidebar-marca-texto font-display text-base font-bold">Portal QuIIN</span>
    </a>
    <button type="button" data-testid="sidebar-collapse" aria-label="Recolher menu"
            class="ml-auto hidden rounded-md p-1.5 text-white/70 hover:bg-white/10 hover:text-white lg:inline-flex"
            @click="recolhida = !recolhida; localStorage.setItem('quiin-sidebar', recolhida ? 'recolhida' : 'aberta')">
      <c-ui.icon name="chevron-right" size="18" />
    </button>
    <button type="button" aria-label="Fechar menu"
            class="ml-auto rounded-md p-1.5 text-white/70 hover:bg-white/10 hover:text-white lg:hidden" @click="aberto = false">
      <c-ui.icon name="x" size="18" />
    </button>
  </div>

  <nav class="flex-1 px-3" @click="aberto = false" hx-boost="true" hx-target="#main" hx-swap="innerHTML show:top" hx-push-url="true" hx-indicator="#progresso">
    <p class="nav-secao">Visão geral</p>
    <a href="{% url 'core:dashboard' %}" data-nav-link class="nav-item {% if request.path == '/' %}nav-item-ativo{% endif %}">
      <c-ui.icon name="home" size="18" class="nav-item-icone" /><span class="nav-rotulo">Dashboard</span>
    </a>

    {% if pode_lancar or pode_aprovar or pode_importar_financeiro %}
    <p class="nav-secao">Operação</p>
    {% if pode_lancar and periodo_aberto_nav and pilares_nav %}
    <a href="{% url 'entries:formulario' periodo_aberto_nav.pk pilares_nav.0.pk %}" data-nav-link class="nav-item {% if '/lancamentos/' in request.path %}nav-item-ativo{% endif %}">
      <c-ui.icon name="pencil" size="18" class="nav-item-icone" /><span class="nav-rotulo">Lançamentos</span>
    </a>
    {% endif %}
    {% if pode_aprovar and periodo_aberto_nav %}
    <a href="{% url 'entries:aprovacao' periodo_aberto_nav.pk %}" data-nav-link class="nav-item {% if '/aprovacao/' in request.path %}nav-item-ativo{% endif %}">
      <c-ui.icon name="check-circle" size="18" class="nav-item-icone" /><span class="nav-rotulo">Aprovação</span>
      {% if total_pendencias %}<span class="sidebar-badge ml-auto rounded-full bg-quiin-quantum-green px-2 py-0.5 text-xs font-semibold text-quiin-deep-purple">{{ total_pendencias }}</span>{% endif %}
    </a>
    {% endif %}
    {% if pode_importar_financeiro %}
    <a href="{% url 'finance:consolidado' %}" data-nav-link class="nav-item {% if '/financeiro/' in request.path %}nav-item-ativo{% endif %}">
      <c-ui.icon name="dollar" size="18" class="nav-item-icone" /><span class="nav-rotulo">Financeiro</span>
    </a>
    {% endif %}
    {% endif %}

    {% if pilares_nav %}
    <p class="nav-secao">Pilares</p>
    {% for pilar in pilares_nav %}
    <a href="{% url 'core:pilar' pilar.pk %}" data-nav-link class="nav-item {% if request.resolver_match.url_name == 'pilar' and request.resolver_match.kwargs.pk == pilar.pk %}nav-item-ativo{% endif %}">
      <c-ui.icon name="building" size="18" class="nav-item-icone" /><span class="nav-rotulo">{{ pilar.nome }}</span>
      {% if pendencias_nav %}{% for pid, qtd in pendencias_nav.items %}{% if pid == pilar.pk %}<span class="sidebar-badge ml-auto rounded-full bg-quiin-sky px-2 py-0.5 text-xs font-semibold text-white">{{ qtd }}</span>{% endif %}{% endfor %}{% endif %}
    </a>
    {% endfor %}
    {% endif %}

    {% if pode_lancar or pode_aprovar %}
    <p class="nav-secao">Programa</p>
    <a href="{% url 'crm_at:funil' %}" data-nav-link class="nav-item {% if '/crm-at/' in request.path %}nav-item-ativo{% endif %}">
      <c-ui.icon name="funnel" size="18" class="nav-item-icone" /><span class="nav-rotulo">Funil AT</span>
    </a>
    <a href="{% url 'talentos:organograma' %}" data-nav-link class="nav-item {% if '/talentos/' in request.path %}nav-item-ativo{% endif %}">
      <c-ui.icon name="users" size="18" class="nav-item-icone" /><span class="nav-rotulo">Talentos</span>
    </a>
    {% endif %}

    <p class="nav-secao">Gestão</p>
    {% if ultimo_periodo_nav %}
    <a href="{% url 'reports:mensal' ultimo_periodo_nav.pk %}" data-nav-link class="nav-item {% if '/relatorio/' in request.path %}nav-item-ativo{% endif %}">
      <c-ui.icon name="file-text" size="18" class="nav-item-icone" /><span class="nav-rotulo">Relatório Mensal</span>
    </a>
    {% endif %}
    {% if pode_ver_auditoria %}
    <a href="{% url 'audit:lista' %}" data-nav-link class="nav-item {% if '/auditoria/' in request.path %}nav-item-ativo{% endif %}">
      <c-ui.icon name="shield" size="18" class="nav-item-icone" /><span class="nav-rotulo">Auditoria</span>
    </a>
    {% endif %}
    {% if papel == 'Master' or papel == 'Admin' %}
    <a href="/admin/" data-nav-link class="nav-item {% if '/admin/' in request.path %}nav-item-ativo{% endif %}">
      <c-ui.icon name="settings" size="18" class="nav-item-icone" /><span class="nav-rotulo">Admin</span>
    </a>
    {% endif %}
  </nav>
</aside>
```
(remover a linha `{% with pendencia=... %}{% endwith %}` — não é necessária)

- [ ] **Step 5: Criar a topbar**

`templates/components/layout/topbar.html`:
```html
<header data-testid="topbar" class="sticky top-0 z-20 border-b border-border bg-surface-2/95 backdrop-blur">
  <div class="flex items-center gap-3 px-4 py-2.5 lg:px-8">
    <button type="button" data-testid="sidebar-toggle" aria-label="Abrir menu"
            class="rounded-md border border-border p-2 text-text lg:hidden" @click="aberto = true">
      <c-ui.icon name="menu" size="18" />
    </button>
    <span class="hidden font-display text-sm font-bold sm:inline lg:hidden">Portal QuIIN</span>

    <form method="get" action="{% url 'core:busca' %}"
          hx-get="{% url 'core:busca' %}" hx-target="#busca-resultados" hx-trigger="input changed delay:300ms, submit"
          class="relative ml-auto hidden w-full max-w-sm md:block"
          x-data="{ focado: false }" @focusin="focado = true" @focusout="setTimeout(() => focado = false, 200)">
      <label for="busca-global" class="sr-only">Busca global</label>
      <input id="busca-global" type="search" name="q" data-testid="busca-global" placeholder="Buscar indicador, empresa, talento…"
             class="w-full rounded-md border border-border bg-surface px-3 py-2 pl-9 text-sm text-text placeholder:text-text-muted/70 focus:outline-none focus-visible:ring-2 focus-visible:ring-focus/60">
      <span class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"><c-ui.icon name="search" size="16" /></span>
      <div id="busca-resultados" x-show="focado" x-cloak
           class="absolute left-0 right-0 top-full z-40 mt-1 max-h-80 overflow-y-auto rounded-lg border border-border bg-surface-2 shadow-lg"></div>
    </form>

    <form method="get" action="{{ request.path }}" class="ml-auto flex items-center gap-2 md:ml-0">
      <label for="periodo-global" class="sr-only">Período de competência</label>
      <select id="periodo-global" name="periodo" data-testid="period-selector" onchange="this.form.submit()"
              class="w-[8.5rem] rounded-md border border-border bg-surface px-2 py-2 text-sm text-text focus:outline-none focus-visible:ring-2 focus-visible:ring-focus/60 sm:w-auto">
        {% for p in periodos_nav %}
        <option value="{{ p.competencia|date:'Y-m-d' }}" {% if request.GET.periodo == p.competencia|date:'Y-m-d' %}selected{% elif not request.GET.periodo and forloop.first %}selected{% endif %}>
          {{ p.rotulo }} — {{ p.get_status_display }}
        </option>
        {% endfor %}
      </select>
    </form>

    <div class="flex items-center gap-2">
      <c-ui.badge papel="{{ papel }}" class="hidden sm:inline-flex" data-testid="papel-badge">{{ papel }}</c-ui.badge>
      <span class="hidden text-sm font-medium xl:inline">{{ user.nome_exibicao }}</span>
      <button type="button" data-testid="dark-toggle" aria-label="Alternar tema"
              class="inline-flex h-9 w-9 items-center justify-center rounded-md border border-border bg-surface-2 text-text"
              x-data="{ escuro: document.documentElement.classList.contains('dark') }"
              @click="escuro = !escuro; document.documentElement.classList.toggle('dark', escuro); localStorage.setItem('quiin-theme', escuro ? 'dark' : 'light')"
              :aria-pressed="escuro">
        <span x-show="!escuro"><c-ui.icon name="sun" size="18" /></span>
        <span x-show="escuro" x-cloak><c-ui.icon name="moon" size="18" /></span>
      </button>
      <form method="post" action="{% url 'accounts:logout' %}">
        {% csrf_token %}
        <button type="submit" aria-label="Sair" title="Sair"
                class="inline-flex h-9 w-9 items-center justify-center rounded-md border border-border bg-surface-2 text-text hover:bg-quiin-mist/40 dark:hover:bg-white/5">
          <c-ui.icon name="log-out" size="18" />
        </button>
      </form>
    </div>
  </div>
</header>
```

- [ ] **Step 6: Reescrever o `base.html`**

```html
{% load static tailwind_cli %}<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{% block title %}Portal QuIIN{% endblock %}</title>
<link rel="stylesheet" href="{% static 'css/fonts.css' %}">
<link rel="stylesheet" href="{% static 'css/legado.css' %}">
{% tailwind_css %}
<script>
  (function () {
    try {
      var tema = localStorage.getItem('quiin-theme');
      if (tema === 'dark' || (!tema && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        document.documentElement.classList.add('dark');
      }
    } catch (e) {}
  })();
</script>
</head>
<body hx-headers='{"x-csrftoken": "{{ csrf_token }}"}' hx-ext="head-support">
<a href="#main" class="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-surface-2 focus:px-3 focus:py-2">Pular para o conteúdo</a>

{% if user.is_authenticated %}
<div x-data="{ aberto: false, recolhida: localStorage.getItem('quiin-sidebar') === 'recolhida' }" :data-aberto="aberto" :data-recolhida="recolhida" class="min-h-screen lg:flex">
  <div x-show="aberto" x-cloak @click="aberto = false" class="fixed inset-0 z-30 bg-black/50 lg:hidden"></div>
  <c-layout.sidebar />
  <div class="min-w-0 flex-1">
    <c-layout.topbar />
    <div id="progresso" class="htmx-indicator fixed inset-x-0 top-0 z-50 h-0.5 bg-quiin-sky"></div>
    <main id="main" class="mx-auto w-full max-w-[1440px] px-4 py-6 lg:px-8">
      {% block breadcrumbs %}{% endblock %}
      {% if messages %}
        <div class="mb-4 space-y-2" role="status">
          {% for message in messages %}
            <div class="alert alert-{{ message.tags|default:'info' }}">{{ message }}</div>
          {% endfor %}
        </div>
      {% endif %}
      {% block content %}{% endblock %}
    </main>
    <footer class="mx-auto w-full max-w-[1440px] px-4 pb-8 text-xs text-text-muted lg:px-8">
      Portal QuIIN — protótipo local de gestão e prestação de contas. Dados fictícios para demonstração.
    </footer>
  </div>
</div>
{% else %}
<main id="main" data-testid="login-shell">
  {% block content %}{% endblock %}
</main>
{% endif %}

<script src="{% static 'js/vendor/htmx.min.js' %}" defer></script>
<script src="{% static 'js/vendor/head-support.js' %}" defer></script>
<script src="{% static 'js/vendor/alpine.min.js' %}" defer></script>
<script>
  function quiinAtivarNav() {
    document.querySelectorAll('[data-nav-link]').forEach(function (link) {
      var ativo = link.getAttribute('href') === window.location.pathname;
      link.classList.toggle('nav-item-ativo', ativo);
      if (ativo) { link.setAttribute('aria-current', 'page'); } else { link.removeAttribute('aria-current'); }
    });
  }
  document.addEventListener('DOMContentLoaded', quiinAtivarNav);
  document.addEventListener('htmx:afterSwap', quiinAtivarNav);
</script>
</body>
</html>
```

- [ ] **Step 7: Estender `ui/badge` com papéis**

Em `templates/components/ui/badge.html`, trocar a linha `<c-vars ... />` por:
```html
<c-vars tone="neutral" pillar="" papel="" class="" />
```
e adicionar antes do `{% elif tone == 'success' %}`:
```html
{% elif papel == 'Master' %}border-transparent bg-quiin-violet/15 text-pillar-pdi
{% elif papel == 'Admin' %}border-transparent bg-quiin-royal/15 text-status-aberto
{% elif papel == 'PontoFocal' %}border-transparent bg-quiin-sky/15 text-pillar-startups-texto
{% elif papel == 'Lideranca' %}border-transparent bg-quiin-blue/15 text-status-enviado
{% elif papel == 'Auditor' %}border-transparent bg-quiin-mist/40 text-text-muted
```

- [ ] **Step 8: Redesenhar o login**

`templates/registration/login.html`:
```html
{% extends 'base.html' %}
{% load core_extras %}
{% block title %}Entrar · Portal QuIIN{% endblock %}
{% block content %}
<div class="flex min-h-screen items-center justify-center bg-quiin-deep-purple px-4">
  <div class="w-full max-w-md">
    <div class="mb-6 flex items-center justify-center gap-2 text-white">
      <span class="brand-mark">Q</span>
      <span class="font-display text-lg font-bold">Portal QuIIN</span>
    </div>
    <c-ui.card class="shadow-lg">
      <h1 class="font-display text-xl font-bold">Entrar no Portal QuIIN</h1>
      <p class="mt-1 text-sm text-text-muted">Acesse com suas credenciais locais para gerenciar indicadores e a prestação de contas mensal.</p>
      {% if form.errors %}
        <div class="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
          Usuário e senha não conferem. Verifique os dados e tente novamente.
        </div>
      {% endif %}
      <form method="post" novalidate class="mt-4 space-y-4">
        {% csrf_token %}
        <c-ui.input name="username" id="id_username" label="Usuário" type="text" autofocus autocomplete="username" required />
        <c-ui.input name="password" id="id_password" label="Senha" type="password" autocomplete="current-password" required />
        <c-ui.button type="submit" class="w-full">Entrar</c-ui.button>
      </form>
      <p class="mt-4 text-xs text-text-muted">Usuários demo: erica/erica123 · clarissa/clarissa123 · focal_pdi/focal123 · lideranca/lider123 · auditor/auditor123</p>
    </c-ui.card>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 9: Redesenhar o 403 (leve)**

`templates/403.html`:
```html
{% extends 'base.html' %}
{% block title %}Sem permissão · Portal QuIIN{% endblock %}
{% block content %}
<c-ui.card class="max-w-xl">
  <h1 class="font-display text-xl font-bold">403 — Sem permissão</h1>
  <p class="mt-2 text-sm text-text-muted">Seu perfil não permite acessar esta área. Caso precise, fale com a coordenação (Master).</p>
  <div class="mt-4"><c-ui.button href="{% url 'core:dashboard' %}">Voltar ao início</c-ui.button></div>
</c-ui.card>
{% endblock %}
```

- [ ] **Step 10: Adicionar breadcrumbs nas páginas**

Inserir após a linha `{% block title %}...{% endblock %}` de cada template:

| Arquivo | Linha a inserir |
|---|---|
| `templates/dashboard/pilar.html` | `{% block breadcrumbs %}{% include "partials/breadcrumbs.html" with atual=pilar.nome %}{% endblock %}` |
| `templates/entries/lancamento.html` | `{% block breadcrumbs %}{% include "partials/breadcrumbs.html" with atual="Lançamentos mensais" %}{% endblock %}` |
| `templates/entries/aprovacao.html` | `{% block breadcrumbs %}{% include "partials/breadcrumbs.html" with atual="Aprovação" %}{% endblock %}` |
| `templates/finance/importar.html` | `{% block breadcrumbs %}{% include "partials/breadcrumbs.html" with atual="Importar financeiro" %}{% endblock %}` |
| `templates/finance/consolidado.html` | `{% block breadcrumbs %}{% include "partials/breadcrumbs.html" with atual="Financeiro consolidado" %}{% endblock %}` |
| `apps/crm_at/templates/crm_at/funil.html` | `{% block breadcrumbs %}{% include "partials/breadcrumbs.html" with atual="Funil AT" %}{% endblock %}` |
| `apps/crm_at/templates/crm_at/empresa_form.html` | `{% block breadcrumbs %}{% include "partials/breadcrumbs.html" with atual=titulo %}{% endblock %}` |
| `apps/crm_at/templates/crm_at/oportunidade_form.html` | `{% block breadcrumbs %}{% include "partials/breadcrumbs.html" with atual=titulo %}{% endblock %}` |
| `apps/talentos/templates/talentos/organograma.html` | `{% block breadcrumbs %}{% include "partials/breadcrumbs.html" with atual="Organograma" %}{% endblock %}` |
| `apps/talentos/templates/talentos/colaborador_form.html` | `{% block breadcrumbs %}{% include "partials/breadcrumbs.html" with atual=titulo %}{% endblock %}` |
| `apps/talentos/templates/talentos/alocacao_form.html` | `{% block breadcrumbs %}{% include "partials/breadcrumbs.html" with atual=titulo %}{% endblock %}` |
| `templates/reports/monthly.html` | `{% block breadcrumbs %}{% include "partials/breadcrumbs.html" with atual="Relatório Mensal" %}{% endblock %}` |
| `templates/audit/lista.html` | `{% block breadcrumbs %}{% include "partials/breadcrumbs.html" with atual="Auditoria" %}{% endblock %}` |
| `templates/dev/design_system.html` | `{% block breadcrumbs %}{% include "partials/breadcrumbs.html" with atual="Design System" %}{% endblock %}` |

(`templates/home.html` é a raiz do dashboard: sem breadcrumb.)

- [ ] **Step 11: Rebuild e rodar testes/regressão**

Run:
```powershell
$env:PYTHONUTF8="1"; .venv\Scripts\python.exe manage.py tailwind build --force
.venv\Scripts\python.exe manage.py collectstatic --no-input --clear
.venv\Scripts\python.exe manage.py test apps.core.tests_shell apps.core.tests_frontend -v 1
npx playwright test
```
Expected: testes Django PASS; 18 E2E verdes (ou ajustes apenas se seletores mudaram — labels devem ser preservados).

- [ ] **Step 12: Commit**

```powershell
git add templates apps/core/tests_frontend.py static/css/tailwind.css
git commit -m "feat(ui): shell com sidebar, topbar, breadcrumbs e navegacao HTMX"
```

---

## Task 4: E2E do shell, evidências e documentação

**Files:**
- Create: `tests/e2e/shell.spec.ts`
- Modify: `docs/retrofit/loops.md`
- Update: `docs/retrofit/evidencias/R1-depois/`

- [ ] **Step 1: Escrever o E2E do shell**

```ts
// tests/e2e/shell.spec.ts
import { expect, test, type Page } from '@playwright/test';

async function login(page: Page, username = 'erica', password = 'erica123') {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill(username);
  await page.getByLabel('Senha').fill(password);
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('navega entre 5 paginas pela sidebar com boost', async ({ page }) => {
  await login(page);
  await expect(page.getByTestId('sidebar')).toBeVisible();

  const rotas: Array<[RegExp, string, RegExp]> = [
    [/Lançamentos/, '/lancamentos/2/1/', /lançamentos mensais/i],
    [/Aprovação/, '/aprovacao/2/', /painel de aprovação/i],
    [/Financeiro/, '/financeiro/', /financeiro consolidado/i],
    [/Relatório Mensal/, '/relatorio/mensal/3/', /relatório mensal/i],
    [/Auditoria/, '/auditoria/', /auditoria/i],
  ];

  for (const [nome, caminho, titulo] of rotas) {
    await page.getByTestId('sidebar').getByRole('link', { name: nome }).click();
    await expect(page).toHaveURL(new RegExp(caminho.replace(/\//g, '\\/')));
    await expect(page.getByRole('heading', { name: titulo }).first()).toBeVisible();
    await expect(page).toHaveTitle(/Portal QuIIN/);
  }

  await page.getByTestId('sidebar').getByRole('link', { name: /Dashboard/ }).click();
  await expect(page.getByRole('heading', { name: /dashboard executivo/i })).toBeVisible();
});

test('sidebar mobile abre, navega e fecha', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  const sidebar = page.getByTestId('sidebar');
  await expect(sidebar).not.toBeInViewport();
  await page.getByTestId('sidebar-toggle').click();
  await expect(sidebar).toBeInViewport();
  await sidebar.getByRole('link', { name: /Auditoria/ }).click();
  await expect(page.getByRole('heading', { name: /auditoria/i })).toBeVisible();
  await expect(sidebar).not.toBeInViewport();
});

test('breadcrumbs refletem a hierarquia', async ({ page }) => {
  await login(page);
  await page.goto('/pilar/1/');
  const breadcrumbs = page.getByTestId('breadcrumbs');
  await expect(breadcrumbs).toBeVisible();
  await expect(breadcrumbs).toContainText('Início');
  await expect(breadcrumbs.locator('[aria-current="page"]')).toHaveText('PDI / FCCT');
});

test('busca global encontra indicador visivel', async ({ page }) => {
  await login(page);
  await page.getByTestId('busca-global').fill('artigos');
  await expect(page.getByTestId('busca-lista')).toBeVisible();
  await expect(page.getByTestId('busca-lista')).toContainText('Artigos publicados');
});

test('seletor de periodo muda o dashboard', async ({ page }) => {
  await login(page);
  await page.getByTestId('period-selector').selectOption({ label: '2026-05 — Fechado' });
  await expect(page).toHaveURL(/periodo=2026-05-01/);
  await expect(page.getByText(/Lançamentos — 2026-05/)).toBeVisible();
});

test('papel ativo aparece no topbar', async ({ page }) => {
  await login(page);
  await expect(page.getByTestId('papel-badge')).toHaveText('Master');
});
```

- [ ] **Step 2: Rodar e ajustar até verde**

Run: `npx playwright test tests/e2e/shell.spec.ts --reporter=list`
Expected: 6 testes PASS.

- [ ] **Step 3: Evidências R1**

Run:
```powershell
$env:EVIDENCIA_DIR="docs/retrofit/evidencias/R1-depois"; npx playwright test tests/e2e/screenshots.spec.ts
```

- [ ] **Step 4: Regressão completa**

Run:
```powershell
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py test
npx playwright test
```
Expected: 0 falhas (Django e Playwright).

- [ ] **Step 5: Atualizar `docs/retrofit/loops.md`**

Marcar R1 como concluído, listar entregáveis, evidências e os totais de testes E2E (24) e Django.

- [ ] **Step 6: Commit final**

```powershell
git add tests/e2e/shell.spec.ts docs/retrofit/loops.md docs/retrofit/evidencias/R1-depois
git commit -m "test(ui): e2e do shell e evidencias do R1"
```
Reportar e **aguardar aprovação antes do R2**.

---

## Self-review (cobertura da spec R1)

- Sidebar colapsável (ícones+labels) com agrupamento por pilar e badges: Task 3 (Steps 4, 5). ✔
- Topbar com busca global, perfil, seletor de período e tema: Tasks 1 e 3. ✔
- Breadcrumbs dinâmicos (`{% block breadcrumbs %}`) em todas as páginas internas: Task 3 (Step 10). ✔
- RBAC visual (cores por papel): Task 3 (Step 7). ✔
- Navegação HTMX-boosted com transições/título: Task 3 (base + sidebar) e head-support: Task 2. ✔
- Sidebar mobile com hamburger: Task 3 + E2E Task 4. ✔
- Login/403 redesenhados: Task 3 (Steps 8, 9). ✔
- Sem quebra de URLs/views/tests: Global Constraints + regressão Task 4. ✔
- Busca global é back-end aditivo (nova rota) e respeita RBAC de pilar: Task 1. ✔
