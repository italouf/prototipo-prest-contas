"""Testes de autenticação (RF-001 a RF-003, RF-100 a RF-106)."""
import re
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import resolve, reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.audit.models import AuditLog
from apps.core.permissions import adicionar_grupo, garantir_grupos
from .models import User

TEST_STORAGES = {
    **settings.STORAGES,
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

@override_settings(STORAGES=TEST_STORAGES)
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

    def test_login_preserva_destino_e_usuario_apos_erro(self):
        resposta = self.client.post(reverse("accounts:login"), {
            "username": "erica", "password": "errada", "next": "/auditoria/",
        })
        self.assertContains(resposta, 'value="erica"')
        self.assertContains(resposta, 'name="next" value="/auditoria/"')
        resposta = self.client.post(reverse("accounts:login"), {
            "username": "erica", "password": "erica123", "next": "/auditoria/",
        })
        self.assertRedirects(resposta, "/auditoria/", fetch_redirect_response=False)

    def test_login_nao_redireciona_para_site_externo(self):
        resposta = self.client.post(reverse("accounts:login"), {
            "username": "erica", "password": "erica123", "next": "https://externo.example/",
        })
        self.assertRedirects(resposta, reverse("core:dashboard"), fetch_redirect_response=False)

    def test_login_contem_links_publicos_e_novo_logo(self):
        resposta = self.client.get(reverse("accounts:login"))
        self.assertContains(resposta, reverse("accounts:cadastro"))
        self.assertContains(resposta, reverse("accounts:password_reset"))
        self.assertContains(resposta, "img/login/senai-cimatec-correto.png")
        self.assertNotContains(resposta, 'data-testid="sidebar"')


@override_settings(STORAGES=TEST_STORAGES)
class CadastroTestes(TestCase):
    def setUp(self):
        self.dados = {
            "nome": "Pessoa de Teste",
            "username": "pessoa.teste",
            "email": "pessoa@example.com",
            "password1": "SenhaTeste123!",
            "password2": "SenhaTeste123!",
        }

    def test_cadastro_publico_cria_usuario_e_permite_login(self):
        resposta = self.client.post(reverse("accounts:cadastro"), self.dados, follow=True)
        self.assertRedirects(resposta, reverse("accounts:login"))
        self.assertContains(resposta, "Cadastro realizado com sucesso")
        usuario = User.objects.get(username=self.dados["username"])
        self.assertEqual(usuario.nome, self.dados["nome"])
        self.assertEqual(usuario.email, self.dados["email"])
        self.assertTrue(usuario.check_password(self.dados["password1"]))
        self.assertNotEqual(usuario.password, self.dados["password1"])
        self.assertTrue(AuditLog.objects.filter(usuario=usuario, acao="CADASTRO").exists())
        resposta = self.client.post(reverse("accounts:login"), {
            "username": usuario.username, "password": self.dados["password1"],
        })
        self.assertRedirects(resposta, reverse("core:dashboard"), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session["_auth_user_id"]), usuario.pk)

    def test_cadastro_nao_concede_privilegios_informados_no_post(self):
        self.client.post(reverse("accounts:cadastro"), {
            **self.dados, "is_staff": "True", "is_superuser": "True", "groups": "Master",
        })
        usuario = User.objects.get(username=self.dados["username"])
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertFalse(usuario.groups.exists())

    def test_cadastro_recusa_usuario_duplicado(self):
        User.objects.create_user(username=self.dados["username"], password="teste123")
        resposta = self.client.post(reverse("accounts:cadastro"), self.dados)
        self.assertIn("username", resposta.context["form"].errors)
        self.assertEqual(User.objects.count(), 1)

    def test_cadastro_recusa_email_duplicado_sem_diferenciar_maiusculas(self):
        User.objects.create_user(username="existente", email="Pessoa@Example.com", password="teste123")
        resposta = self.client.post(reverse("accounts:cadastro"), self.dados)
        self.assertContains(resposta, "Este e-mail já está cadastrado")
        self.assertEqual(User.objects.count(), 1)

    def test_cadastro_recusa_senhas_diferentes(self):
        resposta = self.client.post(reverse("accounts:cadastro"), {**self.dados, "password2": "OutraSenha123!"})
        self.assertIn("password2", resposta.context["form"].errors)
        self.assertFalse(User.objects.exists())
        self.assertContains(resposta, 'aria-invalid="true"')

    def test_cadastro_recusa_senha_curta(self):
        resposta = self.client.post(reverse("accounts:cadastro"), {
            **self.dados, "password1": "abc", "password2": "abc",
        })
        self.assertIn("password2", resposta.context["form"].errors)
        self.assertFalse(User.objects.exists())

    def test_cadastro_valida_campos_obrigatorios_e_email(self):
        resposta = self.client.post(reverse("accounts:cadastro"), {})
        self.assertEqual(set(resposta.context["form"].errors), set(self.dados))
        resposta = self.client.post(reverse("accounts:cadastro"), {**self.dados, "email": "invalido"})
        self.assertIn("email", resposta.context["form"].errors)
        self.assertFalse(User.objects.exists())

    def test_cadastro_normaliza_email(self):
        self.client.post(reverse("accounts:cadastro"), {**self.dados, "email": " Pessoa@Example.COM "})
        self.assertEqual(User.objects.get().email, "pessoa@example.com")

    def test_usuario_logado_e_redirecionado_do_cadastro(self):
        usuario = User.objects.create_user(username="existente", password="teste123")
        self.client.force_login(usuario)
        resposta = self.client.get(reverse("accounts:cadastro"))
        self.assertRedirects(resposta, reverse("core:dashboard"), fetch_redirect_response=False)

    def test_cadastro_exige_csrf(self):
        resposta = Client(enforce_csrf_checks=True).post(reverse("accounts:cadastro"), self.dados)
        self.assertEqual(resposta.status_code, 403)
        self.assertFalse(User.objects.exists())


@override_settings(STORAGES=TEST_STORAGES, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RecuperacaoSenhaTestes(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            username="recuperacao", email="recuperacao@example.com", password="AntigaSenha123!",
        )
        self.uid = urlsafe_base64_encode(force_bytes(self.usuario.pk))
        self.token = default_token_generator.make_token(self.usuario)
        self.link = reverse("accounts:password_reset_confirm", args=[self.uid, self.token])

    def test_envia_email_com_link_e_usuario_corretos(self):
        resposta = self.client.post(reverse("accounts:password_reset"), {"email": self.usuario.email})
        self.assertRedirects(resposta, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.usuario.email])
        link = re.search(r"http://testserver(/\S+)", mail.outbox[0].body).group(1)
        rota = resolve(link)
        self.assertEqual(rota.view_name, "accounts:password_reset_confirm")
        self.assertEqual(rota.kwargs["uidb64"], self.uid)
        self.assertTrue(default_token_generator.check_token(self.usuario, rota.kwargs["token"]))
        self.assertIn(self.usuario.username, mail.outbox[0].body)

    def test_fluxo_completo_redefine_senha_e_permite_login(self):
        self.client.post(reverse("accounts:password_reset"), {"email": self.usuario.email})
        link = re.search(r"http://testserver(/\S+)", mail.outbox[0].body).group(1)
        resposta = self.client.get(link, follow=True)
        self.assertTrue(resposta.context["validlink"])
        # O Django remove o token da URL e o mantém na sessão durante o formulário.
        formulario_url = resposta.redirect_chain[-1][0]
        resposta = self.client.post(formulario_url, {
            "new_password1": "NovaSenha123!", "new_password2": "NovaSenha123!",
        })
        self.assertRedirects(resposta, reverse("accounts:password_reset_complete"))
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("NovaSenha123!"))
        self.assertFalse(self.usuario.check_password("AntigaSenha123!"))
        self.assertTrue(AuditLog.objects.filter(usuario=self.usuario, acao="REDEFINICAO_SENHA").exists())
        self.assertNotIn("_auth_user_id", self.client.session)
        resposta = self.client.post(reverse("accounts:login"), {"username": self.usuario.username, "password": "NovaSenha123!"})
        self.assertRedirects(resposta, reverse("core:dashboard"), fetch_redirect_response=False)
        resposta = Client().get(link, follow=True)
        self.assertFalse(resposta.context["validlink"])

    def test_email_desconhecido_nao_revela_existencia_de_conta(self):
        conhecido = self.client.post(reverse("accounts:password_reset"), {"email": self.usuario.email}, follow=True)
        desconhecido = self.client.post(reverse("accounts:password_reset"), {"email": "desconhecido@example.com"}, follow=True)
        self.assertEqual(conhecido.redirect_chain, desconhecido.redirect_chain)
        self.assertEqual(conhecido.content, desconhecido.content)
        self.assertEqual(len(mail.outbox), 1)

    def test_nao_envia_link_para_usuario_inativo(self):
        self.usuario.is_active = False
        self.usuario.save()
        resposta = self.client.post(reverse("accounts:password_reset"), {"email": self.usuario.email})
        self.assertRedirects(resposta, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_email_invalido_exibe_erro(self):
        resposta = self.client.post(reverse("accounts:password_reset"), {"email": "invalido"})
        self.assertIn("email", resposta.context["form"].errors)
        self.assertEqual(len(mail.outbox), 0)

    def test_token_adulterado_nao_permite_trocar_senha(self):
        link = reverse("accounts:password_reset_confirm", args=[self.uid, "token-invalido"])
        resposta = self.client.post(link, {"new_password1": "Invasao123!", "new_password2": "Invasao123!"})
        self.assertFalse(resposta.context["validlink"])
        self.assertContains(resposta, "Este link é inválido ou expirou")
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("AntigaSenha123!"))

    @override_settings(PASSWORD_RESET_TIMEOUT=1)
    def test_token_expirado_e_recusado(self):
        futuro = default_token_generator._now()
        with patch.object(default_token_generator, "_now", return_value=futuro + timedelta(seconds=2)):
            resposta = self.client.get(self.link, follow=True)
        self.assertFalse(resposta.context["validlink"])
        self.assertContains(resposta, "Solicitar novo link")

    def test_uid_invalido_nao_gera_erro_de_servidor(self):
        resposta = self.client.get(reverse("accounts:password_reset_confirm", args=["invalido", self.token]))
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(resposta.context["validlink"])

    def test_senhas_diferentes_nao_alteram_senha_atual(self):
        resposta = self.client.get(self.link, follow=True)
        formulario_url = resposta.redirect_chain[-1][0]
        resposta = self.client.post(formulario_url, {"new_password1": "NovaSenha123!", "new_password2": "OutraSenha123!"})
        self.assertIn("new_password2", resposta.context["form"].errors)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("AntigaSenha123!"))

    def test_recuperacao_exige_csrf(self):
        resposta = Client(enforce_csrf_checks=True).post(reverse("accounts:password_reset"), {"email": self.usuario.email})
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(len(mail.outbox), 0)

    def test_recuperacao_mantem_layout_publico_mesmo_com_sessao_ativa(self):
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse("accounts:password_reset"))
        self.assertContains(resposta, 'data-testid="login-shell"')
        self.assertNotContains(resposta, 'data-testid="sidebar"')
