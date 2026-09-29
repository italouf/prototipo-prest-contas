from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.pillars.models import Pilar
from ..models import (
    Acompanhamento,
    CentroCompetencia,
    DespesaAcompanhamento,
    KpiAcompanhamento,
    OverrideAcompanhamento,
)


class AcompanhamentoUnicidadeTestes(TestCase):
    def test_centro_e_periodo_referencia_sao_unicos(self):
        centro = CentroCompetencia.objects.create(codigo="quiin", nome="QuIIN")
        Acompanhamento.objects.create(centro=centro, periodo_referencia="2T/2024")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Acompanhamento.objects.create(centro=centro, periodo_referencia="2T/2024")

    def test_mesmo_periodo_para_centros_diferentes_e_permitido(self):
        Acompanhamento.objects.create(
            centro=CentroCompetencia.objects.create(codigo="quiin", nome="QuIIN"),
            periodo_referencia="2T/2024")
        Acompanhamento.objects.create(
            centro=CentroCompetencia.objects.create(codigo="outro-cc", nome="Outro CC"),
            periodo_referencia="2T/2024")
        self.assertEqual(Acompanhamento.objects.count(), 2)


class OverrideChaveTestes(TestCase):
    def setUp(self):
        self.acomp = Acompanhamento.objects.create(
            centro=CentroCompetencia.objects.create(codigo="quiin", nome="QuIIN"),
            periodo_referencia="2T/2024")
        self.pilar = Pilar.objects.create(codigo="PDI", nome="PDI")

    def test_chave_unica_para_mesmo_acompanhamento(self):
        pilar = self.pilar
        OverrideAcompanhamento.objects.create(
            acompanhamento=self.acomp, base="financeiro", pilar=pilar,
            ano=2026, campo="executado", valor=10, chave="fin|PDI|2026|executado")
        with self.assertRaises(IntegrityError), transaction.atomic():
            OverrideAcompanhamento.objects.create(
                acompanhamento=self.acomp, base="financeiro", pilar=pilar,
                ano=2026, campo="executado", valor=11, chave="fin|PDI|2026|executado")

    def test_override_fisico_exige_kpi_e_rejeita_pilar(self):
        kpi = KpiAcompanhamento.objects.create(
            acompanhamento=self.acomp, codigo="PE-01", sequencia=1,
            nome="Projetos de PD&I", unidade="Número absoluto", pilar=self.pilar)
        objeto = OverrideAcompanhamento(
            acompanhamento=self.acomp, base="fisico", kpi=kpi,
            ano=2025, campo="executado", valor=5, chave="fis|PE-01|2025|executado")
        objeto.full_clean()

        invalido = OverrideAcompanhamento(
            acompanhamento=self.acomp, base="fisico",
            ano=2025, campo="executado", valor=5, chave="fis|?|2025|executado")
        with self.assertRaises(ValidationError):
            invalido.full_clean()

    def test_override_financeiro_com_pilar_e_sem_kpi_passa(self):
        objeto = OverrideAcompanhamento(
            acompanhamento=self.acomp, base="financeiro", pilar=self.pilar,
            ano=2026, campo="executado", valor=10, chave="fin|PDI|2026|executado")
        objeto.full_clean()

    def test_override_financeiro_exige_pilar_e_rejeita_kpi(self):
        sem_pilar = OverrideAcompanhamento(
            acompanhamento=self.acomp, base="financeiro",
            ano=2026, campo="previsto", valor=10, chave="fin|?|2026|previsto")
        with self.assertRaises(ValidationError):
            sem_pilar.full_clean()

        kpi = KpiAcompanhamento.objects.create(
            acompanhamento=self.acomp, codigo="PE-01", sequencia=1,
            nome="Projetos de PD&I", unidade="Número absoluto", pilar=self.pilar)
        com_kpi = OverrideAcompanhamento(
            acompanhamento=self.acomp, base="financeiro", pilar=self.pilar, kpi=kpi,
            ano=2026, campo="previsto", valor=10, chave="fin|PDI|2026|previsto")
        with self.assertRaises(ValidationError):
            com_kpi.full_clean()

    def test_override_fisico_com_pilar_e_rejeitado(self):
        kpi = KpiAcompanhamento.objects.create(
            acompanhamento=self.acomp, codigo="PE-01", sequencia=1,
            nome="Projetos de PD&I", unidade="Número absoluto", pilar=self.pilar)
        objeto = OverrideAcompanhamento(
            acompanhamento=self.acomp, base="fisico", kpi=kpi, pilar=self.pilar,
            ano=2025, campo="previsto", valor=5, chave="fis|PE-01|2025|previsto")
        with self.assertRaises(ValidationError):
            objeto.full_clean()


class PrecisaoValoresTestes(TestCase):
    """Guarda de regressão: valores com mais de 2 casas não podem ser truncados (Ruling 10)."""

    def setUp(self):
        self.acomp = Acompanhamento.objects.create(
            centro=CentroCompetencia.objects.create(codigo="quiin", nome="QuIIN"),
            periodo_referencia="2T/2024")
        self.pilar = Pilar.objects.create(codigo="PDI", nome="PDI")

    def test_kpi_preserva_valores_com_mais_de_duas_casas(self):
        kpi = KpiAcompanhamento.objects.create(
            acompanhamento=self.acomp, codigo="PE-02", sequencia=2,
            nome="Fração de meta", unidade="Fração", pilar=self.pilar,
            meta_2024=Decimal("0.0029"), gap=Decimal("-0.6235"))
        kpi.refresh_from_db()
        self.assertEqual(kpi.meta_2024, Decimal("0.0029"))
        self.assertEqual(kpi.gap, Decimal("-0.6235"))

    def test_valor_unitario_preserva_tres_casas(self):
        despesa = DespesaAcompanhamento.objects.create(
            acompanhamento=self.acomp, aba="3. Conta Ação - AFCCT", linha=10,
            pilar=self.pilar, tipo_recurso="EMBRAPII",
            valor_unitario=Decimal("61.725"))
        despesa.refresh_from_db()
        self.assertEqual(despesa.valor_unitario, Decimal("61.725"))
