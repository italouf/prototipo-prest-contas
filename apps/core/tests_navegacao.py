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
        for rotulo in ["Geral", "Pilares", "PDI", "Formação FCRH", "ACS", "Infraestrutura",
                       "Associação Tecnológica", "Talentos", "Prestação de contas",
                       "Mensal", "Semestral", "Relatórios", "Operação", "Lançamentos",
                       "Aprovação", "Financeiro", "Gestão", "Auditoria", "Admin"]:
            self.assertContains(resposta, rotulo)
        self.assertContains(resposta, 'aria-expanded')
        self.assertContains(resposta, 'id="grp-pilares"')
        self.assertContains(resposta, 'id="grp-contas"')
        sidebar = resposta.content.decode().split('data-testid="sidebar"')[1].split("</aside>")[0]
        self.assertNotIn("OUTRASFONTES", sidebar)
        pilares = sidebar.split('id="grp-pilares"')[1].split("</ul>")[0]
        for rotulo in ["PDI", "Formação FCRH", "ACS", "AT e Outras Fontes"]:
            self.assertIn(rotulo, pilares)
        self.assertNotIn("Infraestrutura", pilares)
        self.assertNotIn("Talentos", pilares)
        self.assertNotIn("Funil AT", pilares)
        gestao = sidebar.split('id="grp-gestao"')[1].split("</ul>")[0]
        for rotulo in ["Funil AT", "Talentos", "Auditoria", "Admin"]:
            self.assertIn(rotulo, gestao)

    def test_auditor_nao_ve_operacao_nem_admin(self):
        self.client.force_login(self.auditor)
        resposta = self.client.get(reverse("core:dashboard"))
        self.assertNotContains(resposta, "Lançamentos")
        self.assertNotContains(resposta, "Aprovação")
        self.assertNotContains(resposta, ">Admin<")
        self.assertContains(resposta, "Auditoria")
        sidebar = resposta.content.decode().split('data-testid="sidebar"')[1].split("</aside>")[0]
        pilares = sidebar.split('id="grp-pilares"')[1].split("</ul>")[0]
        for rotulo in ["PDI", "Formação FCRH", "ACS", "AT e Outras Fontes"]:
            self.assertIn(rotulo, pilares)
        self.assertNotIn("Infraestrutura", pilares)
        gestao = sidebar.split('id="grp-gestao"')[1].split("</ul>")[0]
        self.assertIn("Auditoria", gestao)
        self.assertNotIn("Funil AT", gestao)
        self.assertNotIn(">Talentos<", gestao)
        self.assertNotIn(">Admin<", gestao)

    def test_item_ativo_marca_pagina_corrente(self):
        self.client.force_login(self.master)
        resposta = self.client.get(reverse("core:mensal"))
        self.assertContains(resposta, 'aria-current="page"')

    def test_master_ve_link_direto_para_importar_planilhas(self):
        self.client.force_login(self.master)
        resposta = self.client.get(reverse("core:dashboard"))
        self.assertContains(resposta, 'href="/financeiro/prestacao/importar/"')
        self.assertContains(resposta, "Importar planilhas")

    def test_importacao_marca_item_ativo(self):
        self.client.force_login(self.master)
        resposta = self.client.get(reverse("accountability:importar"))
        sidebar = resposta.content.decode().split('data-testid="sidebar"')[1].split("</aside>")[0]
        link = sidebar.split('href="/financeiro/prestacao/importar/"')[1].split("</a>")[0]
        self.assertIn('aria-current="page"', link)
        self.assertEqual(sidebar.count('aria-current="page"'), 1)

    def test_auditor_nao_ve_link_de_importacao_financeira(self):
        self.client.force_login(self.auditor)
        resposta = self.client.get(reverse("core:dashboard"))
        self.assertNotContains(resposta, "Importar planilhas")
        self.assertNotContains(resposta, "/financeiro/prestacao/importar/")


class SemestralViewTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.master = adicionar_grupo(
            User.objects.create_user(username="sem_master", password="x"), "Master")
        Periodo.objects.create(competencia=date(2026, 3, 1), status="FECHADO")
        Periodo.objects.create(competencia=date(2026, 6, 1), status="ABERTO")

    def test_semestral_lista_periodos_por_semestre(self):
        self.client.force_login(self.master)
        resposta = self.client.get(reverse("core:semestral"), {"ano": "2026", "semestre": "1"})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Semestral")
        self.assertContains(resposta, "1º semestre de 2026")
        self.assertContains(resposta, "2026-03")
        self.assertContains(resposta, "/prestacao/mensal/?periodo=2026-03-01")

    def test_semestral_exige_login(self):
        resposta = self.client.get(reverse("core:semestral"))
        self.assertEqual(resposta.status_code, 302)
