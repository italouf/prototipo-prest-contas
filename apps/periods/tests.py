"""Testes de períodos: transições, snapshot e auditoria (RF-040 a RF-045, RN-010)."""
from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.core.permissions import adicionar_grupo, garantir_grupos
from .models import Periodo
from .services import abrir_periodo, fechar_periodo, reabrir_periodo


class PeriodoTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.erica = User.objects.create_user(username="erica", password="erica123")
        self.erica = adicionar_grupo(self.erica, "Master")

    def test_competencia_unica_e_garantida(self):
        Periodo.objects.create(competencia=date(2026, 6, 1))
        with self.assertRaises(IntegrityError):
            Periodo.objects.create(competencia=date(2026, 6, 1))

    def test_master_consegue_fechar_periodo(self):
        periodo = Periodo.objects.create(competencia=date(2026, 6, 1))
        abrir_periodo(periodo, self.erica)
        fechar_periodo(periodo, self.erica)
        periodo.refresh_from_db()
        self.assertEqual(periodo.status, "FECHADO")
        self.assertIsNotNone(periodo.snapshot_json)
        self.assertIsNotNone(periodo.snapshot_gerado_em)

    def test_reabertura_exige_justificativa(self):
        periodo = Periodo.objects.create(competencia=date(2026, 6, 1))
        abrir_periodo(periodo, self.erica)
        fechar_periodo(periodo, self.erica)
        with self.assertRaises(ValidationError):
            reabrir_periodo(periodo, self.erica, "")
        with self.assertRaises(ValidationError):
            reabrir_periodo(periodo, self.erica, "   ")

    def test_auditoria_registra_fechamento_de_periodo(self):
        periodo = Periodo.objects.create(competencia=date(2026, 6, 1))
        abrir_periodo(periodo, self.erica)
        fechar_periodo(periodo, self.erica)
        self.assertTrue(AuditLog.objects.filter(acao="FECHAR_PERIODO", registro_id=str(periodo.pk)).exists())
