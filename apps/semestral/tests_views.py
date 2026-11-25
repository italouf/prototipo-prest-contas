"""Testes de integração HTTP, RBAC, Coleta Mensal, Aprovação, SLA/ITS1 e Downloads (T4/T5)."""
from datetime import date, datetime, timezone
from io import BytesIO
from zipfile import ZipFile

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.periods.models import Periodo
from apps.pillars.models import Pilar, UsuarioPilar

from .models import (
    CicloSemestral,
    CompetenciaMensalPilar,
    ConfiguracaoPilarSemestral,
    LogNotificacaoSLA,
)
from .models_registros import RegFcrhProjeto
from .xlsx_exporter import TEMPLATE_MAP, validar_integridade_xlsx


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class SemestralViewsRBACTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        garantir_grupos()
        for idx, (cod, nome) in enumerate(
            [
                ("PDI", "PDI / FCCT"),
                ("FORMACAO", "Formação"),
                ("STARTUPS", "Startups"),
                ("AT", "Associação Tecnológica"),
                ("OUTRASFONTES", "Outras Fontes"),
            ],
            start=1,
        ):
            Pilar.objects.get_or_create(codigo=cod, defaults={"nome": nome, "ordem": idx})

        cls.master = adicionar_grupo(
            User.objects.create_user(
                username="sem_v_master", email="master@quiin.local", password="x"
            ),
            "Master",
        )
        cls.admin_user = adicionar_grupo(
            User.objects.create_user(
                username="sem_v_admin", email="admin@quiin.local", password="x"
            ),
            "Admin",
        )
        cls.focal_fcrh = adicionar_grupo(
            User.objects.create_user(
                username="focal_formacao", email="fcrh@quiin.local", password="x"
            ),
            "PontoFocal",
        )
        pilar_fcrh = Pilar.objects.get(codigo="FORMACAO")
        UsuarioPilar.objects.get_or_create(usuario=cls.focal_fcrh, pilar=pilar_fcrh)

        cls.auditor = adicionar_grupo(
            User.objects.create_user(
                username="sem_v_auditor", email="auditor@quiin.local", password="x"
            ),
            "Auditor",
        )

        call_command("seed_semestral_v31", "--ano=2026")

    def setUp(self):
        self.ciclo = CicloSemestral.objects.get(ano=2026, semestre=1)
        self.comp_fcrh_jan = CompetenciaMensalPilar.objects.get(
            ciclo=self.ciclo,
            configuracao_pilar__codigo="FCRH",
            competencia=date(2026, 1, 1),
        )
        self.comp_at_jan = CompetenciaMensalPilar.objects.get(
            ciclo=self.ciclo,
            configuracao_pilar__codigo="AT",
            competencia=date(2026, 1, 1),
        )

    def test_acesso_anonimo_redireciona_login(self):
        for url in [
            reverse("core:semestral"),
            reverse("semestral:competencia_form", args=[self.comp_fcrh_jan.pk]),
            reverse("semestral:acesso_direto", args=[self.comp_fcrh_jan.token_acesso]),
            reverse("semestral:exportar_xlsx", args=["FCRH"]),
        ]:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 302)
            self.assertIn("/accounts/login/", resp["Location"])

    def test_rbac_ponto_focal_e_auditor(self):
        # PontoFocal FCRH vê FCRH e não acessa AT
        self.client.force_login(self.focal_fcrh)
        painel = self.client.get(reverse("core:semestral"), {"ano": 2026, "semestre": 1})
        self.assertEqual(painel.status_code, 200)
        self.assertContains(painel, "FCRH")
        self.assertNotContains(painel, "AT — Associação Tecnológica")

        self.assertEqual(
            self.client.get(
                reverse("semestral:competencia_form", args=[self.comp_fcrh_jan.pk])
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse("semestral:competencia_form", args=[self.comp_at_jan.pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse("semestral:exportar_xlsx", args=["AT"])).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse("semestral:exportar_pacote")).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(reverse("semestral:sla_disparar_alertas")).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(reverse("semestral:sla_verificar_its1")).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse("semestral:configurar_ciclo")).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse("semestral:aprovar_competencia", args=[self.comp_fcrh_jan.pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse("semestral:devolver_competencia", args=[self.comp_fcrh_jan.pk]),
                {"justificativa": "Tentativa indevida"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse("semestral:arquivar_competencia", args=[self.comp_fcrh_jan.pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(reverse("semestral:arquivar_aprovados_lote")).status_code,
            403,
        )

        # Auditor tem leitura em tudo, mas 403 em escrita
        self.client.force_login(self.auditor)
        self.assertEqual(
            self.client.get(
                reverse("semestral:competencia_form", args=[self.comp_at_jan.pk])
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                reverse("semestral:submeter_competencia", args=[self.comp_fcrh_jan.pk])
            ).status_code,
            403,
        )

    def test_coleta_mensal_dropdown_oficial_codigo_preview_e_crud(self):
        self.client.force_login(self.focal_fcrh)
        # Link direto tokenizado redireciona para a aba solicitada
        resp_link = self.client.get(
            reverse("semestral:acesso_direto", args=[self.comp_fcrh_jan.token_acesso]),
            {"aba": "fcrh-2"},
        )
        self.assertEqual(resp_link.status_code, 302)
        self.assertIn("aba=fcrh-2", resp_link["Location"])

        form_url = f"{reverse('semestral:competencia_form', args=[self.comp_fcrh_jan.pk])}?aba=fcrh-2"

        # Valor inválido fora da ListaDominioEmbrapii deve ser rejeitado
        resp_bad = self.client.post(
            form_url,
            {
                "titulo": "Curso Teste Inválido",
                "objetivo": "Obj",
                "descricao_publica": "Desc",
                "ementa_detalhada": "Ementa",
                "carga_horaria_total": "20",
                "publico_alvo": "Engenheiros",
                "status_atual": "VALOR_INEXISTENTE",
                "valor_total_planejado": "1000.00",
                "data_inicio": "2026-01-10",
                "qtd_iniciaram": 10,
                "qtd_concluiram": 8,
                "tipo_formacao": "Curso de curta duração",
                "onde_realizada": "No próprio CC",
                "vinculo_linhas_tematicas": "Computação Quântica",
                "qtd_empresas_at": 2,
            },
        )
        self.assertEqual(resp_bad.status_code, 200)
        self.assertEqual(RegFcrhProjeto.objects.count(), 0)

        # Submissão válida com valores oficiais da planilha
        resp_ok = self.client.post(
            form_url,
            {
                "titulo": "Bootcamp Qiskit QuIIN",
                "objetivo": "Capacitar pesquisadores",
                "descricao_publica": "Descrição pública",
                "ementa_detalhada": "Módulos 1 a 3",
                "carga_horaria_total": "60.0",
                "publico_alvo": "Engenheiros",
                "status_atual": "Em andamento",
                "valor_total_planejado": "95000.00",
                "data_inicio": "2026-01-15",
                "qtd_iniciaram": 30,
                "qtd_concluiram": 25,
                "tipo_formacao": "Curso de curta duração",
                "onde_realizada": "No próprio CC",
                "vinculo_linhas_tematicas": "Computação Quântica",
                "qtd_empresas_at": 3,
                "observacoes": "Turma inaugural",
            },
        )
        self.assertEqual(resp_ok.status_code, 302)
        proj = RegFcrhProjeto.objects.get(titulo="Bootcamp Qiskit QuIIN")
        self.assertTrue(
            AuditLog.objects.filter(
                acao="SEMESTRAL_REGISTRO_CRIADO",
                entidade="RegFcrhProjeto",
                registro_id=str(proj.pk),
            ).exists()
        )

        # Verifica exibição do código preview determinístico na listagem
        pagina = self.client.get(form_url)
        self.assertContains(pagina, "QIN-FCRH-2026-1-15-1")

        # Edição
        edit_url = f"{form_url}&editar={proj.pk}"
        self.client.post(
            edit_url,
            {
                "titulo": "Bootcamp Qiskit QuIIN v2",
                "objetivo": "Capacitar pesquisadores",
                "descricao_publica": "Descrição pública",
                "ementa_detalhada": "Módulos 1 a 3",
                "carga_horaria_total": "60.0",
                "publico_alvo": "Engenheiros",
                "status_atual": "Concluído",
                "valor_total_planejado": "95000.00",
                "data_inicio": "2026-01-15",
                "qtd_iniciaram": 30,
                "qtd_concluiram": 28,
                "tipo_formacao": "Curso de curta duração",
                "onde_realizada": "No próprio CC",
                "vinculo_linhas_tematicas": "Computação Quântica",
                "qtd_empresas_at": 3,
                "observacoes": "Atualizado",
            },
        )
        proj.refresh_from_db()
        self.assertEqual(proj.titulo, "Bootcamp Qiskit QuIIN v2")

        # Exclusão
        del_url = reverse(
            "semestral:excluir_registro",
            args=[self.comp_fcrh_jan.pk, "fcrh-2", proj.pk],
        )
        self.client.post(del_url)
        self.assertFalse(RegFcrhProjeto.objects.filter(pk=proj.pk).exists())

    def test_aprovacao_cross_mes_centralizada_arquivamento_e_bloqueio_focal(self):
        # Período aberto no portal é 02/2026, enquanto o focal submete 01/2026
        periodo_fev = Periodo.objects.create(competencia=date(2026, 2, 1), status="ABERTO")
        RegFcrhProjeto.objects.create(
            competencia_mensal=self.comp_fcrh_jan,
            titulo="Curso Quântico 2026",
            objetivo="Capacitar",
            descricao_publica="Desc",
            ementa_detalhada="Ementa",
            carga_horaria_total="40.0",
            publico_alvo="Engenheiros",
            status_atual="Em andamento",
            valor_total_planejado="50000.00",
            data_inicio=date(2026, 1, 10),
            qtd_iniciaram=20,
            qtd_concluiram=18,
            tipo_formacao="Curso de curta duração",
            onde_realizada="No próprio CC",
            vinculo_linhas_tematicas="Computação Quântica",
            qtd_empresas_at=2,
            criado_por=self.focal_fcrh,
        )

        # 1. Focal submete 01/2026 -> vai para EM_ANALISE
        self.client.force_login(self.focal_fcrh)
        resp_sub = self.client.post(
            reverse("semestral:submeter_competencia", args=[self.comp_fcrh_jan.pk]),
            {"observacao_submissao": "Entrega FCRH 01/2026 pronta para análise."},
        )
        self.assertEqual(resp_sub.status_code, 302)
        self.comp_fcrh_jan.refresh_from_db()
        self.assertEqual(self.comp_fcrh_jan.status_aprovacao, "EM_ANALISE")

        # 2. Master abre o Painel de aprovação de 02/2026 e AINDA vê a entrega de 01/2026 + badge
        self.client.force_login(self.master)
        board_url = reverse("entries:aprovacao", args=[periodo_fev.pk])
        board_resp = self.client.get(board_url)
        self.assertEqual(board_resp.status_code, 200)
        self.assertContains(board_resp, 'data-testid="semestral-approval-card"')
        self.assertContains(board_resp, "01/2026")
        self.assertContains(board_resp, "Entrega FCRH 01/2026 pronta para análise.")
        self.assertContains(board_resp, "1 registro(s)")
        self.assertEqual(board_resp.context["pendencias_aprovacao"], 1)

        # Filtro opcional apenas do mês (02/2026) oculta 01/2026 quando solicitado
        board_mes_resp = self.client.get(f"{board_url}?semestral_escopo=mes")
        self.assertNotContains(board_mes_resp, "Entrega FCRH 01/2026 pronta para análise.")

        # 3. Ao abrir a tela do formulário semestral como Master, NÃO há botões de aprovar/devolver lá
        comp_resp = self.client.get(
            reverse("semestral:competencia_form", args=[self.comp_fcrh_jan.pk])
        )
        self.assertNotContains(comp_resp, 'data-testid="painel-revisao-semestral"')
        self.assertNotContains(comp_resp, 'data-testid="btn-aprovar-competencia"')
        self.assertContains(comp_resp, 'data-testid="btn-revisar-no-painel-aprovacao"')

        # 4. Master devolve com justificativa diretamente pelo Painel de aprovação
        r_dev = self.client.post(
            reverse("semestral:devolver_competencia", args=[self.comp_fcrh_jan.pk]),
            {"justificativa": "Detalhar carga horária prática.", "next": board_url},
        )
        self.assertRedirects(r_dev, board_url)
        self.comp_fcrh_jan.refresh_from_db()
        self.assertEqual(self.comp_fcrh_jan.status_aprovacao, "DEVOLVIDO")

        # 5. Focal vê banner de devolução e reenvia
        self.client.force_login(self.focal_fcrh)
        form_resp = self.client.get(
            reverse("semestral:competencia_form", args=[self.comp_fcrh_jan.pk])
        )
        self.assertContains(form_resp, 'data-testid="banner-devolvido-semestral"')
        self.assertContains(form_resp, "Detalhar carga horária prática.")
        self.client.post(
            reverse("semestral:submeter_competencia", args=[self.comp_fcrh_jan.pk]),
            {"observacao_submissao": "Carga horária detalhada."},
        )
        self.comp_fcrh_jan.refresh_from_db()
        self.assertEqual(self.comp_fcrh_jan.status_aprovacao, "EM_ANALISE")

        # 6. Master aprova pelo Painel de aprovação
        self.client.force_login(self.master)
        r_apr = self.client.post(
            reverse("semestral:aprovar_competencia", args=[self.comp_fcrh_jan.pk]),
            {"next": board_url},
        )
        self.assertRedirects(r_apr, board_url)
        self.comp_fcrh_jan.refresh_from_db()
        self.assertEqual(self.comp_fcrh_jan.status_aprovacao, "APROVADO")
        self.assertFalse(self.comp_fcrh_jan.arquivado_painel)

        # 7. Master arquiva e restaura o card aprovado no Painel de aprovação
        r_arq = self.client.post(
            reverse("semestral:arquivar_competencia", args=[self.comp_fcrh_jan.pk]),
            {"acao": "arquivar", "next": board_url},
        )
        self.assertRedirects(r_arq, board_url)
        self.comp_fcrh_jan.refresh_from_db()
        self.assertTrue(self.comp_fcrh_jan.arquivado_painel)
        board_arq = self.client.get(board_url)
        self.assertContains(board_arq, 'data-testid="semestral-arquivados-drawer"')
        self.assertContains(board_arq, 'data-testid="semestral-archived-item"')

        r_desarq = self.client.post(
            reverse("semestral:arquivar_competencia", args=[self.comp_fcrh_jan.pk]),
            {"acao": "desarquivar", "next": board_url},
        )
        self.assertRedirects(r_desarq, board_url)
        self.comp_fcrh_jan.refresh_from_db()
        self.assertFalse(self.comp_fcrh_jan.arquivado_painel)

        # Arquivar todos em lote
        r_lote = self.client.post(
            reverse("semestral:arquivar_aprovados_lote"),
            {"next": board_url},
        )
        self.assertRedirects(r_lote, board_url)
        self.comp_fcrh_jan.refresh_from_db()
        self.assertTrue(self.comp_fcrh_jan.arquivado_painel)

        # 8. Após aprovação, PontoFocal não pode mais editar nem excluir registros (403)
        self.client.force_login(self.focal_fcrh)
        proj = RegFcrhProjeto.objects.get(competencia_mensal=self.comp_fcrh_jan)
        self.assertEqual(
            self.client.post(
                reverse(
                    "semestral:excluir_registro",
                    args=[self.comp_fcrh_jan.pk, "fcrh-2", proj.pk],
                )
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse("semestral:submeter_competencia", args=[self.comp_fcrh_jan.pk])
            ).status_code,
            403,
        )

    def _payload_config_ciclo(self, status: str) -> dict:
        payload = {
            "ciclo-centro_competencia": self.ciclo.centro_competencia,
            "ciclo-abreviacao_cc": self.ciclo.abreviacao_cc,
            "ciclo-termo_cooperacao": self.ciclo.termo_cooperacao,
            "ciclo-periodo_referencia_label": self.ciclo.periodo_referencia_label,
            "ciclo-coordenacao_nome": self.ciclo.coordenacao_nome,
            "ciclo-coordenacao_email": self.ciclo.coordenacao_email,
            "ciclo-status": status,
        }
        for p in ConfiguracaoPilarSemestral.objects.order_by("ordem", "codigo"):
            pref = f"pilar_{p.codigo}"
            payload[f"{pref}-responsavel"] = p.responsavel_id or ""
            payload[f"{pref}-responsavel_nome"] = p.responsavel_nome
            payload[f"{pref}-responsavel_email"] = p.responsavel_email
            payload[f"{pref}-dia_limite_mensal"] = str(p.dia_limite_mensal)
            if p.ativo:
                payload[f"{pref}-ativo"] = "on"
        return payload

    def _payload_fcrh_projeto(self, titulo: str) -> dict:
        return {
            "titulo": titulo,
            "objetivo": "Capacitar pesquisadores",
            "descricao_publica": "Descrição pública",
            "ementa_detalhada": "Módulos 1 a 3",
            "carga_horaria_total": "40.0",
            "publico_alvo": "Engenheiros",
            "status_atual": "Em andamento",
            "valor_total_planejado": "50000.00",
            "data_inicio": "2026-01-10",
            "qtd_iniciaram": 20,
            "qtd_concluiram": 18,
            "tipo_formacao": "Curso de curta duração",
            "onde_realizada": "No próprio CC",
            "vinculo_linhas_tematicas": "Computação Quântica",
            "qtd_empresas_at": 2,
            "observacoes": "Obs teste",
        }

    def test_ciclo_consolidado_e_enviado_bloqueia_focal_e_permite_master_admin_auditado(self):
        proj_inicial = RegFcrhProjeto.objects.create(
            competencia_mensal=self.comp_fcrh_jan,
            titulo="Curso Inicial",
            objetivo="Capacitar",
            descricao_publica="Desc",
            ementa_detalhada="Ementa",
            carga_horaria_total="40.0",
            publico_alvo="Engenheiros",
            status_atual="Em andamento",
            valor_total_planejado="50000.00",
            data_inicio=date(2026, 1, 10),
            qtd_iniciaram=20,
            qtd_concluiram=18,
            tipo_formacao="Curso de curta duração",
            onde_realizada="No próprio CC",
            vinculo_linhas_tematicas="Computação Quântica",
            qtd_empresas_at=2,
            criado_por=self.focal_fcrh,
        )
        form_url = f"{reverse('semestral:competencia_form', args=[self.comp_fcrh_jan.pk])}?aba=fcrh-2"
        edit_url = f"{form_url}&editar={proj_inicial.pk}"
        del_url = reverse(
            "semestral:excluir_registro",
            args=[self.comp_fcrh_jan.pk, "fcrh-2", proj_inicial.pk],
        )
        sub_url = reverse("semestral:submeter_competencia", args=[self.comp_fcrh_jan.pk])
        cfg_url = f"{reverse('semestral:configurar_ciclo')}?ano=2026&semestre=1"

        # 1. Master altera status do ciclo para CONSOLIDADO pela view e valida AuditLog
        self.client.force_login(self.master)
        r_cfg = self.client.post(cfg_url, self._payload_config_ciclo("CONSOLIDADO"))
        self.assertEqual(r_cfg.status_code, 302)
        self.ciclo.refresh_from_db()
        self.assertEqual(self.ciclo.status, "CONSOLIDADO")
        self.assertTrue(
            AuditLog.objects.filter(
                acao="SEMESTRAL_CONFIG_ATUALIZADA",
                entidade="CicloSemestral",
                registro_id=str(self.ciclo.pk),
                campo="status",
                valor_anterior="ABERTO",
                valor_novo="CONSOLIDADO",
            ).exists()
        )

        # 2. Tanto em CONSOLIDADO quanto em ENVIADO, PontoFocal fica somente leitura (403 em qualquer mutação)
        for status_bloqueio in ("CONSOLIDADO", "ENVIADO"):
            if self.ciclo.status != status_bloqueio:
                self.client.force_login(self.master)
                self.client.post(cfg_url, self._payload_config_ciclo(status_bloqueio))
                self.ciclo.refresh_from_db()
                self.assertEqual(self.ciclo.status, status_bloqueio)

            self.client.force_login(self.focal_fcrh)
            painel = self.client.get(reverse("core:semestral"), {"ano": 2026, "semestre": 1})
            self.assertEqual(painel.status_code, 200)
            self.assertContains(painel, 'data-testid="badge-status-ciclo"')
            self.assertContains(painel, 'data-testid="banner-ciclo-bloqueado"')

            get_form = self.client.get(form_url)
            self.assertEqual(get_form.status_code, 200)
            self.assertContains(get_form, 'data-testid="banner-bloqueio-ciclo-focal"')
            self.assertNotContains(get_form, 'data-testid="btn-salvar-registro"')
            self.assertNotContains(get_form, 'data-testid="btn-submeter-competencia"')

            # Tentativas de criar, editar, excluir e submeter retornam 403 e não alteram banco
            self.assertEqual(
                self.client.post(form_url, self._payload_fcrh_projeto("Bloqueado")).status_code,
                403,
            )
            self.assertEqual(
                self.client.post(edit_url, self._payload_fcrh_projeto("Edit Bloqueado")).status_code,
                403,
            )
            self.assertEqual(self.client.post(del_url).status_code, 403)
            self.assertEqual(
                self.client.post(sub_url, {"observacao_submissao": "Bloqueado"}).status_code,
                403,
            )
            self.assertEqual(RegFcrhProjeto.objects.count(), 1)
            proj_inicial.refresh_from_db()
            self.assertEqual(proj_inicial.titulo, "Curso Inicial")

        # 3. Exceção exclusiva: Master e Admin continuam podendo criar, editar, submeter e excluir em ENVIADO, com AuditLog
        for gestor_user in (self.master, self.admin_user):
            self.client.force_login(gestor_user)
            get_gestor = self.client.get(form_url)
            self.assertEqual(get_gestor.status_code, 200)
            self.assertContains(get_gestor, 'data-testid="banner-excecao-gestor-ciclo"')
            self.assertContains(get_gestor, 'data-testid="btn-salvar-registro"')

            titulo_novo = f"Ajuste {gestor_user.username}"
            r_create = self.client.post(form_url, self._payload_fcrh_projeto(titulo_novo))
            self.assertEqual(r_create.status_code, 302)
            reg = RegFcrhProjeto.objects.get(titulo=titulo_novo)

            r_edit = self.client.post(
                f"{form_url}&editar={reg.pk}",
                self._payload_fcrh_projeto(f"{titulo_novo} Editado"),
            )
            self.assertEqual(r_edit.status_code, 302)
            reg.refresh_from_db()
            self.assertEqual(reg.titulo, f"{titulo_novo} Editado")

            r_sub = self.client.post(sub_url, {"observacao_submissao": f"Submissão {gestor_user.username}"})
            self.assertEqual(r_sub.status_code, 302)

            r_del = self.client.post(
                reverse(
                    "semestral:excluir_registro",
                    args=[self.comp_fcrh_jan.pk, "fcrh-2", reg.pk],
                )
            )
            self.assertEqual(r_del.status_code, 302)
            self.assertFalse(RegFcrhProjeto.objects.filter(pk=reg.pk).exists())

            for acao in (
                "SEMESTRAL_REGISTRO_CRIADO",
                "SEMESTRAL_REGISTRO_ATUALIZADO",
                "SEMESTRAL_REGISTRO_EXCLUIDO",
                "SEMESTRAL_SUBMETIDO",
            ):
                self.assertTrue(
                    AuditLog.objects.filter(
                        usuario=gestor_user,
                        acao=acao,
                        justificativa__contains="[Ajuste excepcional Master/Admin em ciclo ENVIADO]",
                    ).exists(),
                    f"Esperado AuditLog excepcional para {gestor_user.username} / {acao}",
                )

        # 4. Reabrir ciclo para ABERTO restaura edição para o PontoFocal
        self.client.force_login(self.master)
        self.client.post(cfg_url, self._payload_config_ciclo("ABERTO"))
        self.ciclo.refresh_from_db()
        self.assertEqual(self.ciclo.status, "ABERTO")

        self.client.force_login(self.focal_fcrh)
        get_reaberto = self.client.get(form_url)
        self.assertEqual(get_reaberto.status_code, 200)
        self.assertNotContains(get_reaberto, 'data-testid="banner-bloqueio-ciclo-focal"')
        self.assertContains(get_reaberto, 'data-testid="btn-salvar-registro"')

    def test_sla_via_views_e_download_xlsx_zip_csv(self):
        self.client.force_login(self.master)
        mail.outbox.clear()

        # Disparar alertas para 2026-01
        r_alerta = self.client.post(
            reverse("semestral:sla_disparar_alertas"),
            {"ano": 2026, "semestre": 1, "competencia": "2026-01"},
        )
        self.assertEqual(r_alerta.status_code, 302)
        self.comp_fcrh_jan.refresh_from_db()
        self.assertEqual(self.comp_fcrh_jan.status, "ALERTA_ENVIADO")
        self.assertEqual(len(mail.outbox), 5)

        # Verificar SLA simulando data após 05/02/2026
        mail.outbox.clear()
        r_its1 = self.client.post(
            reverse("semestral:sla_verificar_its1"),
            {"ano": 2026, "semestre": 1, "referencia_dt": "2026-02-10T12:00"},
        )
        self.assertEqual(r_its1.status_code, 302)
        self.comp_fcrh_jan.refresh_from_db()
        self.assertEqual(self.comp_fcrh_jan.status, "ATRASADO_ITS1_EMITIDA")
        self.assertTrue(
            LogNotificacaoSLA.objects.filter(
                competencia=self.comp_fcrh_jan,
                tipo_evento="COMUNICADO_COORDENACAO",
                codigo_ocorrencia="ITS1",
            ).exists()
        )

        # Focal submete após ITS1 -> REGULARIZADO + EM_ANALISE
        self.client.force_login(self.focal_fcrh)
        self.client.post(
            reverse("semestral:submeter_competencia", args=[self.comp_fcrh_jan.pk]),
            {"observacao_submissao": "Entrega regularizada."},
        )
        self.comp_fcrh_jan.refresh_from_db()
        self.assertEqual(self.comp_fcrh_jan.status, "REGULARIZADO")
        self.assertEqual(self.comp_fcrh_jan.status_aprovacao, "EM_ANALISE")

        # Download individual .xlsx + verificação OOXML lossless
        self.client.force_login(self.master)
        r_xlsx = self.client.get(
            reverse("semestral:exportar_xlsx", args=["AT"]),
            {"ano": 2026, "semestre": 1},
        )
        self.assertEqual(r_xlsx.status_code, 200)
        self.assertEqual(
            r_xlsx["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        validar_integridade_xlsx(TEMPLATE_MAP["AT"][0], r_xlsx.content)

        # Download pacote .zip com os 5 arquivos
        r_zip = self.client.get(
            reverse("semestral:exportar_pacote"),
            {"ano": 2026, "semestre": 1},
        )
        self.assertEqual(r_zip.status_code, 200)
        self.assertEqual(r_zip["Content-Type"], "application/zip")
        with ZipFile(BytesIO(r_zip.content), "r") as zf:
            self.assertEqual(len(zf.namelist()), 5)

        # Download CSV resumo
        r_csv = self.client.get(
            reverse("core:semestral_csv"),
            {"ano": 2026, "semestre": 1},
        )
        self.assertEqual(r_csv.status_code, 200)
        self.assertIn("FCRH;FCRH;01/2026", r_csv.content.decode("utf-8"))
