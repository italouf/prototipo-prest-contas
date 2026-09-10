"""Testes de importação financeira (RF-080 a RF-087 / RN-003, RN-004, RN-015)."""
import io
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.periods.models import Periodo
from apps.pillars.models import Pilar
from .models import FinanceiroConsolidado, ImportacaoFinanceira
from .services import importar_csv


def _arquivo(conteudo, nome="fin.csv"):
    return SimpleUploadedFile(nome, conteudo.encode("utf-8"), content_type="text/csv")


CSV_VALIDO = """competencia,pilar,tipo_recurso,valor_captado,valor_executado,observacao
2026-06,PDI,EMBRAPII,0,500000,Execução comprovada
2026-06,AT,AT,750000,200000,Captação e execução parcial
2026-06,OUTRASFONTES,OUTRAS_FONTES,1000000,150000,Projeto plurianual
"""

CSV_EMBRAPPI = CSV_VALIDO.replace("EMBRAPII", "EMBRAPPI")

CSV_INVALIDO = """competencia,pilar,tipo_recurso,valor_captado,observacao
2026-06,PDI,EMBRAPII,0,falta coluna valor_executado
"""


class ImportacaoFinanceiraTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.erica = User.objects.create_user(username="erica", password="erica123")
        self.erica = adicionar_grupo(self.erica, "Master")
        self.pilar_pdi = Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=1)
        self.pilar_at = Pilar.objects.create(codigo="AT", nome="AT", ordem=2)
        self.pilar_of = Pilar.objects.create(codigo="OUTRASFONTES", nome="Outras Fontes", ordem=3)
        self.periodo = Periodo.objects.create(competencia=date(2026, 6, 1), status="ABERTO", aberto_por=self.erica)

    def test_csv_valido_cria_registros_financeiros(self):
        status, log = importar_csv(_arquivo(CSV_VALIDO), self.periodo, self.erica)
        self.assertEqual(status, "SUCESSO")
        self.assertEqual(FinanceiroConsolidado.objects.count(), 3)
        self.assertTrue(ImportacaoFinanceira.objects.filter(status="SUCESSO").exists())
        self.assertIn("3 linha(s)", log)

    def test_variacao_embrppi_e_normalizada(self):
        importar_csv(_arquivo(CSV_EMBRAPPI), self.periodo, self.erica)
        linha = FinanceiroConsolidado.objects.get(pilar=self.pilar_pdi)
        self.assertEqual(linha.tipo_recurso, "EMBRAPII")

    def test_csv_com_at_lei_tics_importa_com_sucesso(self):
        csv_tics = (
            "competencia,pilar,tipo_recurso,valor_captado,valor_executado,observacao\n"
            "2026-06,AT,AT_LEI_TICS,0,60000,Repasse Lei de TICs\n"
        )
        status, _ = importar_csv(_arquivo(csv_tics), self.periodo, self.erica)
        self.assertEqual(status, "SUCESSO")
        linha = FinanceiroConsolidado.objects.get(pilar=self.pilar_at, tipo_recurso="AT_LEI_TICS")
        self.assertEqual(linha.valor_executado, Decimal("60000"))

    def test_captado_e_executado_ficam_separados(self):
        importar_csv(_arquivo(CSV_VALIDO), self.periodo, self.erica)
        linha = FinanceiroConsolidado.objects.get(pilar=self.pilar_at)
        self.assertEqual(linha.valor_captado, Decimal("750000"))
        self.assertEqual(linha.valor_executado, Decimal("200000"))

    def test_csv_invalido_nao_cria_registros(self):
        status, log = importar_csv(_arquivo(CSV_INVALIDO), self.periodo, self.erica)
        self.assertEqual(status, "ERRO")
        self.assertEqual(FinanceiroConsolidado.objects.count(), 0)
        self.assertTrue(ImportacaoFinanceira.objects.filter(status="ERRO").exists())
        self.assertIn("Colunas obrigatórias", log)

    def test_pilar_inexistente_nao_cria_registros(self):
        csv_errado = CSV_VALIDO.replace("OUTRASFONTES", "PILARX")
        status, _ = importar_csv(_arquivo(csv_errado), self.periodo, self.erica)
        self.assertEqual(status, "ERRO")
        self.assertEqual(FinanceiroConsolidado.objects.count(), 0)

    def test_importacao_bloqueada_em_periodo_fechado(self):
        self.periodo.status = "FECHADO"
        self.periodo.save()
        with self.assertRaises(ValidationError):
            importar_csv(_arquivo(CSV_VALIDO), self.periodo, self.erica)

    def test_importacao_e_atomica(self):
        csv_misturado = io.StringIO()
        csv_misturado.write("competencia,pilar,tipo_recurso,valor_captado,valor_executado,observacao\n")
        csv_misturado.write("2026-06,PDI,EMBRAPII,0,100,\n")
        csv_misturado.write("2026-06,NAOEXISTE,EMBRAPII,0,100,\n")
        status, _ = importar_csv(_arquivo(csv_misturado.getvalue()), self.periodo, self.erica)
        self.assertEqual(status, "ERRO")
        self.assertEqual(FinanceiroConsolidado.objects.count(), 0)


class ImportarPreviewR3Testes(TestCase):
    def test_pagina_importar_tem_componente_de_preview(self):
        garantir_grupos()
        erica = adicionar_grupo(User.objects.create_user(username="r3_fin", password="x"), "Master")
        self.client.force_login(erica)
        resposta = self.client.get(reverse("finance:importar"))
        self.assertContains(resposta, 'x-data="previewCsv"')
        self.assertContains(resposta, 'data-testid="preview-csv"')
