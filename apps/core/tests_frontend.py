"""Testes da stack de front-end do retrofit (R0)."""
from django.conf import settings
from django.template import Context, Template
from django.test import SimpleTestCase


class FrontendStackTestes(SimpleTestCase):
    def test_apps_de_frontend_instaladas(self):
        for app in ("django_cotton", "django_tailwind_cli", "django_htmx", "template_partials"):
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
