"""Testes do parser do Excel financeiro mestre (LOOP 3).

Consolida abas de conta-ação por (pilar, tipo_recurso) com filtro de
mês de referência. Aba 6.1 (Lei de TICs) é segregada como AT_LEI_TICS
e nunca soma no AT (REGRA DURA).
"""
import io
import json
import tempfile
from datetime import date, datetime
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from openpyxl import Workbook
from openpyxl.utils.datetime import to_excel

from apps.accounts.models import User
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.finance.excel_mestre import consolidar_excel
from apps.finance.models import FinanceiroConsolidado, ImportacaoFinanceira
from apps.periods.models import Periodo
from apps.pillars.models import Pilar


def _workbook_mock(caminho):
    """Monta um Excel mock com 2 abas de despesa e linhas em 2 meses."""
    wb = Workbook()
    ws = wb.active
    ws.title = "3. Conta Ação - AFCCT"
    ws.append(["Relatório de acompanhamento"])  # linha 1
    for _ in range(8):  # linhas 2-9: preâmbulo
        ws.append([])
    ws.append(["Linha", "Conta do projeto", "Data do pagamento", "Valor (R$)"])  # linha 10
    ws.append([1, "AFCCT-01", datetime(2026, 4, 5), 100])
    ws.append([2, "AFCCT-01", "20/04/2026", 200.50])
    ws.append([3, "AFCCT-02", to_excel(datetime(2026, 4, 15)), 50])
    ws.append([4, "AFCCT-02", "2026-04-25", 25])
    ws.append([5, "AFCCT-03", datetime(2026, 5, 1), 999])  # outro mês: ignorada no filtro 2026-04

    ws2 = wb.create_sheet("6.1 Conta Ação - AT (Lei TICs)")
    ws2.append(["Formulário de controle"])  # linha 1
    for _ in range(8):
        ws2.append([])
    ws2.append(["Linha", "Descrição", "Data", "Valor (R$)"])  # linha 10: "Data" genérico
    ws2.append([1, "Repasse Lei de TICs", datetime(2026, 4, 7), 60])
    ws2.append([2, "Repasse Lei de TICs", "2026-05-03", 70])  # outro mês

    ws3 = wb.create_sheet("6. Conta Ação - AT")
    ws3.append(["Formulário de controle"])
    for _ in range(8):
        ws3.append([])
    ws3.append(["Linha", "Descrição", "Data", "Valor (R$)"])
    ws3.append([1, "Aporte AT", datetime(2026, 4, 8), 30])

    ws4 = wb.create_sheet("10. Equipe")  # fora do mapa: ignorada com aviso
    ws4.append(["Linha", "Nome"])
    ws4.append([1, "Fulano"])
    wb.save(caminho)


class ConsolidarExcelTestes(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.arquivo = f"{self.tmp.name}/mock.xlsx"
        _workbook_mock(self.arquivo)

    def _por_chave(self, periodo="2026-04"):
        resultado = consolidar_excel(self.arquivo, periodo)
        return {(l["pilar"], l["tipo_recurso"]): l for l in resultado["linhas"]}, resultado

    def test_agregacao_por_pilar_com_filtro_de_mes(self):
        mapa, _ = self._por_chave("2026-04")
        self.assertEqual(mapa[("PDI", "EMBRAPII")]["valor_executado"], Decimal("375.50"))
        self.assertEqual(mapa[("PDI", "EMBRAPII")]["competencia"], "2026-04")
        self.assertEqual(mapa[("PDI", "EMBRAPII")]["valor_captado"], Decimal("0"))
        self.assertIn("3. Conta Ação - AFCCT", mapa[("PDI", "EMBRAPII")]["observacao"])

    def test_outro_mes_nao_contamina(self):
        mapa, _ = self._por_chave("2026-04")
        self.assertEqual(mapa[("PDI", "EMBRAPII")]["valor_executado"], Decimal("375.50"))
        mapa_maio, _ = self._por_chave("2026-05")
        self.assertEqual(mapa_maio[("PDI", "EMBRAPII")]["valor_executado"], Decimal("999"))

    def test_lei_tics_segregada_nunca_soma_no_at(self):
        mapa, _ = self._por_chave("2026-04")
        self.assertEqual(mapa[("AT", "AT")]["valor_executado"], Decimal("30"))
        self.assertEqual(mapa[("AT", "AT_LEI_TICS")]["valor_executado"], Decimal("60"))

    def test_aba_fora_do_mapa_gera_aviso(self):
        _, resultado = self._por_chave("2026-04")
        self.assertTrue(any("10. Equipe" in aviso for aviso in resultado["avisos"]))


class ProcessarExcelMestreCommandTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.erica = User.objects.create_user(username="erica", password="erica123")
        self.erica = adicionar_grupo(self.erica, "Master")
        Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=1)
        Pilar.objects.create(codigo="AT", nome="AT", ordem=2)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.arquivo = f"{self.tmp.name}/mock.xlsx"
        _workbook_mock(self.arquivo)

    def test_dry_run_imprime_json_e_nao_toca_o_banco(self):
        saida = io.StringIO()
        call_command(
            "processar_excel_mestre",
            arquivo=self.arquivo,
            periodo="2026-04",
            stdout=saida,
        )
        linhas = json.loads(saida.getvalue())
        self.assertEqual(len(linhas), 3)
        self.assertTrue(all(set(l) == {"competencia", "pilar", "tipo_recurso", "valor_captado", "valor_executado", "observacao"} for l in linhas))
        self.assertEqual(FinanceiroConsolidado.objects.count(), 0)
        self.assertEqual(ImportacaoFinanceira.objects.count(), 0)

    def test_aplicar_com_periodo_aberto_persiste_e_audita(self):
        periodo = Periodo.objects.create(competencia=date(2026, 4, 1), status="ABERTO", aberto_por=self.erica)
        saida = io.StringIO()
        call_command(
            "processar_excel_mestre",
            arquivo=self.arquivo,
            periodo="2026-04",
            aplicar=True,
            stdout=saida,
        )
        self.assertEqual(FinanceiroConsolidado.objects.filter(periodo=periodo).count(), 3)
        linha_at = FinanceiroConsolidado.objects.get(periodo=periodo, pilar__codigo="AT", tipo_recurso="AT")
        self.assertEqual(linha_at.valor_executado, Decimal("30"))
        linha_tics = FinanceiroConsolidado.objects.get(periodo=periodo, pilar__codigo="AT", tipo_recurso="AT_LEI_TICS")
        self.assertEqual(linha_tics.valor_executado, Decimal("60"))
        self.assertTrue(ImportacaoFinanceira.objects.filter(periodo=periodo, status="SUCESSO").exists())

    def test_aplicar_com_periodo_fechado_e_bloqueado(self):
        Periodo.objects.create(competencia=date(2026, 4, 1), status="FECHADO", aberto_por=self.erica)
        with self.assertRaisesRegex(CommandError, "fechado"):
            call_command(
                "processar_excel_mestre",
                arquivo=self.arquivo,
                periodo="2026-04",
                aplicar=True,
                stdout=io.StringIO(),
            )
        self.assertEqual(FinanceiroConsolidado.objects.count(), 0)

    def test_aplicar_sem_periodo_erro_amigavel(self):
        with self.assertRaisesRegex(CommandError, "não existe|nao existe|não encontrado|Período"):
            call_command(
                "processar_excel_mestre",
                arquivo=self.arquivo,
                periodo="2026-04",
                aplicar=True,
                stdout=io.StringIO(),
            )
