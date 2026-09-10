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
