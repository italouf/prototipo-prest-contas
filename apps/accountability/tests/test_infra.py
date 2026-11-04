"""Contrato do detalhamento financeiro de Infraestrutura (TAB. 10/TAB. 11)."""
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.table import Table, TableColumn

from apps.accountability.infra import CATEGORIAS_INFRA
from apps.accountability import services
from apps.accountability.models import (
    Acompanhamento,
    CentroCompetencia,
    ProjetoFinanceiro,
    ResumoFinanceiro,
)
from apps.accountability.parsers.financeiro_geral import parse_financeiro_geral
from apps.accountability.refat_infra import gerar_refat_infra
from apps.pillars.models import Pilar
from apps.projects.models import Projeto
from django.contrib.auth import get_user_model
from django.test import TestCase

from .fixtures_financeiro import FINANCEIRO, workbook_financeiro


FINANCEIRO_V2 = FINANCEIRO.with_name("FINANCEIRO GERAL - REFAT - v2.xlsx")

PROJETOS_INFRA = (
    "ITEM", "CÓDIGO", "PROJETO", "CATEGORIA", "STATUS", "INÍCIO",
    "FINAL PREVISTO", "ORÇADO", "REALIZADO", "PROJETADO 2026",
    "PROJETADO 2027", "REALIZADO + PROJETADO", "DIFERENÇA ORÇADO",
    "% REALIZADO", "FAROL", "ETAPA",
)
VISAO_INFRA = (
    "Coluna1", "RECURSO INFRA", "REALIZADO", "PROJETADO TOTAL",
    "REALIZADO + PROJETADO", "DIFERENÇA",
)


def _tabela(ws, nome, ref):
    ws.add_table(Table(displayName=nome, ref=ref))
    return ws


def _adicionar_infra(wb, *, linhas_projetos=None, visao=None, tabelas=None,
                     visao_headers=VISAO_INFRA):
    """Acrescenta db_infra ao workbook de teste (sem tocar no v2 real)."""
    ws = wb.create_sheet("db_infra")
    for coluna, titulo in enumerate(PROJETOS_INFRA, start=1):
        ws.cell(1, coluna, titulo)
    linhas = linhas_projetos or []
    for linha, registro in enumerate(linhas, start=2):
        for coluna, titulo in enumerate(PROJETOS_INFRA, start=1):
            ws.cell(linha, coluna, registro.get(titulo))
    fim_projetos = max(1, 1 + len(linhas))
    tabelas = tabelas or {"tbl_ProjetosINFRA", "tbl_VisaoINFRA"}
    if "tbl_ProjetosINFRA" in tabelas:
        _tabela(ws, "tbl_ProjetosINFRA", f"A1:P{fim_projetos}")
    for coluna, titulo in enumerate(visao_headers, start=18):  # R..W
        ws.cell(1, coluna, titulo)
    dados_visao = visao or {
        "Coluna1": "RECURSO INFRA",
        "RECURSO INFRA": Decimal("10000000"),
        "REALIZADO": Decimal("7299414.35"),
        "PROJETADO TOTAL": Decimal("3000000"),
        "REALIZADO + PROJETADO": Decimal("10299414.35"),
        "DIFERENÇA": Decimal("-299414.35"),
    }
    for coluna, titulo in enumerate(visao_headers, start=18):
        ws.cell(2, coluna, dados_visao.get(titulo))
    if "tbl_VisaoINFRA" in tabelas:
        _tabela(ws, "tbl_VisaoINFRA", "R1:W2")
    return wb


def _parse(wb):
    try:
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "financeiro.xlsx"
            wb.save(caminho)
            return parse_financeiro_geral(caminho)
    finally:
        wb.close()


def _resumo(payload, origem, pilar):
    return next((r for r in payload["resumos"]
                 if (r["origem"], r["pilar"]) == (origem, pilar)), None)


class CategoriasInfraTestes(unittest.TestCase):
    def test_lista_canonica_e_estavel(self):
        self.assertEqual(
            CATEGORIAS_INFRA,
            (
                "Obras civis",
                "Laboratórios e salas técnicas",
                "Equipamentos e instrumentação",
                "TI, Data Center e HPC",
                "Serviços e manutenção",
                "Outros",
            ),
        )


class ParserInfraTestes(unittest.TestCase):
    def test_v2_sem_tabelas_infra_continua_valido(self):
        payload = parse_financeiro_geral(FINANCEIRO)
        self.assertEqual(payload["erros"], [])
        self.assertEqual(len(payload["projetos"]), 33)
        self.assertFalse(any(r["origem"] in ("TAB. 10", "TAB. 11")
                             for r in payload["resumos"]))
        self.assertFalse(any(p["origem"] == "TAB. 10" for p in payload["projetos"]))

    def test_projetos_e_resumo_infra_sao_lidos(self):
        wb = _adicionar_infra(workbook_financeiro(), linhas_projetos=[
            {
                "ITEM": 1, "CÓDIGO": "INF-01",
                "PROJETO": "Laboratório Quântico",
                "CATEGORIA": "Laboratórios e salas técnicas",
                "STATUS": "Em andamento",
                "INÍCIO": date(2025, 1, 1),
                "FINAL PREVISTO": date(2027, 6, 30),
                "ORÇADO": Decimal("2000000"),
                "REALIZADO": Decimal("1500000"),
                "PROJETADO 2026": Decimal("300000"),
                "PROJETADO 2027": Decimal("200000"),
                "REALIZADO + PROJETADO": Decimal("2000000"),
                "DIFERENÇA ORÇADO": Decimal("0"),
                "% REALIZADO": Decimal("0.75"),
                "FAROL": "Execução parcial",
                "ETAPA": "Em andamento",
            },
            {
                "ITEM": 2,
                "PROJETO": "Data Center",
                "CATEGORIA": "TI, Data Center e HPC",
                "STATUS": "Futuros projetos",
                "ORÇADO": Decimal("1000000"),
                "REALIZADO": Decimal("0"),
                "PROJETADO 2026": Decimal("500000"),
                "PROJETADO 2027": Decimal("500000"),
                "REALIZADO + PROJETADO": Decimal("1000000"),
                "DIFERENÇA ORÇADO": Decimal("0"),
                "% REALIZADO": Decimal("0"),
                "FAROL": "Sem lançamento",
                "ETAPA": "Futuros projetos",
            },
        ])
        payload = _parse(wb)
        self.assertEqual(payload["erros"], [])
        projetos = [p for p in payload["projetos"] if p["origem"] == "TAB. 10"]
        self.assertEqual(len(projetos), 2)
        self.assertEqual(projetos[0]["categoria"], "Laboratórios e salas técnicas")
        self.assertEqual(projetos[0]["realizado"], Decimal("1500000.00"))
        resumo = _resumo(payload, "TAB. 11", "INFRA")
        self.assertEqual(resumo["recurso_ou_meta"], Decimal("10000000.00"))
        self.assertEqual(resumo["realizado"], Decimal("7299414.35"))
        self.assertEqual(resumo["diferenca"], Decimal("-299414.35"))

    def test_tabelas_infra_exigem_par(self):
        wb = workbook_financeiro()
        ws = wb.create_sheet("db_infra")
        for coluna, titulo in enumerate(VISAO_INFRA, start=1):
            ws.cell(1, coluna, titulo)
        ws.cell(2, 1, "RECURSO INFRA")
        ws.cell(2, 2, Decimal("10000000"))
        _tabela(ws, "tbl_VisaoINFRA", "A1:F2")
        payload = _parse(wb)
        self.assertTrue(any("juntas" in erro for erro in payload["erros"]))

    def test_categoria_desconhecida_rejeita(self):
        wb = _adicionar_infra(workbook_financeiro(), linhas_projetos=[
            {
                "PROJETO": "Obra sem categoria válida",
                "CATEGORIA": "Categoria inventada",
                "STATUS": "Em andamento",
                "ORÇADO": Decimal("100"),
                "REALIZADO": Decimal("0"),
            },
        ])
        payload = _parse(wb)
        self.assertTrue(any("Categoria" in erro and "inválida" in erro
                            for erro in payload["erros"]))

    def test_linhas_vazias_com_formulas_nao_viram_projeto(self):
        wb = _adicionar_infra(workbook_financeiro(), linhas_projetos=[
            {
                "PROJETO": "Laboratório Quântico",
                "CATEGORIA": "Laboratórios e salas técnicas",
                "STATUS": "Em andamento",
                "ORÇADO": Decimal("2000000"),
                "REALIZADO": Decimal("1500000"),
                "REALIZADO + PROJETADO": Decimal("1500000"),
                "DIFERENÇA ORÇADO": Decimal("-500000"),
                "% REALIZADO": Decimal("0.75"),
                "FAROL": "Execução parcial",
                "ETAPA": "Em andamento",
            },
            {  # linha de template: só fórmulas nas colunas calculadas
                "REALIZADO + PROJETADO": Decimal("0"),
                "DIFERENÇA ORÇADO": Decimal("0"),
                "% REALIZADO": Decimal("0"),
                "FAROL": "Sem lançamento",
                "ETAPA": "Futuros projetos",
            },
        ])
        payload = _parse(wb)
        self.assertEqual(payload["erros"], [])
        self.assertEqual(len([p for p in payload["projetos"] if p["origem"] == "TAB. 10"]), 1)

    def test_soma_de_projetos_acima_do_total_gera_aviso(self):
        wb = _adicionar_infra(
            workbook_financeiro(),
            linhas_projetos=[{
                "PROJETO": "Obra acima do total",
                "CATEGORIA": "Obras civis",
                "STATUS": "Em andamento",
                "ORÇADO": Decimal("12000000"),
                "REALIZADO": Decimal("100"),
            }],
            visao={
                "Coluna1": "RECURSO INFRA",
                "RECURSO INFRA": Decimal("10000000"),
                "REALIZADO": Decimal("7299414.35"),
                "PROJETADO TOTAL": Decimal("0"),
                "REALIZADO + PROJETADO": Decimal("7299414.35"),
                "DIFERENÇA": Decimal("2700585.65"),
            },
        )
        payload = _parse(wb)
        self.assertEqual(payload["erros"], [])
        self.assertTrue(any("excede" in aviso.lower() for aviso in payload["avisos"]))

    def test_aliases_da_visao_infra_sao_aceitos(self):
        headers = (
            "Coluna1", "RECURSO PPI INFRA", "REALIZADO", "PROJETADO TOTAL",
            "REALIZADO + PROJETADO", "DIFERENÇA PPI",
        )
        wb = _adicionar_infra(workbook_financeiro(), visao_headers=headers, visao={
            "Coluna1": "RECURSO INFRA",
            "RECURSO PPI INFRA": Decimal("10000000"),
            "REALIZADO": Decimal("7299414.35"),
            "PROJETADO TOTAL": None,
            "REALIZADO + PROJETADO": None,
            "DIFERENÇA PPI": Decimal("2700585.65"),
        })
        payload = _parse(wb)
        self.assertEqual(payload["erros"], [])
        resumo = _resumo(payload, "TAB. 11", "INFRA")
        self.assertEqual(resumo["recurso_ou_meta"], Decimal("10000000.00"))
        self.assertEqual(resumo["diferenca"], Decimal("2700585.65"))


class GerarRefatInfraTestes(unittest.TestCase):
    def test_v3_preserva_v2_e_cria_tabelas_infra(self):
        antes = FINANCEIRO_V2.read_bytes()
        base = parse_financeiro_geral(FINANCEIRO_V2)
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / "v3.xlsx"
            resultado = gerar_refat_infra(FINANCEIRO_V2, destino)
            self.assertTrue(destino.exists())
            self.assertEqual(FINANCEIRO_V2.read_bytes(), antes)
            payload = parse_financeiro_geral(destino)
            self.assertEqual(payload["erros"], [])
            self.assertEqual(
                [r for r in payload["resumos"] if r["origem"] != "TAB. 11"],
                base["resumos"])
            self.assertEqual(payload["projetos"], base["projetos"])
            self.assertEqual(
                len([p for p in payload["projetos"] if p["origem"] == "TAB. 10"]), 0)
            resumo = _resumo(payload, "TAB. 11", "INFRA")
            self.assertEqual(resumo["recurso_ou_meta"], Decimal("10000000.00"))
            self.assertEqual(resumo["realizado"], Decimal("7299414.35"))
            self.assertEqual(resumo["diferenca"], Decimal("2700585.65"))
            self.assertTrue(resultado["alterado"])

            wb = load_workbook(destino, data_only=True)
            self.assertIn("db_infra", wb.sheetnames)
            ws = wb["db_infra"]
            self.assertIn("tbl_ProjetosINFRA", ws.tables)
            self.assertIn("tbl_VisaoINFRA", ws.tables)
            self.assertEqual(ws.tables["tbl_ProjetosINFRA"].ref, "A1:P12")
            self.assertEqual(ws.tables["tbl_VisaoINFRA"].ref, "R1:W2")
            self.assertEqual(ws["C12"].value, "TOTAL")
            self.assertEqual(ws["Y2"].value, CATEGORIAS_INFRA[0])
            self.assertEqual(ws["S2"].value, 10000000)
            self.assertEqual(ws["W2"].value, 2700585.65)
            validacoes = ws.data_validations.dataValidation
            self.assertEqual(validacoes[0].formula1, "_Opcoes_Projetos!$A$2:$A$10")
            self.assertEqual(validacoes[1].formula1, "$Y$2:$Y$7")
            wb.close()


class IngestaoInfraTestes(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(username="infra-ingestao")
        for codigo in ("PDI", "FORMACAO", "STARTUPS", "AT", "OUTRASFONTES", "INFRA"):
            Pilar.objects.get_or_create(codigo=codigo, defaults={"nome": codigo})

    def test_ingestao_persiste_categoria_sem_criar_projeto_infra(self):
        wb = _adicionar_infra(workbook_financeiro(), linhas_projetos=[
            {
                "ITEM": 1,
                "CÓDIGO": "INF-01",
                "PROJETO": "Laboratório Quântico",
                "CATEGORIA": "Laboratórios e salas técnicas",
                "STATUS": "Em andamento",
                "ORÇADO": Decimal("2000000"),
                "REALIZADO": Decimal("1500000"),
                "REALIZADO + PROJETADO": Decimal("1500000"),
                "DIFERENÇA ORÇADO": Decimal("-500000"),
                "% REALIZADO": Decimal("0.75"),
                "FAROL": "Execução parcial",
                "ETAPA": "Em andamento",
            },
        ])
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "v3.xlsx"
            wb.save(caminho)
            wb.close()
            services.ingestar(
                "FINANCEIRO_GERAL", caminho, "Centro Infra", "3T/2026",
                self.usuario)
        acomp = Acompanhamento.objects.get(centro__nome="Centro Infra")
        projeto = ProjetoFinanceiro.objects.get(
            acompanhamento=acomp, origem="TAB. 10", nome="Laboratório Quântico")
        self.assertEqual(projeto.categoria, "Laboratórios e salas técnicas")
        self.assertIsNone(projeto.projeto)
        self.assertTrue(ResumoFinanceiro.objects.filter(
            acompanhamento=acomp, origem="TAB. 11", pilar__codigo="INFRA").exists())
        self.assertFalse(Projeto.objects.filter(pilar__codigo="INFRA").exists())


class ProjetoFinanceiroCategoriaTestes(TestCase):
    def setUp(self):
        self.acomp = Acompanhamento.objects.create(
            centro=CentroCompetencia.objects.create(codigo="quiin", nome="QuIIN"),
            periodo_referencia="3T/2026")
        self.pilar, _ = Pilar.objects.get_or_create(
            codigo="INFRA", defaults={"nome": "Infraestrutura"})

    def test_categoria_e_opcional_e_persistida(self):
        sem = ProjetoFinanceiro.objects.create(
            acompanhamento=self.acomp, origem="TAB. 10", pilar=self.pilar,
            nome="Obra sem categoria")
        com = ProjetoFinanceiro.objects.create(
            acompanhamento=self.acomp, origem="TAB. 10", pilar=self.pilar,
            nome="Obra com categoria", categoria="Obras civis")
        sem.refresh_from_db()
        com.refresh_from_db()
        self.assertEqual(sem.categoria, "")
        self.assertEqual(com.categoria, "Obras civis")
