"""Testes da stack de front-end do retrofit (R0)."""
from django.conf import settings
from django.template import Context, Template
from django.test import SimpleTestCase, TestCase, override_settings
from django_cotton.compiler_regex import CottonCompiler


class FrontendStackTestes(SimpleTestCase):
    def test_apps_de_frontend_instaladas(self):
        for app in (
            "django_cotton.apps.SimpleAppConfig",
            "django_tailwind_cli",
            "django_htmx",
            "template_partials.apps.SimpleAppConfig",
        ):
            self.assertIn(app, settings.INSTALLED_APPS)

    def test_htmx_middleware_instalado(self):
        self.assertIn("django_htmx.middleware.HtmxMiddleware", settings.MIDDLEWARE)

    def test_source_css_fora_dos_arquivos_estaticos(self):
        origem = (settings.BASE_DIR / settings.TAILWIND_CLI_SRC_CSS).resolve()
        for static_dir in settings.STATICFILES_DIRS:
            self.assertFalse(
                origem.is_relative_to(static_dir.resolve()),
                f"{origem} não pode ficar dentro de {static_dir} (check W001)",
            )

    def test_partials_renderizam_com_a_stack_instalada(self):
        html = Template(
            "{% load partials %}"
            "{% partialdef saudacao %}ola{% endpartialdef %}"
            "{% partial saudacao %}"
        ).render(Context())
        self.assertEqual(html, "ola")


class FontesTestes(SimpleTestCase):
    def test_fontes_geradas_para_uso_local(self):
        if not (settings.BASE_DIR / "font").exists():
            self.skipTest("font/ ausente (ambiente sem fontes locais)")
        for rel in (
            "static/fonts/montserrat/Montserrat-Variable.woff2",
            "static/fonts/myriad-pro/MyriadPro-Regular.woff2",
            "static/fonts/jetbrains-mono/JetBrainsMono-Regular.woff2",
        ):
            self.assertTrue((settings.BASE_DIR / rel).exists(), f"{rel} não gerado")


class AssetsVendorizadosTestes(SimpleTestCase):
    def test_assets_presentes(self):
        for rel in (
            "static/js/vendor/htmx.min.js",
            "static/js/vendor/head-support.js",
            "static/js/vendor/alpine.min.js",
            "static/js/vendor/chart.umd.js",
            "static/icons/sprite.svg",
        ):
            caminho = settings.BASE_DIR / rel
            self.assertTrue(caminho.exists(), f"{rel} ausente")
            self.assertGreater(caminho.stat().st_size, 500, f"{rel} vazio")


class TailwindBuildTestes(SimpleTestCase):
    def test_css_build_inclui_tokens_quiin(self):
        caminho = settings.BASE_DIR / "static" / "css" / "tailwind.css"
        self.assertTrue(caminho.exists(), "rode manage.py tailwind build")
        conteudo = caminho.read_text(encoding="utf-8").lower()
        self.assertIn("--color-quiin-navy", conteudo)
        self.assertIn("#04047e", conteudo)
        self.assertIn("--font-display", conteudo)


class ComponentesUITestes(SimpleTestCase):
    def render(self, source, **contexto):
        compilado = CottonCompiler().process(source)
        return Template(compilado).render(Context(contexto))

    def test_button_primary(self):
        html = self.render('<c-ui.button variant="primary">Salvar</c-ui.button>')
        self.assertIn("bg-quiin-navy", html)
        self.assertIn("Salvar", html)
        self.assertIn('type="button"', html)

    def test_button_ghost_tamanho_sm(self):
        html = self.render('<c-ui.button variant="ghost" size="sm">Voltar</c-ui.button>')
        self.assertIn("bg-transparent", html)
        self.assertIn("px-3", html)

    def test_button_href_renderiza_link(self):
        html = self.render('<c-ui.button href="/x/">Ir</c-ui.button>')
        self.assertIn('<a href="/x/"', html)

    def test_badge_pilar(self):
        html = self.render('<c-ui.badge pillar="PDI">PDI</c-ui.badge>')
        self.assertIn("text-pillar-pdi", html)

    def test_input_com_erro_tem_aria(self):
        html = self.render('<c-ui.input name="valor" label="Valor" error="Obrigatório" />')
        self.assertIn('aria-invalid="true"', html)
        self.assertIn("Obrigatório", html)

    def test_card_com_slots(self):
        html = self.render('<c-ui.card><c-slot name="header">Topo</c-slot>Corpo</c-ui.card>')
        self.assertIn("Topo", html)
        self.assertIn("Corpo", html)

    def test_table_slots(self):
        html = self.render(
            '<c-ui.table><c-slot name="head"><tr><th>H</th></tr></c-slot>'
            '<c-slot name="body"><tr><td>D</td></tr></c-slot></c-ui.table>'
        )
        self.assertIn("<th>H</th>", html)
        self.assertIn("<td>D</td>", html)

    def test_icon_usa_sprite(self):
        html = self.render('<c-ui.icon name="check" />')
        self.assertIn("icons/sprite", html)
        self.assertIn("#check", html)
        self.assertIn('aria-hidden="true"', html)


class DevDesignSystemTestes(TestCase):
    @override_settings(DEBUG=True)
    def test_pagina_disponivel_em_debug(self):
        resposta = self.client.get("/dev/design-system/")
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'data-testid="page-design-system"')

    @override_settings(DEBUG=False)
    def test_pagina_indisponivel_fora_de_debug(self):
        resposta = self.client.get("/dev/design-system/")
        self.assertEqual(resposta.status_code, 404)


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


class ToastsTestes(TestCase):
    def test_toasts_aparecem_com_mensagem(self):
        from datetime import date

        from django.contrib.auth.models import Group
        from django.urls import reverse

        from apps.accounts.models import User
        from apps.indicators.models import Indicador
        from apps.periods.models import Periodo
        from apps.pillars.models import Pilar

        grupo, _ = Group.objects.get_or_create(name="Master")
        user = User.objects.create_user(username="toast_user", password="x")
        user.groups.add(grupo)
        pilar = Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=1)
        indicador = Indicador.objects.create(pilar=pilar, codigo="PDI-PROJ-INI", nome="Projetos iniciados", tipo="QTD")
        periodo = Periodo.objects.create(competencia=date(2026, 6, 1), status="ABERTO", aberto_por=user)
        self.client.force_login(user)
        resposta = self.client.post(
            reverse("entries:formulario", args=[periodo.pk, pilar.pk]),
            {f"valor_{indicador.pk}": "1", "salvar": "1"},
            follow=True,
        )
        self.assertContains(resposta, "messages pointer-events-none fixed")


class BundleTestes(SimpleTestCase):
    """Orçamento de bundle do R6 (gzip)."""

    def _gzip_kb(self, rel):
        import gzip

        caminho = settings.BASE_DIR / rel
        return len(gzip.compress(caminho.read_bytes())) / 1024

    def test_css_dentro_do_orcamento(self):
        self.assertLess(self._gzip_kb("static/css/tailwind.css"), 150)

    def test_js_por_pagina_dentro_do_orcamento(self):
        total = sum(
            self._gzip_kb(rel)
            for rel in (
                "static/js/vendor/htmx.min.js",
                "static/js/vendor/head-support.js",
                "static/js/vendor/alpine.min.js",
                "static/js/vendor/chart.umd.js",
            )
        )
        self.assertLess(total, 200)
