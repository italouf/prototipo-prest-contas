"""Testes da navegação L4: sidebar reagrupada, semestral e contexto anual no pilar."""
from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.periods.models import Periodo
from apps.pillars.models import Pilar


class SidebarNavegacaoTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.master = adicionar_grupo(
            User.objects.create_user(username="nav_master", password="x"), "Master")
        self.auditor = adicionar_grupo(
            User.objects.create_user(username="nav_auditor", password="x"), "Auditor")
        for i, (codigo, nome) in enumerate([
            ("PDI", "PDI / FCCT"), ("FORMACAO", "Formação"), ("STARTUPS", "Startups"),
            ("AT", "Associação Tecnológica"), ("INFRA", "Infraestrutura"),
            ("OUTRASFONTES", "Outras Fontes"),
        ]):
            Pilar.objects.create(codigo=codigo, nome=nome, ordem=i + 1)
        Periodo.objects.create(competencia=date(2026, 6, 1), status="ABERTO")

    def test_grupos_e_itens_do_mockup_mais_operacao_e_gestao(self):
        self.client.force_login(self.master)
        resposta = self.client.get(reverse("core:dashboard"))
        html = resposta.content.decode()
        for rotulo in ["Geral", "Pilares", "PDI", "Formação FCRH", "ACS", "Infraestrutura",
                       "Associação Tecnológica", "Talentos", "Prestação de contas",
                       "Mensal", "Semestral", "Relatórios", "Operação", "Lançamentos",
                       "Aprovação", "Financeiro", "Gestão", "Auditoria", "Admin"]:
            self.assertContains(resposta, rotulo)
        self.assertContains(resposta, 'aria-expanded')
        self.assertContains(resposta, 'id="grp-pilares"')
        self.assertContains(resposta, 'id="grp-contas"')
        self.assertNotIn("OUTRASFONTES", html)

    def test_auditor_nao_ve_operacao_nem_admin(self):
        self.client.force_login(self.auditor)
        resposta = self.client.get(reverse("core:dashboard"))
        self.assertNotContains(resposta, "Lançamentos")
        self.assertNotContains(resposta, "Aprovação")
        self.assertNotContains(resposta, ">Admin<")
        self.assertContains(resposta, "Auditoria")

    def test_item_ativo_marca_pagina_corrente(self):
        self.client.force_login(self.master)
        resposta = self.client.get(reverse("core:mensal"))
        self.assertContains(resposta, 'aria-current="page"')


class SemestralViewTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.master = adicionar_grupo(
            User.objects.create_user(username="sem_master", password="x"), "Master")
        Periodo.objects.create(competencia=date(2026, 3, 1), status="FECHADO")
        Periodo.objects.create(competencia=date(2026, 6, 1), status="ABERTO")

    def test_semestral_lista_periodos_por_semestre(self):
        self.client.force_login(self.master)
        resposta = self.client.get(reverse("core:semestral"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Semestral")
        self.assertContains(resposta, "1º semestre")
        self.assertContains(resposta, "2º semestre")
        self.assertContains(resposta, "2026-03")
        self.assertContains(resposta, "/prestacao/mensal/?periodo=2026-03-01")

    def test_semestral_exige_login(self):
        resposta = self.client.get(reverse("core:semestral"))
        self.assertEqual(resposta.status_code, 302)


class PilarContextoAnualTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.master = adicionar_grupo(
            User.objects.create_user(username="ctx_master", password="x"), "Master")
        self.pdi = Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=1)

    def test_pilar_com_filtro_anual_exibe_banner(self):
        self.client.force_login(self.master)
        resposta = self.client.get(
            reverse("core:pilar", args=[self.pdi.pk]), {"ano": "2026", "base": "fis"})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Ano 3: 2026")
        self.assertContains(resposta, "/?ano=2026&base=fis")

    def test_pilar_sem_filtro_nao_exibe_banner(self):
        self.client.force_login(self.master)
        resposta = self.client.get(reverse("core:pilar", args=[self.pdi.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, "contexto-anual")
