"""Testes do relatório mensal (RF-090 a RF-097)."""
from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.indicators.models import Indicador, Meta
from apps.periods.models import Periodo
from apps.pillars.models import Pilar
from apps.entries.services import aprovar, salvar_ou_enviar


class RelatorioTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.erica = User.objects.create_user(username="erica", password="erica123")
        self.erica = adicionar_grupo(self.erica, "Master")
        self.pdi = Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=1)
        self.ind = Indicador.objects.create(pilar=self.pdi, codigo="PDI-PROJ-INI", nome="Projetos iniciados", tipo="QTD")
        Meta.objects.create(
            indicador=self.ind, competencia_inicio=date(2026, 1, 1), competencia_fim=date(2026, 12, 31),
            periodicidade="MENSAL", valor=2,
        )
        self.periodo = Periodo.objects.create(competencia=date(2026, 6, 1), status="ABERTO", aberto_por=self.erica)
        salvar_ou_enviar(self.periodo, self.pdi, self.erica, {str(self.ind.pk): {"valor": "1", "comentario": "Dois projetos na fila."}}, enviar=True)
        aprovar(self.periodo.lancamentos.get(), self.erica)

    def test_relatorio_mensal_apresenta_indicadores_por_pilar(self):
        self.client.force_login(self.erica)
        resposta = self.client.get(reverse("reports:mensal", args=[self.periodo.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Relatório Mensal")
        self.assertContains(resposta, "PDI / FCCT")
        self.assertContains(resposta, "Projetos iniciados")
        self.assertContains(resposta, "50%")
        self.assertContains(resposta, "Dois projetos na fila.")
