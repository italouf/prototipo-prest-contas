"""Testes de integridade, RBAC, idempotência e auditabilidade das 3 Fases de Integração.

Cobre:
- Fase 1: Lista única de projetos oficiais (FINANCEIRO_GERAL -> Semestral v3.1) + exportação lossless.
- Fase 2: Ponte assistida com 1 clique (Semestral aprovado -> Base Operacional) financeiro e físico,
  proteção contra dupla contagem (serviço + UniqueConstraint de banco), modo PROPOSTA e DIRETO,
  preservação de dados importados, compatibilidade com Conciliar base e trilha completa no AuditLog.
- Fase 3: Semáforo de coerência na Conciliação, Painel Semestral e Configuração de Ciclo,
  incluindo registro do resumo de coerência no AuditLog ao fechar/enviar ciclo.
"""
from datetime import date
from decimal import Decimal as D
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.accountability import services as ingestion
from apps.accountability.models import (
    Acompanhamento,
    KpiAcompanhamento,
    ProjetoFinanceiro,
    ResumoFinanceiro,
)
from apps.accountability.tests.fixtures_financeiro import FINANCEIRO
from apps.audit.models import AuditLog
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.entries import operational as op
from apps.entries.effective import estado as ler_estado_operacional, invalidar as invalidar_cache
from apps.entries.models import BaseOperacional, IndicadorOperacional, ProjetoFinanceiroFonte
from apps.periods.models import Periodo
from apps.pillars.models import Pilar, UsuarioPilar
from apps.planning.views import contexto_painel, contexto_pilar
from apps.projects.models import Projeto

from .integracao import (
    CARTEIRA_SEMESTRAL_NOME,
    aplicar_sugestao_operacional,
    aprovar_integracao_operacional,
    calcular_semaforo_coerencia,
    calcular_sugestoes_competencia,
    listar_projetos_oficiais_para_pilar,
    sincronizar_projeto_para_catalogo_oficial,
    validar_vinculo_projeto_oficial,
)
from .models import (
    CicloSemestral,
    CompetenciaMensalPilar,
    ConfiguracaoPilarSemestral,
    IntegracaoSemestralOperacional,
)
from .models_registros import (
    RegAcsEmpresa,
    RegAcsProjetoPdi,
    RegAfcctPedidoPi,
    RegAfcctProjetoPdi,
    RegAfcctPublicacao,
    RegAtAtividade,
    RegFcrhProfissional,
    RegFcrhProjeto,
    RegFinAssociadas,
    RegFinOutrasFontes,
)
from .registry import get_domain_choices, get_tab_spec
from .xlsx_exporter import (
    TEMPLATE_MAP,
    exportar_planilha_embrapii,
    validar_integridade_xlsx,
)

User = get_user_model()


def _primeira_opcao(categoria: str) -> str:
    choices = [c[0] for c in get_domain_choices(categoria, required=True) if c[0]]
    return choices[0] if choices else "Sim"


class IntegracaoSemestralBaseTestCase(TestCase):
    """Base comum com FINANCEIRO_GERAL + INDICADORES_PE + BaseOperacional + Ciclo Semestral 2026."""

    @classmethod
    def setUpTestData(cls):
        garantir_grupos()
        cls.pilares = {
            c: Pilar.objects.get_or_create(codigo=c, defaults={"nome": c, "ordem": idx})[0]
            for idx, c in enumerate(
                ("PDI", "FORMACAO", "STARTUPS", "INFRA", "AT", "OUTRASFONTES"), start=1
            )
        }
        cls.master = adicionar_grupo(
            User.objects.create_user(
                username="int_master", email="int_master@quiin.local", password="x"
            ),
            "Master",
        )
        cls.focal_pdi = adicionar_grupo(
            User.objects.create_user(
                username="int_focal_pdi", email="int_pdi@quiin.local", password="x"
            ),
            "PontoFocal",
        )
        UsuarioPilar.objects.create(usuario=cls.focal_pdi, pilar=cls.pilares["PDI"])

        cls.focal_fcrh = adicionar_grupo(
            User.objects.create_user(
                username="int_focal_fcrh", email="int_fcrh@quiin.local", password="x"
            ),
            "PontoFocal",
        )
        UsuarioPilar.objects.create(usuario=cls.focal_fcrh, pilar=cls.pilares["FORMACAO"])

        cls.auditor = adicionar_grupo(
            User.objects.create_user(
                username="int_auditor", email="int_auditor@quiin.local", password="x"
            ),
            "Auditor",
        )

        ingestion.ingestar("FINANCEIRO_GERAL", FINANCEIRO, "Integração QuIIN", "3T/2026", cls.master)
        ingestion.ingestar(
            "INDICADORES_PE",
            FINANCEIRO.with_name("Indicadores Gerais do Termo de Retificação do PE.xlsx"),
            "Integração QuIIN",
            "3T/2026",
            cls.master,
        )
        cls.acomp = Acompanhamento.objects.get(centro__nome="Integração QuIIN")
        cls.periodo_out = Periodo.objects.create(competencia=date(2026, 10, 1), status="ABERTO")
        cls.periodo_nov = Periodo.objects.create(competencia=date(2026, 11, 1), status="ABERTO")

        call_command("seed_semestral_v31", "--ano=2026")
        cls.ciclo_s2 = CicloSemestral.objects.get(ano=2026, semestre=2)
        cls.ciclo_s1 = CicloSemestral.objects.get(ano=2026, semestre=1)

    def confirmar_base(self, corte=date(2026, 9, 1)):
        base = op.confirmar_base(self.acomp, corte, self.master)
        invalidar_cache()
        return base

    def comp(self, pilar_cod: str, competencia: date = date(2026, 10, 1), ciclo=None) -> CompetenciaMensalPilar:
        ciclo_alvo = ciclo or (self.ciclo_s2 if competencia.month >= 7 else self.ciclo_s1)
        return CompetenciaMensalPilar.objects.get(
            ciclo=ciclo_alvo,
            configuracao_pilar__codigo=pilar_cod,
            competencia=competencia,
        )

    def aprovar_comp(self, comp: CompetenciaMensalPilar) -> CompetenciaMensalPilar:
        comp.status = "SUBMETIDO_NO_PRAZO"
        comp.status_aprovacao = "APROVADO"
        comp.revisado_por = self.master
        comp.save(update_fields=["status", "status_aprovacao", "revisado_por"])
        return comp

    # --- Helpers de criação de registros tipados ---

    def criar_outras_fontes(self, comp, valor: D, descricao: str = "Aporte externo"):
        return RegFinOutrasFontes.objects.create(
            competencia_mensal=comp,
            acao_relacionada="PDI",
            codigo_projeto_atividade="QIN-OF-01",
            tipo_despesa="Custeio",
            mes_ano_competencia=comp.competencia,
            entidade_aporte="Parceiro Externo",
            descricao=descricao,
            data_movimentacao=comp.competencia,
            valor=valor,
            criado_por=self.master,
        )

    def criar_associada(self, comp, contrib_ano1: D, contrib_ano2: D = D("0"), vigente: str = "Sim"):
        return RegFinAssociadas.objects.create(
            competencia_mensal=comp,
            razao_social="Quantum Partner SA",
            nome_fantasia="Quantum Partner",
            cnpj="12.345.678/0001-90",
            eh_startup="Não",
            data_inicio_associacao=comp.competencia,
            categoria_at="Ouro",
            associacao_vigente=vigente,
            contrib_ano1=contrib_ano1,
            contrib_ano2=contrib_ano2,
            nome_contato="Ana Silva",
            cargo_contato="Diretora",
            email_contato="ana@quantum.local",
            part_pdi="Sim",
            part_fcrh="Não",
            part_acs="Não",
            part_lic_pi="Não",
            doacao_infra="Não",
            criado_por=self.master,
        )

    def criar_atividade_at(self, comp, titulo: str, origem_valor: str, valor: D):
        return RegAtAtividade.objects.create(
            competencia_mensal=comp,
            titulo=titulo,
            associadas_participantes="Quantum Partner",
            objetivo="Engajamento tecnológico",
            descricao_publica="Atividade técnica AT",
            status_atual="Concluído",
            valor_executado=valor,
            origem_valor=origem_valor,
            data_inicio=comp.competencia,
            criado_por=self.master,
        )

    def criar_projeto_afcct(self, comp, titulo: str, projeto_oficial=None, criado_por=None):
        return RegAfcctProjetoPdi.objects.create(
            competencia_mensal=comp,
            projeto_oficial=projeto_oficial,
            titulo=titulo,
            resumo_projeto="Resumo executivo do projeto PD&I",
            descricao_publica="Descrição pública PD&I",
            envolvimento_empresas_at="Não",
            trl_inicial="TRL 2",
            trl_final="TRL 4",
            status_atual="Em andamento",
            resultados_executados="Protótipo validado",
            valor_total_planejado=D("250000.00"),
            data_inicio=date(2026, 10, 1),
            data_prevista_termino=date(2027, 6, 30),
            cooperacao_nacional_internacional="Não",
            criado_por=criado_por or self.master,
        )

    def criar_projeto_fcrh(self, comp, titulo: str, qtd_concluiram: int = 12, projeto_oficial=None):
        return RegFcrhProjeto.objects.create(
            competencia_mensal=comp,
            projeto_oficial=projeto_oficial,
            titulo=titulo,
            objetivo="Capacitar profissionais em quântica",
            descricao_publica="Curso de formação",
            ementa_detalhada="Módulo 1 e 2",
            carga_horaria_total=D("40.0"),
            publico_alvo="Engenheiros e pesquisadores",
            status_atual="Em andamento",
            valor_total_planejado=D("80000.00"),
            data_inicio=date(2026, 10, 1),
            qtd_iniciaram=max(qtd_concluiram, 15),
            qtd_concluiram=qtd_concluiram,
            tipo_formacao="Curso de extensão",
            onde_realizada="SENAI CIMATEC",
            vinculo_linhas_tematicas="Computação Quântica",
            criado_por=self.master,
        )

    def criar_projeto_acs(self, comp, titulo: str, projeto_oficial=None):
        return RegAcsProjetoPdi.objects.create(
            competencia_mensal=comp,
            projeto_oficial=projeto_oficial,
            titulo=titulo,
            ambiente_inovacao_aberta="Sim",
            forma_cooperada="Sim",
            objetivo="Desenvolvimento com startup",
            descricao_publica="Projeto ACS",
            trl_inicial="TRL 3",
            trl_final="TRL 5",
            status_atual="Em andamento",
            valor_total_planejado=D("120000.00"),
            data_inicio=date(2026, 10, 1),
            criado_por=self.master,
        )


# ---------------------------------------------------------------------------
# FASE 1 — LISTA ÚNICA DE PROJETOS (FINANCEIRO_GERAL -> SEMESTRAL)
# ---------------------------------------------------------------------------


class Fase1ListaUnicaProjetosTestes(IntegracaoSemestralBaseTestCase):
    def test_catalogo_oficial_enriquece_projetos_com_metadados_do_financeiro(self):
        itens_pdi = listar_projetos_oficiais_para_pilar("PDI", acompanhamento=self.acomp)
        self.assertGreater(len(itens_pdi), 0)
        primeiro = itens_pdi[0]
        self.assertTrue(primeiro["id"])
        self.assertTrue(primeiro["nome"])
        self.assertIn("rotulo", primeiro)

        pf = ProjetoFinanceiro.objects.filter(
            acompanhamento=self.acomp, projeto_id=primeiro["id"]
        ).first()
        self.assertIsNotNone(pf)
        if pf.orcado is not None:
            self.assertEqual(primeiro["valor_orcado"], f"{pf.orcado:.2f}")

    def test_salvar_registros_vinculados_persiste_fk_renderiza_badge_e_audita(self):
        self.client.force_login(self.master)
        proj_pdi = Projeto.objects.filter(pilar__codigo="PDI", ativo=True).first()
        proj_form = Projeto.objects.filter(pilar__codigo="FORMACAO", ativo=True).first()
        proj_start = Projeto.objects.filter(pilar__codigo="STARTUPS", ativo=True).first()
        self.assertIsNotNone(proj_pdi)
        self.assertIsNotNone(proj_form)
        self.assertIsNotNone(proj_start)

        # 1) AFCCT -> PDI via HTTP POST completo com valores válidos dos domínios EMBRAPII
        spec_afcct = get_tab_spec("AFCCT", "afcct-2")
        comp_afcct = self.comp("AFCCT")
        url_afcct = reverse("semestral:competencia_form", args=[comp_afcct.pk]) + "?aba=afcct-2"
        payload_afcct = {
            "action": "save_record",
            "aba": "afcct-2",
            "projeto_oficial": str(proj_pdi.pk),
            "titulo": proj_pdi.nome,
            "resumo_projeto": "Resumo do projeto oficial vinculado",
            "descricao_publica": "Descrição pública",
            "envolvimento_empresas_at": _primeira_opcao(spec_afcct.dropdowns["envolvimento_empresas_at"]),
            "trl_inicial": _primeira_opcao(spec_afcct.dropdowns["trl_inicial"]),
            "trl_final": _primeira_opcao(spec_afcct.dropdowns["trl_final"]),
            "status_atual": _primeira_opcao(spec_afcct.dropdowns["status_atual"]),
            "resultados_executados": "Marco inicial concluído",
            "valor_total_planejado": "150000.00",
            "qtd_pis_geradas": "0",
            "qtd_publicacoes_geradas": "0",
            "data_inicio": "2026-10-01",
            "data_prevista_termino": "2027-06-30",
            "cooperacao_nacional_internacional": _primeira_opcao(
                spec_afcct.dropdowns["cooperacao_nacional_internacional"]
            ),
        }
        resp = self.client.post(url_afcct, payload_afcct)
        self.assertEqual(resp.status_code, 302)
        reg_afcct = RegAfcctProjetoPdi.objects.get(competencia_mensal=comp_afcct)
        self.assertEqual(reg_afcct.projeto_oficial_id, proj_pdi.pk)

        # Verifica badge visual na listagem
        page = self.client.get(url_afcct)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Portfólio oficial")

        # Verifica AuditLog contendo referência ao projeto oficial
        log_afcct = AuditLog.objects.filter(
            acao="SEMESTRAL_REGISTRO_CRIADO",
            entidade="RegAfcctProjetoPdi",
            registro_id=str(reg_afcct.pk),
        ).first()
        self.assertIsNotNone(log_afcct)
        self.assertIn("Portfólio oficial:", log_afcct.justificativa)
        self.assertIn(str(proj_pdi.pk), log_afcct.justificativa)

        # 2) FCRH -> FORMACAO
        spec_fcrh = get_tab_spec("FCRH", "fcrh-2")
        comp_fcrh = self.comp("FCRH")
        payload_fcrh = {
            "action": "save_record",
            "aba": "fcrh-2",
            "projeto_oficial": str(proj_form.pk),
            "titulo": proj_form.nome,
            "objetivo": "Formação em tecnologias quânticas",
            "descricao_publica": "Descrição pública do curso",
            "ementa_detalhada": "Ementa completa",
            "carga_horaria_total": "40.0",
            "publico_alvo": "Profissionais de P&D",
            "status_atual": _primeira_opcao(spec_fcrh.dropdowns["status_atual"]),
            "valor_total_planejado": "75000.00",
            "data_inicio": "2026-10-01",
            "qtd_iniciaram": "20",
            "qtd_concluiram": "15",
            "tipo_formacao": _primeira_opcao(spec_fcrh.dropdowns["tipo_formacao"]),
            "onde_realizada": _primeira_opcao(spec_fcrh.dropdowns["onde_realizada"]),
            "vinculo_linhas_tematicas": "Computação Quântica",
            "qtd_empresas_at": "2",
        }
        resp_fcrh = self.client.post(
            reverse("semestral:competencia_form", args=[comp_fcrh.pk]) + "?aba=fcrh-2",
            payload_fcrh,
        )
        self.assertEqual(resp_fcrh.status_code, 302)
        self.assertEqual(
            RegFcrhProjeto.objects.get(competencia_mensal=comp_fcrh).projeto_oficial_id,
            proj_form.pk,
        )

        # 3) ACS -> STARTUPS
        spec_acs = get_tab_spec("ACS", "acs-2")
        comp_acs = self.comp("ACS")
        payload_acs = {
            "action": "save_record",
            "aba": "acs-2",
            "projeto_oficial": str(proj_start.pk),
            "titulo": proj_start.nome,
            "ambiente_inovacao_aberta": _primeira_opcao(spec_acs.dropdowns["ambiente_inovacao_aberta"]),
            "forma_cooperada": _primeira_opcao(spec_acs.dropdowns["forma_cooperada"]),
            "objetivo": "Projeto cooperado com startup",
            "descricao_publica": "Descrição pública ACS",
            "trl_inicial": _primeira_opcao(spec_acs.dropdowns["trl_inicial"]),
            "trl_final": _primeira_opcao(spec_acs.dropdowns["trl_final"]),
            "status_atual": _primeira_opcao(spec_acs.dropdowns["status_atual"]),
            "valor_total_planejado": "120000.00",
            "qtd_pis_geradas": "0",
            "qtd_publicacoes_geradas": "0",
            "data_inicio": "2026-10-01",
            "qtd_empresas_base_tec": "1",
        }
        resp_acs = self.client.post(
            reverse("semestral:competencia_form", args=[comp_acs.pk]) + "?aba=acs-2",
            payload_acs,
        )
        self.assertEqual(resp_acs.status_code, 302)
        self.assertEqual(
            RegAcsProjetoPdi.objects.get(competencia_mensal=comp_acs).projeto_oficial_id,
            proj_start.pk,
        )

    def test_integridade_rejeita_vinculo_de_pilar_incompativel_ou_projeto_inativo(self):
        proj_start = Projeto.objects.filter(pilar__codigo="STARTUPS", ativo=True).first()
        proj_inativo = Projeto.objects.create(
            centro=self.acomp.centro,
            pilar=self.pilares["PDI"],
            nome="Projeto PDI Inativo",
            ativo=False,
        )
        spec_afcct = get_tab_spec("AFCCT", "afcct-2")

        with self.assertRaises(ValidationError):
            validar_vinculo_projeto_oficial(spec_afcct, proj_start)

        with self.assertRaises(ValidationError):
            validar_vinculo_projeto_oficial(spec_afcct, proj_inativo)

        # Também rejeita via HTTP POST (queryset restrito + clean_projeto_oficial)
        self.client.force_login(self.master)
        comp_afcct = self.comp("AFCCT")
        resp = self.client.post(
            reverse("semestral:competencia_form", args=[comp_afcct.pk]) + "?aba=afcct-2",
            {
                "action": "save_record",
                "aba": "afcct-2",
                "projeto_oficial": str(proj_start.pk),
                "titulo": "Tentativa cruzada",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(RegAfcctProjetoPdi.objects.filter(competencia_mensal=comp_afcct).count(), 0)

    def test_exportacao_xlsx_lossless_permanece_integra_com_projeto_oficial_vinculado(self):
        proj_pdi = Projeto.objects.filter(pilar__codigo="PDI", ativo=True).first()
        proj_form = Projeto.objects.filter(pilar__codigo="FORMACAO", ativo=True).first()
        proj_start = Projeto.objects.filter(pilar__codigo="STARTUPS", ativo=True).first()

        self.criar_projeto_afcct(self.comp("AFCCT"), proj_pdi.nome, projeto_oficial=proj_pdi)
        self.criar_projeto_fcrh(self.comp("FCRH"), proj_form.nome, projeto_oficial=proj_form)
        self.criar_projeto_acs(self.comp("ACS"), proj_start.nome, projeto_oficial=proj_start)

        for arquivo_codigo in ("AFCCT", "FCRH", "ACS"):
            _nome_arquivo, dados_xlsx = exportar_planilha_embrapii(self.ciclo_s2, arquivo_codigo)
            template_path, _pattern = TEMPLATE_MAP[arquivo_codigo]
            relatorio = validar_integridade_xlsx(template_path, dados_xlsx)
            self.assertGreater(relatorio["sheets_checked"], 0)
            self.assertGreater(relatorio["formulas_preserved"], 0)


# ---------------------------------------------------------------------------
# FASE 2 — PONTE ASSISTIDA COM 1 CLIQUE (SEMESTRAL APROVADO -> BASE OPERACIONAL)
# ---------------------------------------------------------------------------


class Fase2PonteAssistidaOperacionalTestes(IntegracaoSemestralBaseTestCase):
    def test_ponte_financeira_proposta_aprovar_atualiza_dashboards_sem_mutar_importado(self):
        self.confirmar_base()
        resumo_of_antes = ResumoFinanceiro.objects.get(
            acompanhamento=self.acomp, origem="TAB. 9", pilar__codigo="OUTRASFONTES", ano__isnull=True
        ).realizado
        resumo_at_cap_antes = ResumoFinanceiro.objects.get(
            acompanhamento=self.acomp, origem="TAB. 9", pilar__codigo="AT", ano__isnull=True
        ).captado
        resumo_at_real_antes = ResumoFinanceiro.objects.get(
            acompanhamento=self.acomp, origem="TAB. 9", pilar__codigo="AT", ano__isnull=True
        ).realizado

        # Lança e aprova FIN_QUIIN (Aba 10 Outras Fontes + Aba 13 Associadas) e AT (Aba 2)
        comp_fin = self.aprovar_comp(self.comp("FIN_QUIIN"))
        self.criar_outras_fontes(comp_fin, D("45000.50"))
        self.criar_associada(comp_fin, contrib_ano1=D("80000.00"), contrib_ano2=D("20000.00"), vigente="Sim")

        comp_at = self.aprovar_comp(self.comp("AT"))
        self.criar_atividade_at(comp_at, "Workshop AT Quântica", "Recurso AT", D("30000.00"))
        self.criar_atividade_at(comp_at, "Evento com Outra Fonte", "Outra Fonte", D("12000.00"))

        # Verifica sugestões determinísticas
        pacote_fin = calcular_sugestoes_competencia(comp_fin, acompanhamento=self.acomp)
        tipos_fin = {s["tipo_alvo"]: s for s in pacote_fin["sugestoes"]}
        self.assertIn("OUTRASFONTES_REALIZADO", tipos_fin)
        self.assertIn("AT_CAPTADO", tipos_fin)
        self.assertIn("KPI_PE-03", tipos_fin)
        self.assertEqual(tipos_fin["OUTRASFONTES_REALIZADO"]["incremento"], D("45000.50"))
        self.assertEqual(tipos_fin["AT_CAPTADO"]["incremento"], D("100000.00"))

        estado_antes = ler_estado_operacional(self.acomp)
        of_antes = estado_antes.total("OUTRASFONTES", "realizado")
        at_cap_antes = estado_antes.total("AT", "captado")
        at_real_antes = estado_antes.total("AT", "realizado")
        painel_at_antes = contexto_pilar(
            self.pilares["AT"], "todos", "fin", self.master, self.acomp
        )["painel_pilar"]["executado"]

        # Aplica em modo PROPOSTA: não deve alterar dashboards antes da aprovação
        integ_of = aplicar_sugestao_operacional(
            comp_fin, "OUTRASFONTES_REALIZADO", self.master, modo="PROPOSTA", acompanhamento=self.acomp
        )
        self.assertEqual(integ_of.status_execucao, "APLICADA")
        self.assertEqual(integ_of.lancamento_operacional.status, "ENVIADO")
        self.assertEqual(integ_of.lancamento_operacional.origem, "Integração Semestral")
        self.assertEqual(ler_estado_operacional(self.acomp).total("OUTRASFONTES", "realizado"), of_antes)

        # Aprova no fluxo oficial op.aprovar -> atualiza Estado e Dashboards
        op.aprovar(integ_of.lancamento_operacional, self.master)
        invalidar_cache()
        self.assertEqual(
            ler_estado_operacional(self.acomp).total("OUTRASFONTES", "realizado"),
            of_antes + D("45000.50"),
        )

        # Aplica AT_CAPTADO, AT_REALIZADO e OUTRASFONTES_REALIZADO_AT em modo DIRETO -> publica imediatamente
        integ_at_cap = aplicar_sugestao_operacional(
            comp_fin, "AT_CAPTADO", self.master, modo="DIRETO", acompanhamento=self.acomp
        )
        integ_at_real = aplicar_sugestao_operacional(
            comp_at, "AT_REALIZADO", self.master, modo="DIRETO", acompanhamento=self.acomp
        )
        integ_of_at = aplicar_sugestao_operacional(
            comp_at, "OUTRASFONTES_REALIZADO_AT", self.master, modo="DIRETO", acompanhamento=self.acomp
        )
        self.assertEqual(integ_at_cap.lancamento_operacional.status, "APROVADO")
        self.assertEqual(integ_at_cap.lancamento_operacional.origem, "Integração Semestral (Direto)")
        self.assertEqual(integ_at_real.lancamento_operacional.status, "APROVADO")
        self.assertEqual(integ_of_at.lancamento_operacional.status, "APROVADO")

        invalidar_cache()
        estado_depois = ler_estado_operacional(self.acomp)
        self.assertEqual(
            estado_depois.total("OUTRASFONTES", "realizado"),
            of_antes + D("45000.50") + D("12000.00"),
        )
        self.assertEqual(estado_depois.total("AT", "captado"), at_cap_antes + D("100000.00"))
        self.assertEqual(estado_depois.total("AT", "realizado"), at_real_antes + D("30000.00"))

        # Dashboard combinado de Captação (AT + Outras Fontes) soma exatamente os 3 incrementos de realizado
        painel_at = contexto_pilar(self.pilares["AT"], "todos", "fin", self.master, self.acomp)["painel_pilar"]
        self.assertEqual(
            painel_at["executado"],
            painel_at_antes + D("45000.50") + D("12000.00") + D("30000.00"),
        )
        painel_geral = contexto_painel("todos", "fin", self.master, self.acomp)["painel"]
        self.assertIsNotNone(painel_geral)

        # Integridade não-destrutiva: ResumoFinanceiro importado da planilha continua intacto
        self.assertEqual(
            ResumoFinanceiro.objects.get(
                acompanhamento=self.acomp, origem="TAB. 9", pilar__codigo="OUTRASFONTES", ano__isnull=True
            ).realizado,
            resumo_of_antes,
        )
        self.assertEqual(
            ResumoFinanceiro.objects.get(
                acompanhamento=self.acomp, origem="TAB. 9", pilar__codigo="AT", ano__isnull=True
            ).captado,
            resumo_at_cap_antes,
        )
        self.assertEqual(
            ResumoFinanceiro.objects.get(
                acompanhamento=self.acomp, origem="TAB. 9", pilar__codigo="AT", ano__isnull=True
            ).realizado,
            resumo_at_real_antes,
        )

        # Carteira de consolidação sobrevive à reconciliação de base
        self.assertTrue(
            ProjetoFinanceiroFonte.objects.filter(
                centro=self.acomp.centro,
                pilar=self.pilares["OUTRASFONTES"],
                nome=CARTEIRA_SEMESTRAL_NOME,
                ativo=True,
            ).exists()
        )
        op.confirmar_base(self.acomp, date(2026, 9, 1), self.master, "Conciliação pós-ponte", reconciliar=True)
        invalidar_cache()
        self.assertEqual(
            ler_estado_operacional(self.acomp).total("OUTRASFONTES", "realizado"),
            of_antes + D("45000.50") + D("12000.00"),
        )

    def test_ponte_fisica_atualiza_kpis_e_dashboard_fisico_sem_mutar_kpi_importado(self):
        self.confirmar_base()
        kpi_pe01_importado = KpiAcompanhamento.objects.get(acompanhamento=self.acomp, codigo="PE-01").acumulado
        kpi_pe07_importado = KpiAcompanhamento.objects.get(acompanhamento=self.acomp, codigo="PE-07").acumulado

        # AFCCT -> PE-01 (2), PE-08 (1), PE-09 (1)
        comp_afcct = self.aprovar_comp(self.comp("AFCCT"))
        for i in range(2):
            self.criar_projeto_afcct(comp_afcct, f"Projeto Quântico {i}")
        RegAfcctPedidoPi.objects.create(
            competencia_mensal=comp_afcct,
            titulo_pi="Patente Qubit",
            codigo_projeto="QIN-AFCCT-2026-10-1-1",
            tipo_pi="Patente de Invenção",
            data_pedido=date(2026, 10, 15),
            numero_pedido_inpi="BR10202600001",
            criado_por=self.master,
        )
        RegAfcctPublicacao.objects.create(
            competencia_mensal=comp_afcct,
            titulo_publicacao="Artigo Nature Q",
            codigo_projeto="QIN-AFCCT-2026-10-1-1",
            data_publicacao_aceite=date(2026, 10, 20),
            titulo_periodico="Nature Quantum",
            classificacao_periodico="A1",
            autores="Pesquisador QuIIN",
            criado_por=self.master,
        )

        # FCRH -> PE-07 = max(soma_concl=14, qtd_prof=2) = 14
        comp_fcrh = self.aprovar_comp(self.comp("FCRH"))
        self.criar_projeto_fcrh(comp_fcrh, "Turma Quântica", qtd_concluiram=14)
        for i in range(2):
            RegFcrhProfissional.objects.create(
                competencia_mensal=comp_fcrh,
                nome_completo=f"Profissional {i}",
                cpf=f"000.000.000-0{i}",
                email=f"prof{i}@quiin.local",
                codigo_projeto="QIN-FCRH-2026-10-1-1",
                vinculo_profissional="Pesquisador",
                certificado_emitido="Sim",
                criado_por=self.master,
            )

        # ACS -> PE-05 (1 EBT) e PE-06 (1 projeto)
        comp_acs = self.aprovar_comp(self.comp("ACS"))
        RegAcsEmpresa.objects.create(
            competencia_mensal=comp_acs,
            razao_social="QStart Tecnologia Ltda",
            nome_fantasia="QStart",
            codigo_projeto="QIN-PJACS-2026-10-1-1",
            cnpj="99.888.777/0001-66",
            eh_ebt_ou_startup="Sim",
            startup_atraida_criada="Atraída",
            nome_contato="Carlos",
            cargo="CEO",
            telefone="71999990000",
            email="carlos@qstart.local",
            houve_alavancagem="Não",
            criado_por=self.master,
        )
        self.criar_projeto_acs(comp_acs, "Projeto Open Innovation")

        estado_pre = ler_estado_operacional(self.acomp)
        pe01_antes = estado_pre.valor("kpi:PE-01") or D("0")
        pe08_antes = estado_pre.valor("kpi:PE-08") or D("0")
        pe09_antes = estado_pre.valor("kpi:PE-09") or D("0")
        pe07_antes = estado_pre.valor("kpi:PE-07") or D("0")
        pe05_antes = estado_pre.valor("kpi:PE-05") or D("0")
        pe06_antes = estado_pre.valor("kpi:PE-06") or D("0")
        pdi_fis_antes = contexto_pilar(self.pilares["PDI"], "todos", "fis", self.master, self.acomp)["painel_pilar"]["executado"]

        aplicar_sugestao_operacional(comp_afcct, "KPI_PE-01", self.master, modo="DIRETO", acompanhamento=self.acomp)
        aplicar_sugestao_operacional(comp_afcct, "KPI_PE-08", self.master, modo="DIRETO", acompanhamento=self.acomp)
        aplicar_sugestao_operacional(comp_afcct, "KPI_PE-09", self.master, modo="DIRETO", acompanhamento=self.acomp)
        aplicar_sugestao_operacional(comp_fcrh, "KPI_PE-07", self.master, modo="DIRETO", acompanhamento=self.acomp)
        aplicar_sugestao_operacional(comp_acs, "KPI_PE-05", self.master, modo="DIRETO", acompanhamento=self.acomp)
        aplicar_sugestao_operacional(comp_acs, "KPI_PE-06", self.master, modo="DIRETO", acompanhamento=self.acomp)

        invalidar_cache()
        estado_pos = ler_estado_operacional(self.acomp)
        self.assertEqual(estado_pos.valor("kpi:PE-01"), pe01_antes + 2)
        self.assertEqual(estado_pos.valor("kpi:PE-08"), pe08_antes + 1)
        self.assertEqual(estado_pos.valor("kpi:PE-09"), pe09_antes + 1)
        self.assertEqual(estado_pos.valor("kpi:PE-07"), pe07_antes + 14)
        self.assertEqual(estado_pos.valor("kpi:PE-05"), pe05_antes + 1)
        self.assertEqual(estado_pos.valor("kpi:PE-06"), pe06_antes + 1)

        # Dashboards físicos refletem os novos acumulados homologados
        painel_pdi_fis = contexto_pilar(self.pilares["PDI"], "todos", "fis", self.master, self.acomp)["painel_pilar"]
        self.assertGreater(painel_pdi_fis["executado"], pdi_fis_antes)
        painel_fcrh_fis = contexto_pilar(self.pilares["FORMACAO"], "todos", "fis", self.master, self.acomp)["painel_pilar"]
        self.assertEqual(painel_fcrh_fis["executado"], pe07_antes + 14)
        painel_acs_fis = contexto_pilar(self.pilares["STARTUPS"], "todos", "fis", self.master, self.acomp)["painel_pilar"]
        self.assertGreater(painel_acs_fis["executado"], pe05_antes + pe06_antes)

        # KpiAcompanhamento importado continua intacto
        self.assertEqual(
            KpiAcompanhamento.objects.get(acompanhamento=self.acomp, codigo="PE-01").acumulado,
            kpi_pe01_importado,
        )
        self.assertEqual(
            KpiAcompanhamento.objects.get(acompanhamento=self.acomp, codigo="PE-07").acumulado,
            kpi_pe07_importado,
        )

    def test_idempotencia_anti_dupla_contagem_constraint_banco_e_reaplicacao_auditada(self):
        self.confirmar_base()
        comp_afcct = self.aprovar_comp(self.comp("AFCCT"))
        self.criar_projeto_afcct(comp_afcct, "Projeto Único")
        pe01_antes = ler_estado_operacional(self.acomp).valor("kpi:PE-01")

        # 1ª aplicação: sucesso
        integ1 = aplicar_sugestao_operacional(
            comp_afcct, "KPI_PE-01", self.master, modo="DIRETO", acompanhamento=self.acomp
        )
        self.assertEqual(ler_estado_operacional(self.acomp).valor("kpi:PE-01"), pe01_antes + 1)

        # 2ª tentativa sem reaplicar=True: bloqueada pelo serviço
        with self.assertRaises(ValidationError):
            aplicar_sugestao_operacional(
                comp_afcct, "KPI_PE-01", self.master, modo="DIRETO", acompanhamento=self.acomp
            )
        self.assertEqual(ler_estado_operacional(self.acomp).valor("kpi:PE-01"), pe01_antes + 1)

        # Proteção adicional no nível de banco (UniqueConstraint parcial)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                IntegracaoSemestralOperacional.objects.create(
                    competencia_mensal=comp_afcct,
                    acompanhamento=self.acomp,
                    indicador_operacional=integ1.indicador_operacional,
                    lancamento_operacional=integ1.lancamento_operacional,
                    tipo_alvo="KPI_PE-01",
                    incremento_calculado=D("1"),
                    valor_vigente_anterior=pe01_antes,
                    valor_proposto=pe01_antes + 1,
                    modo="DIRETO",
                    status_execucao="APLICADA",
                    executado_por=self.master,
                )

        # Reaplicação explícita (ex.: gestor ajusta manualmente para pe01_antes + 3)
        integ2 = aplicar_sugestao_operacional(
            comp_afcct,
            "KPI_PE-01",
            self.master,
            valor_alvo_final=str(int(pe01_antes + 3)),
            modo="DIRETO",
            justificativa="Retificação de contagem",
            acompanhamento=self.acomp,
            reaplicar=True,
        )
        integ1.refresh_from_db()
        self.assertEqual(integ1.status_execucao, "SUPERADA")
        self.assertEqual(integ2.status_execucao, "APLICADA")
        self.assertEqual(integ2.lancamento_operacional.versao, 2)
        self.assertEqual(ler_estado_operacional(self.acomp).valor("kpi:PE-01"), pe01_antes + 3)

        # Trilha de auditoria registra a substituição
        log2 = AuditLog.objects.filter(
            acao="SEMESTRAL_INTEGRAR_BASE_OPERACIONAL",
            entidade="IntegracaoSemestralOperacional",
            registro_id=str(integ2.pk),
        ).first()
        self.assertIsNotNone(log2)
        self.assertIn(f"Substitui integração anterior #{integ1.pk}", log2.justificativa)

    def test_guardrails_status_rbac_corte_periodo_fechado_e_saldo_negativo(self):
        self.confirmar_base(corte=date(2026, 9, 1))
        comp_fin = self.comp("FIN_QUIIN", date(2026, 10, 1))
        self.criar_outras_fontes(comp_fin, D("5000.00"), descricao="Guardrail")

        # 1) Rejeita se competência não estiver APROVADA (NAO_ENVIADO, EM_ANALISE, DEVOLVIDO)
        for status_invalido in ("NAO_ENVIADO", "EM_ANALISE", "DEVOLVIDO"):
            comp_fin.status_aprovacao = status_invalido
            comp_fin.save(update_fields=["status_aprovacao"])
            with self.assertRaises(ValidationError):
                aplicar_sugestao_operacional(
                    comp_fin, "OUTRASFONTES_REALIZADO", self.master, acompanhamento=self.acomp
                )

        # Aprova para testar demais guardrails
        self.aprovar_comp(comp_fin)

        # 2) RBAC: PontoFocal e Auditor recebem PermissionDenied e HTTP 403
        for nao_gestor in (self.focal_pdi, self.auditor):
            with self.assertRaises(PermissionDenied):
                aplicar_sugestao_operacional(
                    comp_fin, "OUTRASFONTES_REALIZADO", nao_gestor, acompanhamento=self.acomp
                )
            self.client.force_login(nao_gestor)
            resp = self.client.post(
                reverse("semestral:integrar_operacional", args=[comp_fin.pk]),
                {"tipo_alvo": "OUTRASFONTES_REALIZADO", "modo": "PROPOSTA"},
            )
            self.assertEqual(resp.status_code, 403)

        # 3) Competência anterior ao corte da Base Operacional (08/2026 < 09/2026)
        comp_antiga = self.aprovar_comp(self.comp("FIN_QUIIN", date(2026, 8, 1)))
        self.criar_outras_fontes(comp_antiga, D("1000.00"), descricao="Antiga")
        with self.assertRaises(ValidationError):
            aplicar_sugestao_operacional(
                comp_antiga, "OUTRASFONTES_REALIZADO", self.master, acompanhamento=self.acomp
            )

        # 4) Valor alvo inferior ao saldo histórico (geraria saldo negativo na carteira)
        of_base = ler_estado_operacional(self.acomp).total("OUTRASFONTES", "realizado")
        if of_base > D("100"):
            with self.assertRaises(ValidationError):
                aplicar_sugestao_operacional(
                    comp_fin,
                    "OUTRASFONTES_REALIZADO",
                    self.master,
                    valor_alvo_final=f"{(of_base - D('100')):.2f}",
                    modo="DIRETO",
                    acompanhamento=self.acomp,
                )

        # 5) Período mensal FECHADO bloqueia integração
        self.periodo_out.status = "FECHADO"
        self.periodo_out.save(update_fields=["status"])
        with self.assertRaises(ValidationError):
            aplicar_sugestao_operacional(
                comp_fin, "OUTRASFONTES_REALIZADO", self.master, acompanhamento=self.acomp
            )

    def test_fluxo_http_ponte_operacional_atalho_no_board_e_trilha_completa_auditlog(self):
        self.confirmar_base()
        comp_fin = self.aprovar_comp(self.comp("FIN_QUIIN", date(2026, 10, 1)))
        self.criar_outras_fontes(comp_fin, D("25000.00"), descricao="HTTP test")

        # Painel de aprovação exibe atalho da ponte com contagem pendente
        self.client.force_login(self.master)
        resp_board = self.client.get(
            reverse("entries:aprovacao", args=[self.periodo_out.pk]) + "?semestral_escopo=todos"
        )
        self.assertEqual(resp_board.status_code, 200)
        self.assertContains(resp_board, f'data-testid="btn-ponte-operacional-{comp_fin.pk}"')
        self.assertContains(resp_board, "Atualizar Dashboards (1)")

        # Página da competência exibe bloco #ponte-operacional para Master
        resp_form = self.client.get(reverse("semestral:competencia_form", args=[comp_fin.pk]))
        self.assertEqual(resp_form.status_code, 200)
        self.assertContains(resp_form, 'id="ponte-operacional"')

        # PontoFocal não vê bloco #ponte-operacional na competência aprovada do seu pilar
        comp_pdi = self.aprovar_comp(self.comp("AFCCT", date(2026, 10, 1)))
        self.criar_projeto_afcct(comp_pdi, "Proj Visibilidade", criado_por=self.focal_pdi)
        self.client.force_login(self.focal_pdi)
        resp_focal = self.client.get(reverse("semestral:competencia_form", args=[comp_pdi.pk]))
        self.assertEqual(resp_focal.status_code, 200)
        self.assertNotContains(resp_focal, 'id="ponte-operacional"')

        # Executa integração via HTTP POST como Master em modo PROPOSTA e depois aprova
        self.client.force_login(self.master)
        of_antes = ler_estado_operacional(self.acomp).total("OUTRASFONTES", "realizado")
        resp_post = self.client.post(
            reverse("semestral:integrar_operacional", args=[comp_fin.pk]),
            {
                "tipo_alvo": "OUTRASFONTES_REALIZADO",
                "modo": "PROPOSTA",
                "valor_alvo_final": f"{(of_antes + D('25000.00')):.2f}",
                "justificativa": "Conciliado com extrato outubro",
            },
        )
        self.assertEqual(resp_post.status_code, 302)
        self.assertIn("#ponte-operacional", resp_post["Location"])

        integ = IntegracaoSemestralOperacional.objects.get(
            competencia_mensal=comp_fin, tipo_alvo="OUTRASFONTES_REALIZADO", status_execucao="APLICADA"
        )
        op.aprovar(integ.lancamento_operacional, self.master)

        # Verifica trilha completa de auditabilidade (criação carteira + envio + aprovação + integração)
        self.assertTrue(
            AuditLog.objects.filter(acao="CRIAR_PROJETO_FIN_FONTE", usuario=self.master).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(
                acao="ENVIAR_OPERACIONAL",
                registro_id=str(integ.lancamento_operacional_id),
                usuario=self.master,
            ).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(
                acao="APROVAR_OPERACIONAL",
                registro_id=str(integ.lancamento_operacional_id),
                usuario=self.master,
            ).exists()
        )
        log_integ = AuditLog.objects.filter(
            acao="SEMESTRAL_INTEGRAR_BASE_OPERACIONAL",
            entidade="IntegracaoSemestralOperacional",
            registro_id=str(integ.pk),
        ).first()
        self.assertIsNotNone(log_integ)
        self.assertEqual(log_integ.usuario_id, self.master.pk)
        self.assertEqual(log_integ.campo, "OUTRASFONTES_REALIZADO")
        self.assertEqual(log_integ.origem, "Integração Semestral")
        self.assertEqual(D(log_integ.valor_anterior), of_antes)
        self.assertEqual(D(log_integ.valor_novo), of_antes + D("25000.00"))
        self.assertIn(f"Competência #{comp_fin.pk}", log_integ.justificativa)
        self.assertIn(str(integ.lancamento_operacional_id), log_integ.justificativa)
        self.assertIn("Conciliado com extrato outubro", log_integ.justificativa)


# ---------------------------------------------------------------------------
# FASE 3 — SEMÁFORO DE COERÊNCIA NA CONCILIAÇÃO E FECHAMENTO DE CICLO
# ---------------------------------------------------------------------------


class Fase3SemaforoCoerenciaTestes(IntegracaoSemestralBaseTestCase):
    def test_semaforo_detecta_sem_dados_divergente_alinhado_vinculos_e_integracoes(self):
        self.confirmar_base()

        # Sem registros semestrais no ciclo: todas as 6 linhas devem estar SEM_DADOS
        sem_vazio = calcular_semaforo_coerencia(acompanhamento=self.acomp, ciclo=self.ciclo_s2)
        self.assertTrue(sem_vazio["disponivel"])
        self.assertEqual(len(sem_vazio["linhas"]), 6)
        self.assertEqual(sem_vazio["resumo"]["sem_dados"], 6)
        self.assertEqual(sem_vazio["resumo"]["alinhados"], 0)
        self.assertEqual(sem_vazio["resumo"]["divergentes"], 0)

        # Popula Outras Fontes exatamente igual ao saldo da Base Operacional -> ALINHADO
        base_of = ler_estado_operacional(self.acomp).total("OUTRASFONTES", "realizado")
        comp_fin = self.aprovar_comp(self.comp("FIN_QUIIN"))
        self.criar_outras_fontes(comp_fin, base_of, descricao="Alinhado com TAB. 9")
        # Popula AT Captado com valor diferente da Base -> DIVERGENTE
        self.criar_associada(comp_fin, contrib_ano1=D("12345.00"), vigente="Sim")
        # Vincula 1 projeto PDI oficial
        proj_pdi = Projeto.objects.filter(pilar__codigo="PDI", ativo=True).first()
        comp_afcct = self.aprovar_comp(self.comp("AFCCT"))
        self.criar_projeto_afcct(comp_afcct, proj_pdi.nome, projeto_oficial=proj_pdi)
        # Aplica 1 integração no ciclo
        aplicar_sugestao_operacional(
            comp_afcct, "KPI_PE-01", self.master, modo="DIRETO", acompanhamento=self.acomp
        )

        semaforo = calcular_semaforo_coerencia(acompanhamento=self.acomp, ciclo=self.ciclo_s2)
        por_cod = {item["codigo"]: item for item in semaforo["linhas"]}
        self.assertEqual(por_cod["OUTRASFONTES_REALIZADO"]["status"], "ALINHADO")
        self.assertEqual(por_cod["AT_CAPTADO"]["status"], "DIVERGENTE")
        self.assertEqual(semaforo["resumo"]["projetos_vinculados"], 1)
        self.assertEqual(semaforo["resumo"]["projetos_semestral_total"], 1)
        self.assertEqual(semaforo["resumo"]["integracoes_aplicadas"], 1)
        self.assertGreaterEqual(semaforo["resumo"]["alinhados"], 1)
        self.assertGreaterEqual(semaforo["resumo"]["divergentes"], 1)

    def test_semaforo_renderiza_em_conciliar_base_painel_e_configurar_e_respeita_rbac(self):
        self.confirmar_base()
        self.client.force_login(self.master)

        for url in [
            reverse("entries:configurar"),
            reverse("core:semestral") + "?ano=2026&semestre=2",
            reverse("semestral:configurar_ciclo") + "?ano=2026&semestre=2",
        ]:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, f"Falha ao abrir {url}")
            self.assertContains(resp, 'data-testid="semaforo-coerencia"')

        # PontoFocal não visualiza semáforo consolidado no Painel Semestral
        self.client.force_login(self.focal_pdi)
        resp_focal = self.client.get(reverse("core:semestral") + "?ano=2026&semestre=2")
        self.assertEqual(resp_focal.status_code, 200)
        self.assertNotContains(resp_focal, 'data-testid="semaforo-coerencia"')

    def test_fechar_ciclo_registra_resumo_coerencia_no_auditlog(self):
        self.confirmar_base()
        self.client.force_login(self.master)

        payload = {
            "ciclo-centro_competencia": self.ciclo_s2.centro_competencia,
            "ciclo-abreviacao_cc": self.ciclo_s2.abreviacao_cc,
            "ciclo-termo_cooperacao": self.ciclo_s2.termo_cooperacao,
            "ciclo-periodo_referencia_label": self.ciclo_s2.periodo_referencia_label,
            "ciclo-coordenacao_nome": self.ciclo_s2.coordenacao_nome,
            "ciclo-coordenacao_email": self.ciclo_s2.coordenacao_email,
            "ciclo-status": "CONSOLIDADO",
        }
        for cfg in ConfiguracaoPilarSemestral.objects.all():
            prefix = f"pilar_{cfg.codigo}"
            payload[f"{prefix}-responsavel"] = str(cfg.responsavel_id or "")
            payload[f"{prefix}-responsavel_nome"] = cfg.responsavel_nome
            payload[f"{prefix}-responsavel_email"] = cfg.responsavel_email
            payload[f"{prefix}-dia_limite_mensal"] = str(cfg.dia_limite_mensal)
            if cfg.ativo:
                payload[f"{prefix}-ativo"] = "on"

        resp = self.client.post(
            reverse("semestral:configurar_ciclo") + "?ano=2026&semestre=2",
            payload,
        )
        self.assertEqual(resp.status_code, 302)

        self.ciclo_s2.refresh_from_db()
        self.assertEqual(self.ciclo_s2.status, "CONSOLIDADO")

        log_cfg = AuditLog.objects.filter(
            acao="SEMESTRAL_CONFIG_ATUALIZADA",
            entidade="CicloSemestral",
            registro_id=str(self.ciclo_s2.pk),
        ).order_by("-data_hora").first()
        self.assertIsNotNone(log_cfg)
        self.assertIn("Semáforo de coerência no fechamento:", log_cfg.justificativa)
        self.assertIn("alinhado(s)", log_cfg.justificativa)
        self.assertIn("divergente(s)", log_cfg.justificativa)
        self.assertIn("integração(ões)", log_cfg.justificativa)


# ---------------------------------------------------------------------------
# FLUXO OPERACIONAL COMPLETO — APROVAÇÃO EM 1 CLIQUE, REAPLICAÇÃO SOBRE ENVIADO,
# SINCRONIZAÇÃO DE PROJETO NOVO AO PORTFÓLIO OFICIAL E REALIZADO FINANCEIRO
# ---------------------------------------------------------------------------


class FluxoAprovacao1CliqueEPortfolioFinanceiroTestes(IntegracaoSemestralBaseTestCase):
    def test_proposta_enviada_exibe_aviso_aguardando_e_aprovacao_em_1_clique_atualiza_dashboards(self):
        self.confirmar_base()
        pe01_antes = ler_estado_operacional(self.acomp).kpi("PE-01", None)
        pdi_fis_antes = contexto_pilar(self.pilares["PDI"], "todos", "fis", self.master, self.acomp)["painel_pilar"]["executado"]

        comp_afcct = self.aprovar_comp(self.comp("AFCCT"))
        self.criar_projeto_afcct(comp_afcct, "Novo Projeto Teste Aprovacao")

        integ = aplicar_sugestao_operacional(
            comp_afcct, "KPI_PE-01", self.master, modo="PROPOSTA", acompanhamento=self.acomp
        )
        self.assertEqual(integ.lancamento_operacional.status, "ENVIADO")

        # Enquanto ENVIADO, Dashboards Físicos ainda exibem o valor anterior
        invalidar_cache()
        self.assertEqual(ler_estado_operacional(self.acomp).kpi("PE-01", None), pe01_antes)

        # Tela da competência deixa explícito que está aguardando aprovação, sem decimal bruto, com botão 1-clique e link do período exato
        self.client.force_login(self.master)
        resp_pendente = self.client.get(reverse("semestral:competencia_form", args=[comp_afcct.pk]))
        self.assertEqual(resp_pendente.status_code, 200)
        self.assertContains(resp_pendente, 'data-testid="badge-aguardando-KPI_PE-01"')
        self.assertContains(resp_pendente, 'data-testid="btn-aprovar-integracao-KPI_PE-01"')
        self.assertContains(
            resp_pendente,
            reverse("entries:aprovacao", args=[integ.lancamento_operacional.periodo_id]),
        )
        self.assertContains(resp_pendente, f"{int(pe01_antes + 1)} projetos")
        self.assertNotContains(resp_pendente, f"{int(pe01_antes + 1)},000000")
        self.assertNotContains(resp_pendente, 'data-testid="badge-integrado-KPI_PE-01"')

        # RBAC: PontoFocal não pode aprovar proposta operacional
        self.client.force_login(self.focal_pdi)
        resp_negado = self.client.post(
            reverse("semestral:aprovar_integracao_operacional", args=[integ.pk])
        )
        self.assertEqual(resp_negado.status_code, 403)

        # Master aprova em 1 clique -> Dashboards Físicos (Visão Geral e PDI) atualizam imediatamente
        self.client.force_login(self.master)
        resp_aprov = self.client.post(
            reverse("semestral:aprovar_integracao_operacional", args=[integ.pk])
        )
        self.assertEqual(resp_aprov.status_code, 302)

        integ.refresh_from_db()
        integ.lancamento_operacional.refresh_from_db()
        self.assertEqual(integ.lancamento_operacional.status, "APROVADO")
        self.assertEqual(integ.lancamento_operacional.origem, "Integração Semestral (Aprovada)")

        invalidar_cache()
        self.assertEqual(ler_estado_operacional(self.acomp).kpi("PE-01", None), pe01_antes + 1)

        painel_pdi_fis = contexto_pilar(self.pilares["PDI"], "todos", "fis", self.master, self.acomp)["painel_pilar"]
        self.assertEqual(painel_pdi_fis["executado"], pdi_fis_antes + 1)

        # AuditLog registra a aprovação via ponte
        self.assertTrue(
            AuditLog.objects.filter(
                acao="SEMESTRAL_INTEGRACAO_APROVADA",
                entidade="IntegracaoSemestralOperacional",
                registro_id=str(integ.pk),
                usuario=self.master,
            ).exists()
        )

        # Agora a tela exibe badge verde "Publicado nos Dashboards" e remove o aviso âmbar
        resp_pub = self.client.get(reverse("semestral:competencia_form", args=[comp_afcct.pk]))
        self.assertEqual(resp_pub.status_code, 200)
        self.assertContains(resp_pub, 'data-testid="badge-integrado-KPI_PE-01"')
        self.assertNotContains(resp_pub, 'data-testid="badge-aguardando-KPI_PE-01"')

    def test_reaplicar_sobre_proposta_enviada_substitui_sem_erro_e_publica_dashboards(self):
        self.confirmar_base()
        pe01_antes = ler_estado_operacional(self.acomp).kpi("PE-01", None)

        comp_afcct = self.aprovar_comp(self.comp("AFCCT"))
        self.criar_projeto_afcct(comp_afcct, "Projeto Reaplicar Sobre Enviado")

        integ1 = aplicar_sugestao_operacional(
            comp_afcct, "KPI_PE-01", self.master, modo="PROPOSTA", acompanhamento=self.acomp
        )
        self.assertEqual(integ1.lancamento_operacional.status, "ENVIADO")

        # Reaplicar em modo DIRETO sobre proposta ainda ENVIADO deve devolver a anterior e publicar a nova sem ValidationError
        integ2 = aplicar_sugestao_operacional(
            comp_afcct,
            "KPI_PE-01",
            self.master,
            valor_alvo_final=str(int(pe01_antes + 2)),
            modo="DIRETO",
            justificativa="Correção com 2 projetos efetivos",
            acompanhamento=self.acomp,
            reaplicar=True,
        )
        integ1.refresh_from_db()
        self.assertEqual(integ1.status_execucao, "SUPERADA")
        self.assertEqual(integ2.status_execucao, "APLICADA")
        self.assertEqual(integ2.lancamento_operacional.status, "APROVADO")

        invalidar_cache()
        self.assertEqual(ler_estado_operacional(self.acomp).kpi("PE-01", None), pe01_antes + 2)
        self.assertTrue(AuditLog.objects.filter(acao="DEVOLVER_OPERACIONAL", usuario=self.master).exists())

    def test_sincronizar_projeto_novo_para_portfolio_oficial_e_lancar_realizado_financeiro(self):
        self.confirmar_base()
        pdi_real_antes = ler_estado_operacional(self.acomp).total("PDI", "realizado")
        pe01_antes = ler_estado_operacional(self.acomp).kpi("PE-01", None)
        resumo_pdi_antes = ResumoFinanceiro.objects.get(
            acompanhamento=self.acomp, origem="TAB. 1", pilar__codigo="PDI", ano__isnull=True
        ).realizado

        # Usuário cadastra um NOVO projeto (sem selecionar projeto_oficial) com Valor Planejado = R$ 50.000,00
        comp_afcct = self.aprovar_comp(self.comp("AFCCT"))
        reg = self.criar_projeto_afcct(
            comp_afcct,
            "Novo Projeto Teste 2",
            projeto_oficial=None,
        )
        reg.valor_total_planejado = D("50000.00")
        reg.save(update_fields=["valor_total_planejado"])
        # Também cria uma proposta PE-01 pendente ANTES de sincronizar, para garantir que o sync não invalida base.versao
        integ_pe01 = aplicar_sugestao_operacional(
            comp_afcct, "KPI_PE-01", self.master, modo="PROPOSTA", acompanhamento=self.acomp
        )

        # Página exibe o bloco de sincronização de novos projetos
        self.client.force_login(self.master)
        resp_antes = self.client.get(reverse("semestral:competencia_form", args=[comp_afcct.pk]))
        self.assertEqual(resp_antes.status_code, 200)
        self.assertContains(resp_antes, 'data-testid="bloco-projetos-sem-vinculo"')
        self.assertContains(resp_antes, f'data-testid="btn-sincronizar-projeto-{reg.pk}"')

        # RBAC: PontoFocal não pode sincronizar para o Portfólio Oficial
        self.client.force_login(self.focal_pdi)
        resp_forbidden = self.client.post(
            reverse("semestral:sincronizar_projeto_oficial", args=[comp_afcct.pk, "afcct-2", reg.pk])
        )
        self.assertEqual(resp_forbidden.status_code, 403)

        # Master sincroniza com 1 clique
        self.client.force_login(self.master)
        resp_sync = self.client.post(
            reverse("semestral:sincronizar_projeto_oficial", args=[comp_afcct.pk, "afcct-2", reg.pk])
        )
        self.assertEqual(resp_sync.status_code, 302)

        reg.refresh_from_db()
        self.assertIsNotNone(reg.projeto_oficial)
        proj = reg.projeto_oficial
        self.assertEqual(proj.nome, "Novo Projeto Teste 2")
        self.assertEqual(proj.pilar.codigo, "PDI")
        self.assertTrue(proj.ativo)

        # ProjetoFinanceiro criado em TAB. 2 com Orçado = 50.000,00 e Realizado inicial = 0,00 (Orçado != Realizado!)
        pf = ProjetoFinanceiro.objects.get(acompanhamento=self.acomp, projeto=proj, origem="TAB. 2")
        self.assertEqual(pf.orcado, D("50000.00"))
        self.assertEqual(pf.realizado, D("0.00"))

        # Indicador operacional registrado no snapshot da base com abertura 0.00
        chave_proj = f"projeto:{proj.pk}:realizado"
        self.assertTrue(
            IndicadorOperacional.objects.filter(acompanhamento=self.acomp, chave=chave_proj, ativo=True).exists()
        )
        base = BaseOperacional.objects.get(acompanhamento=self.acomp)
        self.assertEqual(base.snapshot["alvos"][chave_proj]["valor"], "0.00")

        # Total Realizado de PDI NÃO muda apenas por cadastrar o orçamento planejado
        invalidar_cache()
        self.assertEqual(ler_estado_operacional(self.acomp).total("PDI", "realizado"), pdi_real_antes)

        # Proposta PE-01 pendente (criada antes do sync) continua aprovável sem erro de versão!
        aprovar_integracao_operacional(integ_pe01.pk, self.master)
        invalidar_cache()
        self.assertEqual(ler_estado_operacional(self.acomp).kpi("PE-01", None), pe01_antes + 1)

        # Projeto já aparece em PDI (Físico) -> Entregáveis dos projetos E em PDI (Financeiro) -> tabela de projetos
        resp_pdi_fis = self.client.get(reverse("core:pilar", args=[self.pilares["PDI"].pk]) + "?base=fis")
        self.assertEqual(resp_pdi_fis.status_code, 200)
        self.assertContains(resp_pdi_fis, "Novo Projeto Teste 2")

        resp_pdi_fin = self.client.get(reverse("core:pilar", args=[self.pilares["PDI"].pk]) + "?base=fin")
        self.assertEqual(resp_pdi_fin.status_code, 200)
        self.assertContains(resp_pdi_fin, "Novo Projeto Teste 2")

        # AuditLog registra a sincronização
        self.assertTrue(
            AuditLog.objects.filter(
                acao="SEMESTRAL_PROJETO_SINCRONIZADO_CATALOGO",
                entidade="Projeto",
                registro_id=str(proj.pk),
                usuario=self.master,
            ).exists()
        )

        # Idempotência: sincronizar novamente não duplica Projeto nem ProjetoFinanceiro
        qtd_projs = Projeto.objects.filter(centro=self.acomp.centro, pilar=self.pilares["PDI"]).count()
        qtd_pfs = ProjetoFinanceiro.objects.filter(acompanhamento=self.acomp, origem="TAB. 2").count()
        sincronizar_projeto_para_catalogo_oficial(comp_afcct, "afcct-2", reg.pk, self.master, acompanhamento=self.acomp)
        self.assertEqual(Projeto.objects.filter(centro=self.acomp.centro, pilar=self.pilares["PDI"]).count(), qtd_projs)
        self.assertEqual(ProjetoFinanceiro.objects.filter(acompanhamento=self.acomp, origem="TAB. 2").count(), qtd_pfs)

        # Agora a Ponte exibe o card financeiro PROJ:<uuid_hex> exigindo Realizado explícito (nunca copia Orçado!)
        tipo_proj = f"PROJ:{proj.pk.hex}"
        self.assertLessEqual(len(tipo_proj), 40)
        pacote = calcular_sugestoes_competencia(comp_afcct, acompanhamento=self.acomp)
        self.assertEqual(pacote["total_projetos_sem_vinculo"], 0)
        sug_fin = next(s for s in pacote["sugestoes"] if s["tipo_alvo"] == tipo_proj)
        self.assertTrue(sug_fin["eh_orcado_manual"])
        self.assertEqual(sug_fin["valor_vigente"], D("0.00"))
        self.assertEqual(sug_fin["orcado_referencia"], D("50000.00"))

        with self.assertRaises(ValidationError):
            aplicar_sugestao_operacional(
                comp_afcct, tipo_proj, self.master, valor_alvo_final="", modo="DIRETO", acompanhamento=self.acomp
            )

        # Lança Realizado financeiro de R$ 12.500,00 em modo DIRETO -> atualiza PDI Financeiro e Visão Geral Financeiro
        integ_fin = aplicar_sugestao_operacional(
            comp_afcct,
            tipo_proj,
            self.master,
            valor_alvo_final="12500,00",
            modo="DIRETO",
            justificativa="1ª medição executada do projeto",
            acompanhamento=self.acomp,
        )
        self.assertEqual(integ_fin.lancamento_operacional.status, "APROVADO")

        invalidar_cache()
        estado_final = ler_estado_operacional(self.acomp)
        self.assertEqual(estado_final.valor(chave_proj), D("12500.00"))
        self.assertEqual(estado_final.total("PDI", "realizado"), pdi_real_antes + D("12500.00"))

        # ResumoFinanceiro importado continua preservado
        self.assertEqual(
            ResumoFinanceiro.objects.get(
                acompanhamento=self.acomp, origem="TAB. 1", pilar__codigo="PDI", ano__isnull=True
            ).realizado,
            resumo_pdi_antes,
        )

        # Exportação EMBRAPII v3.1 continua 100% íntegra
        _nome, dados_xlsx = exportar_planilha_embrapii(self.ciclo_s2, "AFCCT")
        template_path, _pattern = TEMPLATE_MAP["AFCCT"]
        relatorio = validar_integridade_xlsx(template_path, dados_xlsx)
        self.assertGreater(relatorio["sheets_checked"], 0)
        self.assertGreater(relatorio["formulas_preserved"], 0)
