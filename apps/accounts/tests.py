"""Testes de autenticação (RF-001 a RF-003, RF-100 a RF-106)."""
from django.test import TestCase
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.core.permissions import adicionar_grupo, garantir_grupos
from .models import User


class LoginTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.erica = User.objects.create_user(username="erica", password="erica123", nome="Érica")
        self.erica = adicionar_grupo(self.erica, "Master")

    def test_usuario_loga_com_credenciais_validas(self):
        resposta = self.client.post(reverse("accounts:login"), {"username": "erica", "password": "erica123"})
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(AuditLog.objects.filter(usuario=self.erica, acao="LOGIN").exists())

    def test_usuario_nao_loga_com_credenciais_invalidas(self):
        resposta = self.client.post(reverse("accounts:login"), {"username": "erica", "password": "senha-errada"})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "não conferem")

    def test_home_requer_login(self):
        resposta = self.client.get(reverse("core:dashboard"))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("accounts:login"), resposta.url)

    def test_logout_aceita_post_e_encerra_sessao(self):
        self.client.force_login(self.erica)
        resposta = self.client.post(reverse("accounts:logout"))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("accounts:login"), resposta.url)
        sessao = self.client.session
        self.assertNotIn("_auth_user_id", sessao)

    def test_logout_nao_aceita_get(self):
        self.client.force_login(self.erica)
        resposta = self.client.get(reverse("accounts:logout"))
        self.assertEqual(resposta.status_code, 405)
