from datetime import date, timedelta
from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.accounts.models import User
from .models import Associado, Plano


class SituacaoVigenciaTestes(SimpleTestCase):
    @patch("apps.gestao_at.models.timezone.localdate", return_value=date(2026, 10, 27))
    def test_faixas_de_vencimento(self, hoje):
        for dias, esperado in [
            (-1, "Vencido"),
            (0, "Vence em até 10 dias"),
            (10, "Vence em até 10 dias"),
            (11, "Vence em até 30 dias"),
            (30, "Vence em até 30 dias"),
            (31, "Vence em até 60 dias"),
            (60, "Vence em até 60 dias"),
            (61, "Vence em até 90 dias"),
            (90, "Vence em até 90 dias"),
            (91, "Vigente"),
        ]:
            with self.subTest(dias=dias):
                associado = Associado(fim_vigencia=hoje.return_value + timedelta(days=dias))
                self.assertEqual(associado.situacao_vigencia, esperado)


class VencimentosPaginaTestes(TestCase):
    @patch("apps.gestao_at.views.pode_ver_associados", return_value=True)
    @patch("apps.gestao_at.models.timezone.localdate", return_value=date(2026, 10, 27))
    def test_faixas_aparecem_na_lista_e_na_carteira(self, hoje, permissao):
        self.client.force_login(User.objects.create_user(username="teste_vencimentos"))
        plano = Plano.objects.create(nome="Plano teste vencimentos", valor_anual=100)
        for dias in (-1, 10, 30, 60, 90, 91):
            Associado.objects.create(
                nome=f"Associado teste {dias}", tipo="Empresa", plano=plano,
                inicio_vigencia=date(2025, 1, 1),
                fim_vigencia=hoje.return_value + timedelta(days=dias),
            )

        resposta = self.client.get(reverse("gestao_at:acompanhamento"))
        self.assertEqual(resposta.status_code, 200)
        html = resposta.content.decode()
        painel = html.split("<h2>Vencimentos e renovações</h2>", 1)[1].split("</section>", 1)[0]
        carteira = html.split("<h2>Carteira de associados</h2>", 1)[1].split("</section>", 1)[0]
        for situacao in ("Vencido", *(f"Vence em até {dias} dias" for dias in (10, 30, 60, 90))):
            self.assertIn(situacao, painel)
            self.assertIn(situacao, carteira)
        self.assertNotIn("Associado teste 91", painel)
        self.assertIn("Vigente", carteira)
        self.assertNotIn('<span class="feature-muted">próximos 90 dias</span>', html)


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class ContatosAssociadosTestes(TestCase):
    def test_contatos_informados_estao_vinculados_aos_associados(self):
        from importlib import import_module

        contatos = import_module("apps.gestao_at.migrations.0004_contatos_informados").CONTATOS
        self.assertEqual(sum(len(lista) for lista in contatos.values()), 20)
        for empresa, lista in contatos.items():
            associado = Associado.objects.get(nome=empresa)
            for nome, email in lista:
                with self.subTest(empresa=empresa, email=email):
                    self.assertTrue(associado.contatos.filter(email=email, nome=nome).exists())

    @patch("apps.gestao_at.views.pode_ver_associados", return_value=True)
    def test_pagina_exibe_todos_os_contatos_e_preserva_email_principal(self, permissao):
        self.client.force_login(User.objects.create_user(username="teste_contatos"))
        associado = Associado.objects.get(nome="BV")
        associado.email = "principal@bv.com.br"
        associado.save(update_fields=["email"])
        for url in (reverse("gestao_at:acompanhamento"), reverse("gestao_at:associado", args=[associado.pk])):
            resposta = self.client.get(url)
            self.assertContains(resposta, "principal@bv.com.br")
            self.assertContains(resposta, "joao.gianvecchio@bv.com.br")
            self.assertContains(resposta, "peterson.nogueira@bv.com.br")


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class LogoAssociadoTestes(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="teste_logo")
        self.client.force_login(self.user)
        self.associado = Associado.objects.get(nome="BV")
        self.url = reverse("gestao_at:associado", args=[self.associado.pk])
        self.logo_url = reverse("gestao_at:associado_logo", args=[self.associado.pk])
        arquivo = BytesIO()
        Image.new("RGB", (2, 2), "red").save(arquivo, format="PNG")
        self.imagem = arquivo.getvalue()

    @patch("apps.gestao_at.views.pode_gerir_associados", return_value=True)
    @patch("apps.gestao_at.views.pode_ver_associados", return_value=True)
    def test_inserir_exibir_substituir_e_remover_logo(self, ver, gerir):
        def enviar(conteudo):
            return self.client.post(self.url, {
                "acao": "logo", "logo": SimpleUploadedFile("logo.png", conteudo, content_type="image/png"),
            })

        self.assertEqual(enviar(self.imagem).status_code, 302)
        resposta = self.client.get(self.logo_url)
        self.assertEqual(resposta.content, self.imagem)
        self.assertEqual(resposta["Content-Type"], "image/png")
        self.assertEqual(resposta["Cache-Control"], "private, no-store")
        self.assertContains(self.client.get(self.url), self.logo_url)
        self.assertNotContains(self.client.get(self.url), "Horas usadas")

        outra = BytesIO()
        Image.new("RGB", (2, 2), "blue").save(outra, format="PNG")
        self.assertEqual(enviar(outra.getvalue()).status_code, 302)
        self.assertEqual(self.client.get(self.logo_url).content, outra.getvalue())
        self.assertEqual(self.client.post(self.url, {"acao": "remover_logo"}).status_code, 302)
        self.assertEqual(self.client.get(self.logo_url).status_code, 404)

    @patch("apps.gestao_at.views.pode_gerir_associados", return_value=True)
    @patch("apps.gestao_at.views.pode_ver_associados", return_value=True)
    def test_rejeita_arquivo_invalido_e_imagem_grande(self, ver, gerir):
        invalido = SimpleUploadedFile("logo.png", b"nao e uma imagem", content_type="image/png")
        self.assertContains(self.client.post(self.url, {"acao": "logo", "logo": invalido}), "Envie uma imagem válida")
        grande = SimpleUploadedFile("logo.png", self.imagem + b"0" * (2 * 1024 * 1024), content_type="image/png")
        self.assertContains(self.client.post(self.url, {"acao": "logo", "logo": grande}), "no máximo 2 MB")
        self.associado.refresh_from_db()
        self.assertIsNone(self.associado.logo)

    @patch("apps.gestao_at.views.pode_gerir_associados", return_value=False)
    @patch("apps.gestao_at.views.pode_ver_associados", return_value=True)
    def test_usuario_sem_permissao_nao_altera_logo(self, ver, gerir):
        arquivo = SimpleUploadedFile("logo.png", self.imagem, content_type="image/png")
        self.assertEqual(self.client.post(self.url, {"acao": "logo", "logo": arquivo}).status_code, 403)
        self.associado.refresh_from_db()
        self.assertIsNone(self.associado.logo)
