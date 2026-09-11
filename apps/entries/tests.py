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
from .models import Lancamento
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


class AprovacaoR3Testes(TestCase):
    def setUp(self):
        from apps.core.permissions import adicionar_grupo, garantir_grupos

        garantir_grupos()
        self.erica = adicionar_grupo(User.objects.create_user(username="r3_master", password="x"), "Master")
        self.pilar = Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=1)
        self.ind = Indicador.objects.create(pilar=self.pilar, codigo="PDI-PROJ-INI", nome="Projetos iniciados", tipo="QTD")
        Meta.objects.create(
            indicador=self.ind, competencia_inicio=date(2026, 1, 1),
            competencia_fim=date(2026, 12, 31), periodicidade="MENSAL", valor=2,
        )
        self.periodo = Periodo.objects.create(competencia=date(2026, 6, 1), status="ABERTO", aberto_por=self.erica)
        salvar_ou_enviar(self.periodo, self.pilar, self.erica, {str(self.ind.pk): {"valor": "1"}}, enviar=True)
        self.lc = Lancamento.objects.get(periodo=self.periodo)
        self.client.force_login(self.erica)

    def test_aprovacao_expoe_kanban_por_status(self):
        kanban = self.client.get(reverse("entries:aprovacao", args=[self.periodo.pk])).context["kanban"]
        self.assertEqual(list(kanban.keys()), ["RASCUNHO", "ENVIADO", "APROVADO", "DEVOLVIDO"])
        self.assertEqual(len(kanban["ENVIADO"]), 1)

    def test_timeline_do_lancamento_mostra_auditoria(self):
        self.client.post(
            reverse("entries:aprovacao", args=[self.periodo.pk]),
            {"lancamento_id": self.lc.pk, "aprovar": "1"},
        )
        resposta = self.client.get(reverse("entries:lancamento_drawer", args=[self.lc.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Lançamento aprovado")
        self.assertNotContains(resposta, "Painel de aprovação")

    def test_timeline_requer_gestor(self):
        from apps.core.permissions import adicionar_grupo

        auditor = adicionar_grupo(User.objects.create_user(username="r3_auditor", password="x"), "Auditor")
        self.client.force_login(auditor)
        resposta = self.client.get(reverse("entries:lancamento_drawer", args=[self.lc.pk]))
        self.assertEqual(resposta.status_code, 403)

    def test_formulario_tem_filtros_e_campos_de_validacao(self):
        resposta = self.client.get(reverse("entries:formulario", args=[self.periodo.pk, self.pilar.pk]))
        self.assertContains(resposta, 'data-testid="filtro-tipo-TODOS"')
        self.assertContains(resposta, 'data-testid="filtro-tipo-QTD"')
        self.assertContains(resposta, 'x-data="campoValor(')


class MoverLancamentoR7Testes(TestCase):
    """Drag-and-drop do kanban (R7): transições, permissões e justificativa."""

    def setUp(self):
        garantir_grupos()
        self.erica = adicionar_grupo(User.objects.create_user(username="r7_master", password="x"), "Master")
        self.pilar = Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=1)
        self.ind = Indicador.objects.create(pilar=self.pilar, codigo="PDI-PROJ-INI", nome="Projetos iniciados", tipo="QTD")
        Meta.objects.create(
            indicador=self.ind, competencia_inicio=date(2026, 1, 1),
            competencia_fim=date(2026, 12, 31), periodicidade="MENSAL", valor=2,
        )
        self.periodo = Periodo.objects.create(competencia=date(2026, 6, 1), status="ABERTO", aberto_por=self.erica)
        salvar_ou_enviar(self.periodo, self.pilar, self.erica, {str(self.ind.pk): {"valor": "1"}}, enviar=True)
        self.lc = Lancamento.objects.get(periodo=self.periodo)
        self.client.force_login(self.erica)

    def _mover(self, destino, justificativa=""):
        resposta = self.client.post(
            reverse("entries:lancamento_mover", args=[self.lc.pk]),
            {"destino": destino, "comentario_revisao": justificativa},
        )
        self.lc.refresh_from_db()
        return resposta

    def test_pagina_kanban_tem_atributos_de_drag(self):
        resposta = self.client.get(reverse("entries:aprovacao", args=[self.periodo.pk]))
        self.assertContains(resposta, 'data-testid="kanban"')
        self.assertContains(resposta, 'data-mover-url=')
        self.assertContains(resposta, 'data-card-id=')
        self.assertContains(resposta, 'draggable="true"')

    def test_enviar_de_rascunho_via_mover(self):
        self.lc.status = "RASCUNHO"
        self.lc.save(update_fields=["status"])
        resposta = self._mover("ENVIADO")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.lc.status, "ENVIADO")
        self.assertIn("success", resposta["HX-Trigger"])
        self.assertIn("Enviado", resposta["HX-Trigger"])

    def test_aprovar_via_mover(self):
        resposta = self._mover("APROVADO")
        self.assertEqual(self.lc.status, "APROVADO")
        self.assertIn("success", resposta["HX-Trigger"])

    def test_devolver_exige_justificativa(self):
        resposta = self._mover("DEVOLVIDO")
        self.assertEqual(self.lc.status, "ENVIADO")
        self.assertIn("error", resposta["HX-Trigger"])
        self._mover("DEVOLVIDO", "Ajustar a meta.")
        self.assertEqual(self.lc.status, "DEVOLVIDO")
        self.assertEqual(self.lc.comentario_revisao, "Ajustar a meta.")

    def test_destino_invalido_nao_muda_status(self):
        resposta = self._mover("RASCUNHO")
        self.assertEqual(self.lc.status, "ENVIADO")
        self.assertIn("error", resposta["HX-Trigger"])

    def test_periodo_fechado_bloqueia_envio(self):
        self.periodo.status = "FECHADO"
        self.periodo.save(update_fields=["status"])
        self.lc.status = "RASCUNHO"
        self.lc.save(update_fields=["status"])
        resposta = self._mover("ENVIADO")
        self.assertEqual(self.lc.status, "RASCUNHO")
        self.assertIn("error", resposta["HX-Trigger"])

    def test_requer_gestor(self):
        focal = adicionar_grupo(User.objects.create_user(username="r7_focal", password="x"), "PontoFocal")
        UsuarioPilar.objects.create(usuario=focal, pilar=self.pilar)
        self.client.force_login(focal)
        resposta = self.client.post(
            reverse("entries:lancamento_mover", args=[self.lc.pk]), {"destino": "APROVADO"}
        )
        self.assertEqual(resposta.status_code, 403)
        self.lc.refresh_from_db()
        self.assertEqual(self.lc.status, "ENVIADO")
