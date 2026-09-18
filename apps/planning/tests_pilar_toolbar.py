"""Testes da toolbar por pilar: edição escopada, CSV, HTML, impressão (L15, TDD)."""
from decimal import Decimal as D

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.pillars.models import Pilar, UsuarioPilar
from apps.planning.models import PlanoAnual
from apps.planning.tests import criar_base_anual

APLICAR = "planning:aplicar"


def grade(pilar_pk, **kwargs):
    base = {"ano": "todos", "base": "fin", "pilar": str(pilar_pk)}
    base.update(kwargs)
    return base


class EdicaoEscopadaTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pilares = criar_base_anual()

    def setUp(self):
        garantir_grupos()
        self.master = adicionar_grupo(User.objects.create_user(username="pe_master", password="x"), "Master")
        self.focal = adicionar_grupo(User.objects.create_user(username="pe_focal", password="x"), "PontoFocal")
        self.lider = adicionar_grupo(User.objects.create_user(username="pe_lider", password="x"), "Lideranca")
        UsuarioPilar.objects.create(usuario=self.focal, pilar=self.pilares["PDI"])

    def test_master_edita_pilar_e_volta_para_pagina_do_pilar(self):
        self.client.force_login(self.master)
        pk = self.pilares["PDI"].pk
        resposta = self.client.post(reverse(APLICAR), grade(pk, **{
            "v__2026__financeiro__PDI__executado": "9",
        }))
        self.assertRedirects(resposta, f"/pilar/{pk}/?ano=todos&base=fin",
                             fetch_redirect_response=False)
        linha = PlanoAnual.objects.get(ano=2026, pilar__codigo="PDI", base="financeiro")
        self.assertEqual(linha.executado, D(9))
        self.assertTrue(AuditLog.objects.filter(
            entidade="PlanoAnual", registro_id=str(linha.pk)).exists())

    def test_pilar_escopado_rejeita_linha_de_outro_pilar(self):
        self.client.force_login(self.master)
        pk = self.pilares["PDI"].pk
        resposta = self.client.post(reverse(APLICAR), grade(pk, **{
            "v__2026__financeiro__INFRA__executado": "5",
        }))
        self.assertEqual(resposta.status_code, 403)
        linha = PlanoAnual.objects.get(ano=2026, pilar__codigo="INFRA", base="financeiro")
        self.assertEqual(linha.executado, D(4))

    def test_focal_nao_edita_pilar_invisivel(self):
        self.client.force_login(self.focal)
        pk = self.pilares["INFRA"].pk
        resposta = self.client.post(reverse(APLICAR), grade(pk, **{
            "v__2026__financeiro__INFRA__executado": "5",
        }))
        self.assertEqual(resposta.status_code, 403)

    def test_pilar_inexistente_da_404(self):
        self.client.force_login(self.master)
        resposta = self.client.post(reverse(APLICAR), grade(9999, **{
            "v__2026__financeiro__PDI__executado": "9",
        }))
        self.assertEqual(resposta.status_code, 404)

    def test_lideranca_recebe_403_mesmo_escopado(self):
        self.client.force_login(self.lider)
        pk = self.pilares["PDI"].pk
        resposta = self.client.post(reverse(APLICAR), grade(pk, **{
            "v__2026__financeiro__PDI__executado": "9",
        }))
        self.assertEqual(resposta.status_code, 403)

    def test_aplicar_e_baixar_escopado_devolve_html_do_pilar(self):
        self.client.force_login(self.master)
        pk = self.pilares["AT"].pk
        resposta = self.client.post(reverse(APLICAR), grade(pk, **{
            "v__2026__financeiro__AT__executado": "2", "acao": "baixar",
        }))
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("attachment", resposta["Content-Disposition"])
        self.assertIn("AT", resposta["Content-Disposition"])
        html = resposta.content.decode()
        self.assertIn("Associação Tecnológica (AT)", html)

    def test_editor_do_pilar_mostra_so_as_linhas_do_pilar(self):
        self.client.force_login(self.focal)
        resposta = self.client.get(reverse("core:pilar", args=[self.pilares["PDI"].pk]))
        self.assertContains(resposta, 'name="v__2026__financeiro__PDI__executado"')
        self.assertNotContains(resposta, "__INFRA__")
        self.assertNotContains(resposta, "__AT__")

    def test_lideranca_nao_ve_editor_no_pilar(self):
        self.client.force_login(self.lider)
        resposta = self.client.get(reverse("core:pilar", args=[self.pilares["PDI"].pk]))
        self.assertNotContains(resposta, 'id="editor-dados"')


class CsvPilarTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pilares = criar_base_anual()

    def setUp(self):
        garantir_grupos()
        self.master = adicionar_grupo(User.objects.create_user(username="pc_master", password="x"), "Master")

    def test_csv_do_pilar_tem_layout_proprio(self):
        self.client.force_login(self.master)
        pk = self.pilares["PDI"].pk
        resposta = self.client.get(
            reverse("planning:csv"), {"ano": "2026", "base": "fis", "pilar": str(pk)})
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("text/csv", resposta["Content-Type"])
        self.assertIn("PDI", resposta["Content-Disposition"])
        conteudo = resposta.content.decode("utf-8-sig")
        linhas = conteudo.splitlines()
        self.assertEqual(linhas[0], "Pilar;Ano;Previsto;Executado;Saldo;% Executado")
        self.assertIn("PDI;Ano 3: 2026;6;5;1;83%", linhas)
        self.assertIn("PDI;Total;18;13;5;72%", linhas)
        self.assertNotIn("INFRA", conteudo)

    def test_csv_pilar_inexistente_da_404(self):
        self.client.force_login(self.master)
        resposta = self.client.get(reverse("planning:csv"), {"pilar": "9999"})
        self.assertEqual(resposta.status_code, 404)

    def test_csv_pilar_invisivel_da_403(self):
        garantir_grupos()
        focal = adicionar_grupo(User.objects.create_user(username="pc_focal", password="x"), "PontoFocal")
        UsuarioPilar.objects.create(usuario=focal, pilar=self.pilares["PDI"])
        self.client.force_login(focal)
        resposta = self.client.get(
            reverse("planning:csv"), {"pilar": str(self.pilares["INFRA"].pk)})
        self.assertEqual(resposta.status_code, 403)


class HtmlPilarTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pilares = criar_base_anual()

    def setUp(self):
        garantir_grupos()
        self.master = adicionar_grupo(User.objects.create_user(username="ph_master", password="x"), "Master")

    def test_html_do_pilar_e_standalone_recortado(self):
        self.client.force_login(self.master)
        pk = self.pilares["AT"].pk
        resposta = self.client.get(
            reverse("planning:export_html"), {"ano": "2026", "base": "fin", "pilar": str(pk)})
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("AT", resposta["Content-Disposition"])
        html = resposta.content.decode()
        self.assertIn("Associação Tecnológica (AT)", html)
        self.assertIn("Ano 3: 2026", html)

    def test_toolbar_do_pilar_aponta_para_acoes_escopadas(self):
        self.client.force_login(self.master)
        pk = self.pilares["PDI"].pk
        resposta = self.client.get(reverse("core:pilar", args=[pk]))
        self.assertContains(resposta, f"/plano-anual/dados.csv?ano=todos&base=fin&pilar={pk}")
        self.assertContains(resposta, f"/plano-anual/dashboard.html?ano=todos&base=fin&pilar={pk}")
        self.assertContains(resposta, f'href="/pilar/{pk}/"')
        self.assertContains(resposta, "print-cabecalho")
