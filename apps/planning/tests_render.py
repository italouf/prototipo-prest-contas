"""Guarda de regressão do render do painel anual (L9).

Com LANGUAGE_CODE=pt-br, floats/Decimals renderizam com vírgula — o que é
correto no texto visível, mas inválido dentro de atributos SVG e de
<input type="number">. Estes testes quebram se a localização vazar para
esses atributos.
"""
import re

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.planning.tests import criar_base_anual

ATRIBUTO_COM_VIRGULA = re.compile(r'(?:x|y|width|height|rx|viewBox|opacity)="[^"]*\d,\d')


class RenderPainelAnualTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        criar_base_anual()

    def setUp(self):
        garantir_grupos()
        self.master = adicionar_grupo(
            User.objects.create_user(username="l9_master", password="x"), "Master")
        self.client.force_login(self.master)

    def test_svg_sem_virgula_em_atributos_nos_10_estados(self):
        for ano in ("todos", "2024", "2025", "2026", "2027"):
            for base in ("fin", "fis"):
                with self.subTest(ano=ano, base=base):
                    resposta = self.client.get(
                        reverse("core:dashboard"), {"ano": ano, "base": base})
                    self.assertEqual(resposta.status_code, 200)
                    html = resposta.content.decode()
                    achados = ATRIBUTO_COM_VIRGULA.findall(html)
                    self.assertEqual(achados, [], f"atributos com vírgula: {achados[:3]}")

    def test_barras_tem_dimensoes_validas(self):
        resposta = self.client.get(reverse("core:dashboard"))
        html = resposta.content.decode()
        larguras = re.findall(r'<rect[^>]*width="([0-9.]+)"', html)
        self.assertGreater(len(larguras), 20)
        self.assertTrue(all(float(w) > 0 for w in larguras))
        self.assertEqual(html.count('viewBox="0 0 430 268"'), 3)
        for fonte in ("ppi", "at", "outras"):
            self.assertContains(resposta, f'data-testid="chart-fonte-{fonte}"')

    def test_editor_usa_ponto_decimal_em_inputs_number(self):
        resposta = self.client.get(reverse("core:dashboard"))
        html = resposta.content.decode()
        self.assertContains(resposta, 'value="1.75"')
        self.assertNotContains(resposta, 'value="1,75"')

    def test_rotulos_visiveis_continuam_em_pt_br(self):
        resposta = self.client.get(reverse("core:dashboard"))
        html = resposta.content.decode()
        self.assertIn("7,75", html)
        self.assertIn("R$ milhões", html)
