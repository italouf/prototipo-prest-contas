"""Dashboard financeiro de Infraestrutura: DTO, fallback, navegação e telas."""
import tempfile
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.core.context_processors import nav
from apps.core.permissions import adicionar_grupo, garantir_grupos, usuario_pode_dashboard_pilar
from apps.pillars.models import Pilar, UsuarioPilar
from apps.planning.services import PILARES_COM_PAINEL
from apps.planning.views import contexto_pilar

from .. import services
from ..models import Acompanhamento, CentroCompetencia, ProjetoFinanceiro, ResumoFinanceiro
from ..panel import painel_financeiro_pilar
from ..refat_infra import gerar_refat_infra
from .fixtures_financeiro import FINANCEIRO


def _celula(tabela, campo):
    return next(c for c in tabela["linhas"][0]["celulas"] if c["campo"] == campo)


class DashboardInfraTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        garantir_grupos()
        cls.usuario = adicionar_grupo(
            get_user_model().objects.create_user(username="infra-dashboard"), "Master")
        cls.infra, _ = Pilar.objects.get_or_create(
            codigo="INFRA", defaults={"nome": "Infraestrutura"})
        cls.acomp = Acompanhamento.objects.create(
            centro=CentroCompetencia.objects.create(codigo="centro-infra", nome="Centro Infra"),
            periodo_referencia="3T/2026")
        ResumoFinanceiro.objects.create(
            acompanhamento=cls.acomp, origem="TAB. 11", pilar=cls.infra, ano=None,
            recurso_ou_meta=Decimal("10000000"), realizado=Decimal("7299414.35"),
            projetado=Decimal("3000000"),
            realizado_mais_projetado=Decimal("10299414.35"),
            diferenca=Decimal("-299414.35"))
        ProjetoFinanceiro.objects.create(
            acompanhamento=cls.acomp, origem="TAB. 10", pilar=cls.infra,
            sequencia=1, codigo_projeto_embrapii="INF-01",
            nome="Laboratório Quântico", categoria="Laboratórios e salas técnicas",
            status="Em andamento", etapa="Em andamento", farol="Execução parcial",
            orcado=Decimal("2000000"), realizado=Decimal("1500000"),
            projetado_2026=Decimal("300000"), projetado_2027=Decimal("200000"),
            realizado_mais_projetado=Decimal("2000000"), diferenca=Decimal("0"),
            percentual=Decimal("0.75"))
        ProjetoFinanceiro.objects.create(
            acompanhamento=cls.acomp, origem="TAB. 10", pilar=cls.infra,
            sequencia=2, nome="Data Center", categoria="TI, Data Center e HPC",
            status="Futuros projetos", etapa="Futuros projetos",
            farol="Sem lançamento", orcado=Decimal("1000000"), realizado=Decimal("0"),
            projetado_2026=Decimal("500000"), projetado_2027=Decimal("500000"),
            realizado_mais_projetado=Decimal("1000000"), diferenca=Decimal("0"),
            percentual=Decimal("0"))

    def test_dto_tem_cards_categoria_residual_e_total(self):
        bloco = painel_financeiro_pilar(self.infra, self.acomp)
        self.assertEqual(bloco["codigo"], "INFRA")
        self.assertEqual(bloco["previsto"], Decimal("10000000"))
        self.assertEqual(bloco["executado"], Decimal("7299414.35"))
        self.assertFalse(bloco["infra_sem_detalhamento"])
        self.assertEqual(bloco["projetos"], 2)
        linhas = bloco["tabela_projetos_financeiros"]["linhas"]
        self.assertEqual(len(linhas), 4)
        residual = next(l for l in linhas if l["nao_detalhado"])
        total = next(l for l in linhas if l["total"])
        valores_residual = {c["campo"]: c["valor"] for c in residual["celulas"]}
        valores_total = {c["campo"]: c["valor"] for c in total["celulas"]}
        self.assertEqual(valores_residual["orcado"], Decimal("7000000"))
        self.assertEqual(valores_residual["realizado"], Decimal("5799414.35"))
        self.assertEqual(valores_residual["realizado_mais_projetado"], Decimal("7299414.35"))
        self.assertEqual(valores_total["orcado"], Decimal("10000000"))
        self.assertEqual(valores_total["realizado"], Decimal("7299414.35"))
        self.assertEqual(
            bloco["tabela_visao_financeira"]["cabecalhos"],
            ["Coluna1", "RECURSO INFRA", "REALIZADO", "PROJETADO TOTAL",
             "REALIZADO + PROJETADO", "DIFERENÇA"])
        self.assertEqual(
            _celula(bloco["tabela_visao_financeira"], "recurso_ou_meta")["valor"],
            Decimal("10000000"))

    def test_apresentar_pilar_usa_categoria_e_nao_detalhado(self):
        contexto = contexto_pilar(
            self.infra, "todos", "fin", self.usuario, self.acomp)
        painel = contexto["painel_pilar"]
        self.assertEqual(
            [c["titulo"] for c in painel["cards_overview"]],
            ["RECURSO INFRA", "Realizado · Infraestrutura", "DIFERENÇA"])
        self.assertEqual(
            [g["titulo"] for g in painel["grupos_projetos"]],
            ["Laboratórios e salas técnicas", "TI, Data Center e HPC", "Não detalhado"])
        self.assertEqual(
            painel["grafico_financeiro"]["titulo"],
            "Carteira de projetos por categoria")
        self.assertEqual(len(painel["grafico_financeiro"]["linhas"]), 3)

    def test_fallback_sem_tab11_usa_tab1_e_sinaliza(self):
        acomp = Acompanhamento.objects.create(
            centro=CentroCompetencia.objects.create(codigo="centro-antigo", nome="Centro Antigo"),
            periodo_referencia="2T/2026")
        ResumoFinanceiro.objects.create(
            acompanhamento=acomp, origem="TAB. 1", pilar=self.infra, ano=None,
            recurso_ou_meta=Decimal("10000000"), realizado=Decimal("7299414.35"))
        bloco = painel_financeiro_pilar(self.infra, acomp)
        self.assertTrue(bloco["infra_sem_detalhamento"])
        self.assertEqual(bloco["previsto"], Decimal("10000000"))
        self.assertEqual(bloco["executado"], Decimal("7299414.35"))
        self.assertEqual(bloco["projetos"], 0)
        residual = next(l for l in bloco["tabela_projetos_financeiros"]["linhas"]
                        if l["nao_detalhado"])
        valores = {c["campo"]: c["valor"] for c in residual["celulas"]}
        self.assertEqual(valores["orcado"], Decimal("10000000"))
        self.assertEqual(valores["realizado"], Decimal("7299414.35"))

    def test_pagina_financeira_renderiza_tabelas_e_grafico(self):
        self.client.force_login(self.usuario)
        resposta = self.client.get(
            reverse("core:pilar", args=[self.infra.pk]) + "?base=fin")
        self.assertEqual(resposta.status_code, 200)
        conteudo = resposta.content.decode()
        for texto in ("RECURSO INFRA", "Não detalhado",
                      "Carteira de projetos por categoria",
                      "Laboratórios e salas técnicas"):
            self.assertIn(texto, conteudo)

    def test_csv_e_html_exportam_tabelas_infra(self):
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse("planning:csv"), {
            "pilar": self.infra.pk,
            "acompanhamento": self.acomp.pk,
            "base": "fin",
        })
        self.assertEqual(resposta.status_code, 200)
        conteudo = resposta.content.decode("utf-8-sig")
        for texto in ("tbl_VisaoINFRA", "tbl_ProjetosINFRA",
                      "Não detalhado", "RECURSO INFRA"):
            self.assertIn(texto, conteudo)
        html = self.client.get(reverse("planning:export_html"), {
            "pilar": self.infra.pk,
            "acompanhamento": self.acomp.pk,
            "base": "fin",
        })
        self.assertEqual(html.status_code, 200)
        self.assertIn("Não detalhado", html.content.decode())

    def test_base_fisica_mostra_secao_em_construcao(self):
        self.client.force_login(self.usuario)
        resposta = self.client.get(
            reverse("core:pilar", args=[self.infra.pk]) + "?base=fis")
        self.assertEqual(resposta.status_code, 200)
        conteudo = resposta.content.decode()
        self.assertIn('data-testid="infra-em-construcao"', conteudo)
        self.assertIn("Seção em construção", conteudo)
        self.assertNotIn('data-testid="grafico-financeiro-pilar"', conteudo)


class NavegacaoInfraTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        garantir_grupos()
        cls.infra, _ = Pilar.objects.get_or_create(
            codigo="INFRA", defaults={"nome": "Infraestrutura"})
        cls.master = adicionar_grupo(
            get_user_model().objects.create_user(username="infra-master"), "Master")
        cls.focal = get_user_model().objects.create_user(username="infra-focal")
        UsuarioPilar.objects.create(usuario=cls.focal, pilar=cls.infra)
        cls.sem_vinculo = get_user_model().objects.create_user(username="infra-sem-vinculo")

    def test_infra_entra_nos_pilares_com_painel(self):
        self.assertEqual(
            PILARES_COM_PAINEL,
            ("PDI", "FORMACAO", "STARTUPS", "INFRA", "AT"))

    def test_permissao_de_dashboard(self):
        self.assertTrue(usuario_pode_dashboard_pilar(self.master, self.infra))
        self.assertTrue(usuario_pode_dashboard_pilar(self.focal, self.infra))
        self.assertFalse(usuario_pode_dashboard_pilar(self.sem_vinculo, self.infra))

    def test_sidebar_do_master_inclui_infra(self):
        request = RequestFactory().get("/")
        request.user = self.master
        contexto = nav(request)
        self.assertIn(self.infra, contexto["pilares_grupo"])


class IntegracaoRefatInfraTestes(TestCase):
    def test_v3_real_importa_e_renderiza_dashboard(self):
        garantir_grupos()
        usuario = adicionar_grupo(
            get_user_model().objects.create_user(username="infra-v3"), "Master")
        for codigo in ("PDI", "FORMACAO", "STARTUPS", "AT", "OUTRASFONTES", "INFRA"):
            Pilar.objects.get_or_create(codigo=codigo, defaults={"nome": codigo})
        infra = Pilar.objects.get(codigo="INFRA")
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / "v3.xlsx"
            gerar_refat_infra(
                FINANCEIRO.with_name("FINANCEIRO GERAL - REFAT - v2.xlsx"), destino)
            services.ingestar(
                "FINANCEIRO_GERAL", destino, "Centro V3", "3T/2026", usuario)
        acomp = Acompanhamento.objects.get(centro__nome="Centro V3")
        self.assertTrue(ResumoFinanceiro.objects.filter(
            acompanhamento=acomp, origem="TAB. 11", pilar=infra).exists())
        self.assertFalse(ProjetoFinanceiro.objects.filter(
            acompanhamento=acomp, origem="TAB. 10", pilar=infra).exists())
        self.client.force_login(usuario)
        resposta = self.client.get(reverse("core:pilar", args=[infra.pk]) + "?base=fin")
        self.assertEqual(resposta.status_code, 200)
        conteudo = resposta.content.decode()
        self.assertIn("Não detalhado", conteudo)
        self.assertIn("RECURSO INFRA", conteudo)
        self.assertNotIn("Detalhamento de Infraestrutura não importado", conteudo)
