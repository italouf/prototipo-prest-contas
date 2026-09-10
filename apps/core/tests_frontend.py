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
            "static/fonts/panton/Panton-Regular.woff2",
            "static/fonts/myriad-pro/MyriadPro-Regular.woff2",
            "static/fonts/jetbrains-mono/JetBrainsMono-Regular.woff2",
        ):
            self.assertTrue((settings.BASE_DIR / rel).exists(), f"{rel} não gerado")


class AssetsVendorizadosTestes(SimpleTestCase):
    def test_assets_presentes(self):
        for rel in (
            "static/js/vendor/htmx.min.js",
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
