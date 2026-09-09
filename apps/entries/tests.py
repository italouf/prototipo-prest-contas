"""Testes de lançamentos e dashboards (RF-050 a RF-058, RF-060 a RF-065, RF-070 a RF-073)."""
from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.calculos import meta_realizado_percentual
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.indicators.models import Indicador, Meta
from apps.periods.models import Periodo
from apps.pillars.models import Pilar, UsuarioPilar
from .services import aprovar, salvar_ou_enviar


class LancamentoTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.master = User.objects.create_user(username="erica", password="erica123")
        self.master = adicionar_grupo(self.master, "Master")
        self.focal = User.objects.create_user(username="focal_pdi", password="focal123")
        self.focal = adicionar_grupo(self.focal, "PontoFocal")
        self.lideranca = User.objects.create_user(username="lideranca", password="lider123")
        self.lideranca = adicionar_grupo(self.lideranca, "Lideranca")
        self.auditor = User.objects.create_user(username="auditor", password="auditor123")
        self.auditor = adicionar_grupo(self.auditor, "Auditor")

        self.pdi = Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=1)
        self.formacao = Pilar.objects.create(codigo="FORMACAO", nome="Formação", ordem=2)
        UsuarioPilar.objects.create(usuario=self.focal, pilar=self.pdi)

        self.ind = Indicador.objects.create(pilar=self.pdi, codigo="PDI-PROJ-INI", nome="Projetos iniciados", unidade="projetos", tipo="QTD")
        self.ind_formacao = Indicador.objects.create(pilar=self.formacao, codigo="FORM-CURSOS", nome="Cursos lançados", unidade="cursos", tipo="QTD")
        Meta.objects.create(
            indicador=self.ind,
            competencia_inicio=date(2026, 1, 1),
            competencia_fim=date(2026, 12, 31),
            periodicidade="MENSAL",
            valor=10,
        )
        self.periodo = Periodo.objects.create(competencia=date(2026, 6, 1), status="ABERTO", aberto_por=self.master)

    def test_lancamento_duplicado_para_mesmo_periodo_e_indicador_e_bloqueado(self):
        dados = {str(self.ind.pk): {"valor": "5", "comentario": "primeiro"}}
        salvar_ou_enviar(self.periodo, self.pdi, self.focal, dados)
        salvar_ou_enviar(self.periodo, self.pdi, self.focal, {str(self.ind.pk): {"valor": "7", "comentario": "atualização"}})
        self.assertEqual(self.periodo.lancamentos.count(), 1)
        self.assertEqual(self.periodo.lancamentos.first().valor_numerico, 7)

    def test_ponto_focal_nao_acessa_pilar_nao_autorizado(self):
        with self.assertRaises(ValidationError):
            salvar_ou_enviar(self.periodo, self.formacao, self.focal, {str(self.ind_formacao.pk): {"valor": "1"}})
        self.client.force_login(self.focal)
        resposta = self.client.get(reverse("entries:formulario", args=[self.periodo.pk, self.formacao.pk]))
        self.assertEqual(resposta.status_code, 403)

    def test_lancamento_em_periodo_fechado_nao_pode_ser_editado(self):
        self.periodo.status = "FECHADO"
        self.periodo.save()
        with self.assertRaises(ValidationError):
            salvar_ou_enviar(self.periodo, self.pdi, self.focal, {str(self.ind.pk): {"valor": "5"}})

    def test_lideranca_nao_acessa_tela_de_lancamento(self):
        self.client.force_login(self.lideranca)
        resposta = self.client.get(reverse("entries:formulario", args=[self.periodo.pk, self.pdi.pk]))
        self.assertEqual(resposta.status_code, 403)

    def test_auditor_nao_acessa_edicao(self):
        self.client.force_login(self.auditor)
        resposta = self.client.get(reverse("entries:formulario", args=[self.periodo.pk, self.pdi.pk]))
        self.assertEqual(resposta.status_code, 403)

    def test_dashboard_calcula_percentual_corretamente(self):
        salvar_ou_enviar(self.periodo, self.pdi, self.focal, {str(self.ind.pk): {"valor": "5"}}, enviar=True)
        lc = self.periodo.lancamentos.get()
        aprovar(lc, self.master)
        resultado = meta_realizado_percentual(self.ind, self.periodo)
        self.assertEqual(resultado["percentual"], 50)
        self.client.force_login(self.master)
        resposta = self.client.get(reverse("core:dashboard"))
        self.assertContains(resposta, "50%")
