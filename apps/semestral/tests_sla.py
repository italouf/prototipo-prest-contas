"""Testes do motor de SLA mensal, links diretos, aprovação e Advertência Formal ITS1 (T3)."""
from datetime import date, datetime, timezone
from io import StringIO

from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.core.permissions import adicionar_grupo, garantir_grupos

from .models import (
    CicloSemestral,
    CompetenciaMensalPilar,
    ConfiguracaoPilarSemestral,
    LogNotificacaoSLA,
)
from .sla import (
    aprovar_competencia,
    devolver_competencia,
    disparar_alertas_mensais,
    gerar_link_direto,
    submeter_competencia,
    verificar_sla_e_emitir_its1,
)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class MotorSLATestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.user_master = adicionar_grupo(
            User.objects.create_user(
                username="master_sla", email="master.sla@quiin.local", password="x"
            ),
            "Master",
        )
        self.user_resp = adicionar_grupo(
            User.objects.create_user(
                username="resp_fcrh", email="resp.fcrh@quiin.local", password="x"
            ),
            "PontoFocal",
        )
        self.ciclo = CicloSemestral.objects.create(
            ano=2026,
            semestre=1,
            coordenacao_nome="Mabel",
            coordenacao_email="mabel.gestao@quiin.local",
        )
        self.cfg_fcrh = ConfiguracaoPilarSemestral.objects.create(
            codigo="FCRH",
            nome="FCRH — Formação e Capacitação de RH",
            arquivo_embrapii="FCRH",
            responsavel=self.user_resp,
            responsavel_nome="Coord. FCRH",
            responsavel_email="resp.fcrh@quiin.local",
            ordem=1,
        )
        self.cfg_at = ConfiguracaoPilarSemestral.objects.create(
            codigo="AT",
            nome="AT — Associação Tecnológica",
            arquivo_embrapii="AT",
            responsavel_nome="Coord. AT",
            responsavel_email="resp.at@quiin.local",
            ordem=2,
        )
        self.comp_fcrh = CompetenciaMensalPilar.objects.create(
            ciclo=self.ciclo,
            configuracao_pilar=self.cfg_fcrh,
            competencia=date(2026, 1, 1),
            prazo_limite=datetime(2026, 2, 5, 23, 59, tzinfo=timezone.utc),
        )
        self.comp_at = CompetenciaMensalPilar.objects.create(
            ciclo=self.ciclo,
            configuracao_pilar=self.cfg_at,
            competencia=date(2026, 1, 1),
            prazo_limite=datetime(2026, 2, 5, 23, 59, tzinfo=timezone.utc),
        )

    def test_fluxo_completo_alerta_its1_coordenacao_e_regularizacao(self):
        mail.outbox.clear()

        # 1. Disparo de alertas mensais com link direto e deadline
        res_alert = disparar_alertas_mensais(
            competencia_date=date(2026, 1, 1),
            ciclo=self.ciclo,
            base_url="https://sig.quiin.local",
            actor=self.user_resp,
        )
        self.assertEqual(res_alert["enviados"], 2)
        self.comp_fcrh.refresh_from_db()
        self.assertEqual(self.comp_fcrh.status, "ALERTA_ENVIADO")
        self.assertIsNotNone(self.comp_fcrh.alerta_inicial_em)
        self.assertEqual(len(mail.outbox), 2)
        link_fcrh = gerar_link_direto(self.comp_fcrh, base_url="https://sig.quiin.local")
        self.assertIn(link_fcrh, mail.outbox[0].body)
        self.assertIn("05/02/2026", mail.outbox[0].body)

        # 2. AT submete dentro do prazo -> SUBMETIDO_NO_PRAZO + EM_ANALISE
        submeter_competencia(
            self.comp_at,
            usuario=self.user_resp,
            observacao="Entregue no prazo.",
            agora=datetime(2026, 2, 4, 15, 0, tzinfo=timezone.utc),
        )
        self.comp_at.refresh_from_db()
        self.assertEqual(self.comp_at.status, "SUBMETIDO_NO_PRAZO")
        self.assertEqual(self.comp_at.status_aprovacao, "EM_ANALISE")

        # 3. Passa do prazo limite (FCRH inadimplente; AT já submetido)
        mail.outbox.clear()
        res_its1 = verificar_sla_e_emitir_its1(
            agora=datetime(2026, 2, 6, 9, 0, tzinfo=timezone.utc),
            ciclo=self.ciclo,
            base_url="https://sig.quiin.local",
            actor=self.user_resp,
        )
        self.assertEqual(res_its1["emitidas"], 1)
        self.assertEqual(res_its1["ocorrencias"][0]["pilar"], "FCRH")

        self.comp_fcrh.refresh_from_db()
        self.assertEqual(self.comp_fcrh.status, "ATRASADO_ITS1_EMITIDA")
        self.assertIsNotNone(self.comp_fcrh.its1_emitida_em)

        # Valida e-mails: Advertência ITS1 (para FCRH com Mabel em CC) + Comunicado dedicado a Mabel
        self.assertEqual(len(mail.outbox), 2)
        email_resp, email_coord = mail.outbox[0], mail.outbox[1]
        self.assertIn("ITS1", email_resp.subject)
        self.assertEqual(email_resp.to, ["resp.fcrh@quiin.local"])
        self.assertEqual(email_resp.cc, ["mabel.gestao@quiin.local"])
        self.assertIn(link_fcrh, email_resp.body)
        self.assertEqual(email_coord.to, ["mabel.gestao@quiin.local"])
        self.assertIn("ITS1", email_coord.subject)
        self.assertIn("FCRH", email_coord.body)

        # Valida Logs SLA e Trilha de Auditoria
        self.assertEqual(
            LogNotificacaoSLA.objects.filter(
                competencia=self.comp_fcrh,
                tipo_evento="ADVERTENCIA_ITS1",
                codigo_ocorrencia="ITS1",
            ).count(),
            1,
        )
        self.assertEqual(
            LogNotificacaoSLA.objects.filter(
                competencia=self.comp_fcrh,
                tipo_evento="COMUNICADO_COORDENACAO",
                codigo_ocorrencia="ITS1",
            ).count(),
            1,
        )
        self.assertTrue(
            AuditLog.objects.filter(
                acao="SEMESTRAL_ITS1_EMITIDA",
                entidade="CompetenciaMensalPilar",
                registro_id=str(self.comp_fcrh.pk),
            ).exists()
        )

        # 4. Reexecução idempotente não duplica ITS1
        mail.outbox.clear()
        res_dup = verificar_sla_e_emitir_its1(
            agora=datetime(2026, 2, 7, 9, 0, tzinfo=timezone.utc),
            ciclo=self.ciclo,
        )
        self.assertEqual(res_dup["emitidas"], 0)
        self.assertEqual(len(mail.outbox), 0)

        # 5. Submissão tardia regulariza a competência e envia para análise
        submeter_competencia(
            self.comp_fcrh,
            usuario=self.user_resp,
            observacao="Regularizado após ajuste.",
            agora=datetime(2026, 2, 8, 11, 0, tzinfo=timezone.utc),
        )
        self.comp_fcrh.refresh_from_db()
        self.assertEqual(self.comp_fcrh.status, "REGULARIZADO")
        self.assertEqual(self.comp_fcrh.status_aprovacao, "EM_ANALISE")
        self.assertIsNotNone(self.comp_fcrh.regularizado_em)
        self.assertTrue(
            LogNotificacaoSLA.objects.filter(
                competencia=self.comp_fcrh, tipo_evento="REGULARIZACAO"
            ).exists()
        )

    def test_fluxo_devolucao_reenvio_e_aprovacao_preservando_sla(self):
        # Simula ITS1 + regularização
        verificar_sla_e_emitir_its1(
            agora=datetime(2026, 2, 6, 9, 0, tzinfo=timezone.utc),
            ciclo=self.ciclo,
        )
        self.comp_fcrh.refresh_from_db()
        submeter_competencia(self.comp_fcrh, usuario=self.user_resp, observacao="Envio inicial.")
        self.comp_fcrh.refresh_from_db()
        self.assertEqual(self.comp_fcrh.status, "REGULARIZADO")
        self.assertEqual(self.comp_fcrh.status_aprovacao, "EM_ANALISE")

        # PontoFocal não pode aprovar nem devolver
        with self.assertRaises(PermissionDenied):
            aprovar_competencia(self.comp_fcrh, usuario=self.user_resp)
        with self.assertRaises(PermissionDenied):
            devolver_competencia(self.comp_fcrh, usuario=self.user_resp, justificativa="x")

        # Devolução sem justificativa falha
        with self.assertRaises(ValidationError):
            devolver_competencia(self.comp_fcrh, usuario=self.user_master, justificativa="   ")

        # Master devolve com justificativa
        mail.outbox.clear()
        devolver_competencia(
            self.comp_fcrh,
            usuario=self.user_master,
            justificativa="Faltou informar o valor planejado.",
            base_url="https://sig.quiin.local",
        )
        self.comp_fcrh.refresh_from_db()
        self.assertEqual(self.comp_fcrh.status_aprovacao, "DEVOLVIDO")
        self.assertEqual(self.comp_fcrh.status, "REGULARIZADO")
        self.assertEqual(self.comp_fcrh.comentario_revisao, "Faltou informar o valor planejado.")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Faltou informar o valor planejado.", mail.outbox[0].body)
        self.assertTrue(
            LogNotificacaoSLA.objects.filter(
                competencia=self.comp_fcrh, tipo_evento="DEVOLUCAO_SEMESTRAL"
            ).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(
                acao="SEMESTRAL_DEVOLVIDO",
                entidade="CompetenciaMensalPilar",
                registro_id=str(self.comp_fcrh.pk),
            ).exists()
        )

        # PontoFocal reenvia -> volta para EM_ANALISE preservando SLA REGULARIZADO
        submeter_competencia(self.comp_fcrh, usuario=self.user_resp, observacao="Corrigido.")
        self.comp_fcrh.refresh_from_db()
        self.assertEqual(self.comp_fcrh.status_aprovacao, "EM_ANALISE")
        self.assertEqual(self.comp_fcrh.status, "REGULARIZADO")
        self.assertEqual(self.comp_fcrh.comentario_revisao, "")

        # Master aprova
        mail.outbox.clear()
        aprovar_competencia(
            self.comp_fcrh,
            usuario=self.user_master,
            comentario="Tudo conferido.",
            base_url="https://sig.quiin.local",
        )
        self.comp_fcrh.refresh_from_db()
        self.assertEqual(self.comp_fcrh.status_aprovacao, "APROVADO")
        self.assertEqual(self.comp_fcrh.revisado_por, self.user_master)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(
            LogNotificacaoSLA.objects.filter(
                competencia=self.comp_fcrh, tipo_evento="APROVACAO_SEMESTRAL"
            ).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(
                acao="SEMESTRAL_APROVADO",
                entidade="CompetenciaMensalPilar",
                registro_id=str(self.comp_fcrh.pk),
            ).exists()
        )

    def test_ciclo_consolidado_ou_enviado_bloqueia_submissao_focal_e_audita_gestor(self):
        for status_bloqueio in ("CONSOLIDADO", "ENVIADO"):
            self.ciclo.status = status_bloqueio
            self.ciclo.save(update_fields=["status"])
            self.comp_fcrh.refresh_from_db()
            self.assertTrue(self.ciclo.bloqueado_para_edicao_focal)
            self.assertTrue(self.comp_fcrh.bloqueada_por_ciclo)
            self.assertTrue(self.comp_fcrh.bloqueada_para_focal)

            with self.assertRaises(PermissionDenied):
                submeter_competencia(
                    self.comp_fcrh,
                    usuario=self.user_resp,
                    observacao="Tentativa bloqueada",
                )

            submeter_competencia(
                self.comp_fcrh,
                usuario=self.user_master,
                observacao=f"Ajuste excepcional em {status_bloqueio}",
                agora=datetime(2026, 2, 4, 10, 0, tzinfo=timezone.utc),
            )
            log = (
                AuditLog.objects.filter(
                    acao="SEMESTRAL_SUBMETIDO",
                    entidade="CompetenciaMensalPilar",
                    registro_id=str(self.comp_fcrh.pk),
                    usuario=self.user_master,
                )
                .order_by("-id")
                .first()
            )
            self.assertIsNotNone(log)
            self.assertIn(
                f"[Ajuste excepcional Master/Admin em ciclo {status_bloqueio}]",
                log.justificativa,
            )

    def test_management_command_verificar_sla(self):
        out = StringIO()
        call_command(
            "verificar_sla_semestral",
            "--enviar-alertas",
            "--competencia=2026-01",
            "--referencia=2026-02-07T10:00:00",
            stdout=out,
        )
        self.assertIn("Alertas mensais enviados: 2", out.getvalue())
        self.assertIn("Advertências ITS1 emitidas: 2", out.getvalue())
