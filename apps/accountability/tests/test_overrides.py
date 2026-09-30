from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.pillars.models import Pilar
from .. import overrides, panel, services
from ..models import Acompanhamento, OverrideAcompanhamento
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
FINANCEIRO = RAIZ / "mockup" / "exemplos_arquivos" / "FINANCEIRO GERAL.xlsx"
INDICADORES = RAIZ / "mockup" / "exemplos_arquivos" / "Indicadores Gerais do Termo de Retificação do PE.xlsx"
CENTRO = "Centro de Competência Embrapii CIMATEC em Tecnologias Quânticas - Quiin"


class OverrideTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        garantir_grupos()
        User = get_user_model()
        cls.user = adicionar_grupo(User.objects.create_user(username="ovr", password="x"), "Master")
        for codigo, nome in (("PDI", "PDI"), ("FORMACAO", "Formação FCRH"),
                             ("STARTUPS", "ACS"), ("INFRA", "Infraestrutura"),
                             ("AT", "AT"), ("OUTRASFONTES", "Outras Fontes")):
            Pilar.objects.create(codigo=codigo, nome=nome)
        services.ingestar("FINANCEIRO_GERAL", FINANCEIRO, CENTRO, "2T/2024", cls.user)
        services.ingestar("INDICADORES_PE", INDICADORES, CENTRO, "2T/2024", cls.user)
        cls.acomp = Acompanhamento.objects.get()

    def test_override_tem_precedencia_sobre_o_importado(self):
        overrides.aplicar_overrides(self.acomp, "financeiro",
                                    [(2026, "PDI", "executado", Decimal("999"))], self.user)
        p = panel.painel_acompanhamento(2026, "financeiro", self.acomp)
        linha = next(l for l in p["tabela"]["grupos"][0]["linhas"] if l["rotulo"] == "PDI")
        assert linha["executado"] == Decimal("999")

    def test_override_fisico_por_kpi(self):
        kpi = self.acomp.kpis.get(codigo="PE-01")
        overrides.aplicar_overrides(self.acomp, "fisico",
                                    [(2025, kpi.codigo, "executado", Decimal("99"))], self.user)
        p = panel.painel_acompanhamento(2025, "fisico", self.acomp)
        linha = next(l for l in p["tabela"]["grupos"][0]["linhas"]
                     if l["rotulo"].startswith("Projetos de PD&I"))
        assert linha["executado"] == Decimal("99")

    def test_valor_vazio_remove_o_override_e_restaura_o_importado(self):
        overrides.aplicar_overrides(self.acomp, "financeiro",
                                    [(2026, "PDI", "executado", Decimal("999"))], self.user)
        overrides.aplicar_overrides(self.acomp, "financeiro",
                                    [(2026, "PDI", "executado", None)], self.user)
        assert not OverrideAcompanhamento.objects.filter(acompanhamento=self.acomp).exists()

    def test_restaurar_tudo_limpa_a_base_inteira(self):
        overrides.aplicar_overrides(self.acomp, "financeiro",
                                    [(2026, "PDI", "executado", Decimal("1"))], self.user)
        overrides.aplicar_overrides(self.acomp, "fisico",
                                    [(2026, "PE-01", "previsto", Decimal("2"))], self.user)
        assert overrides.restaurar_tudo(self.acomp, self.user) == 2
        assert not OverrideAcompanhamento.objects.filter(acompanhamento=self.acomp).exists()

    def test_ponto_focal_nao_edita_pilar_alheio(self):
        # Deviation mecânica (Ruling 1/12 — asserções intactas): o bloco do brief
        # traz literalmente `Pilar.objects.create(codigo="OUTRASFONTES",
        # nome="Outras Fontes", ordem=6)`, mas `Pilar.codigo` é unique=True e o
        # setUpTestData do próprio brief já criou OUTRASFONTES (obrigatório para
        # `services.ingestar` aceitar o FINANCEIRO GERAL) — a linha literal estoura
        # IntegrityError antes de chegar na asserção. `get_or_create` preserva a
        # intenção da linha (garantir o pilar); NENHUMA asserção foi alterada.
        Pilar.objects.get_or_create(codigo="OUTRASFONTES", defaults={"nome": "Outras Fontes", "ordem": 6})
        pf = adicionar_grupo(get_user_model().objects.create_user(username="pf2", password="x"), "PontoFocal")
        with self.assertRaises(PermissionDenied):
            overrides.aplicar_overrides(self.acomp, "financeiro",
                                        [(2026, "AT", "executado", Decimal("1"))], pf)

    def test_ano_fora_do_intervalo_e_rejeitado(self):
        with self.assertRaises(ValidationError):
            overrides.aplicar_overrides(self.acomp, "financeiro",
                                        [(2030, "PDI", "executado", Decimal("1"))], self.user)

    def test_grade_de_edicao_espelha_os_valores_efetivos(self):
        grade = overrides.grade_edicao_overrides(self.acomp, "financeiro")
        assert grade and grade[0]["linhas"][0]["codigo"] == "PDI"
        fisica = overrides.grade_edicao_overrides(self.acomp, "fisico")
        assert fisica and fisica[0]["linhas"][0]["codigo"] == "PE-01"


# ---------------------------------------------------------------------------
# Testes complementares (Ruling 1/12: o bloco do brief acima é piso — asserções
# verbatim e nunca alteradas; as abaixo pinam decisões de implementação).
# ---------------------------------------------------------------------------

import re
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.pillars.models import UsuarioPilar
from apps.planning.models import PlanoAnual
from ..models import CentroCompetencia

APLICAR = "planning:aplicar"


def _preparar(cls):
    """Fixture idêntica à do brief (roda uma vez por classe de TestCase)."""
    garantir_grupos()
    User = get_user_model()
    cls.user = adicionar_grupo(User.objects.create_user(username="ovrc", password="x"), "Master")
    for codigo, nome in (("PDI", "PDI"), ("FORMACAO", "Formação FCRH"),
                         ("STARTUPS", "ACS"), ("INFRA", "Infraestrutura"),
                         ("AT", "AT"), ("OUTRASFONTES", "Outras Fontes")):
        Pilar.objects.create(codigo=codigo, nome=nome)
    services.ingestar("FINANCEIRO_GERAL", FINANCEIRO, CENTRO, "2T/2024", cls.user)
    services.ingestar("INDICADORES_PE", INDICADORES, CENTRO, "2T/2024", cls.user)
    cls.acomp = Acompanhamento.objects.get()


class OverrideApiComplementarTestes(TestCase):
    setUpTestData = classmethod(_preparar)

    def test_chave_abrevia_a_base(self):
        assert overrides.chave("financeiro", "PDI", 2026, "executado") == "fin|PDI|2026|executado"
        assert overrides.chave("fisico", "PE-01", 2025, "previsto") == "fis|PE-01|2025|previsto"
        assert overrides.chave("fin", "PDI", 2026, "executado") == "fin|PDI|2026|executado"
        assert overrides.chave("fis", "PE-01", 2025, "previsto") == "fis|PE-01|2025|previsto"
        with self.assertRaises(ValidationError):
            overrides.chave("mensal", "PDI", 2026, "executado")

    def test_sem_permissao_de_edicao_levanta_permission_denied(self):
        lider = adicionar_grupo(
            get_user_model().objects.create_user(username="ovrl", password="x"), "Lideranca")
        with self.assertRaises(PermissionDenied):
            overrides.aplicar_overrides(self.acomp, "financeiro",
                                        [(2026, "PDI", "executado", Decimal("1"))], lider)
        with self.assertRaises(PermissionDenied):
            overrides.restaurar_tudo(self.acomp, lider)

    def test_codigos_desconhecidos_sao_rejeitados(self):
        with self.assertRaises(ValidationError):
            overrides.aplicar_overrides(self.acomp, "financeiro",
                                        [(2026, "XX", "executado", Decimal("1"))], self.user)
        with self.assertRaises(ValidationError):
            overrides.aplicar_overrides(self.acomp, "fisico",
                                        [(2026, "PE-99", "executado", Decimal("1"))], self.user)

    def test_valores_e_campos_invalidos_sao_rejeitados(self):
        casos = [
            ("financeiro", [(2026, "PDI", "executado", Decimal("-1"))]),
            ("financeiro", [(2026, "PDI", "executado", Decimal("10") ** 10)]),
            ("financeiro", [(2026, "PDI", "xxx", Decimal("1"))]),
            ("fisico", [(2026, "PE-01", "previsto", Decimal("2.5"))]),
            ("fisico", [(2026, "PE-01", "previsto", Decimal("-3"))]),
            ("mensal", [(2026, "PDI", "executado", Decimal("1"))]),
        ]
        for base, itens in casos:
            with self.subTest(base=base, itens=itens):
                with self.assertRaises(ValidationError):
                    overrides.aplicar_overrides(self.acomp, base, itens, self.user)
        assert not OverrideAcompanhamento.objects.filter(acompanhamento=self.acomp).exists()

    def test_reaplicar_o_mesmo_valor_nao_escreve_nem_audita(self):
        assert overrides.aplicar_overrides(
            self.acomp, "financeiro", [(2026, "PDI", "executado", Decimal("999"))], self.user) == 1
        assert overrides.aplicar_overrides(
            self.acomp, "financeiro", [(2026, "PDI", "executado", Decimal("999"))], self.user) == 0
        assert OverrideAcompanhamento.objects.filter(acompanhamento=self.acomp).count() == 1
        assert AuditLog.objects.filter(acao="EDITAR_OVERRIDE_PRESTACAO").count() == 1

    def test_edicao_audita_anterior_e_novo(self):
        overrides.aplicar_overrides(self.acomp, "financeiro",
                                    [(2026, "PDI", "executado", Decimal("100"))], self.user)
        overrides.aplicar_overrides(self.acomp, "financeiro",
                                    [(2026, "PDI", "executado", Decimal("250"))], self.user)
        logs = list(AuditLog.objects.filter(acao="EDITAR_OVERRIDE_PRESTACAO")
                    .order_by("pk"))
        assert len(logs) == 2
        assert logs[0].campo == "executado" and logs[0].valor_anterior == ""
        assert Decimal(logs[0].valor_novo) == Decimal("100")
        assert Decimal(logs[1].valor_anterior) == Decimal("100")
        assert Decimal(logs[1].valor_novo) == Decimal("250")

    def test_remocao_audita_o_valor_removido(self):
        overrides.aplicar_overrides(self.acomp, "financeiro",
                                    [(2026, "PDI", "executado", Decimal("999"))], self.user)
        overrides.aplicar_overrides(self.acomp, "financeiro",
                                    [(2026, "PDI", "executado", None)], self.user)
        log = AuditLog.objects.filter(acao="EDITAR_OVERRIDE_PRESTACAO").order_by("pk").last()
        assert Decimal(log.valor_anterior) == Decimal("999")
        assert log.valor_novo == ""

    def test_restaurar_tudo_sem_overrides_retorna_zero(self):
        assert overrides.restaurar_tudo(self.acomp, self.user) == 0
        assert AuditLog.objects.filter(acao="RESTAURAR_OVERRIDE_PRESTACAO").count() == 1

    def test_overrides_de_acompanhamentos_distintos_nao_se_misturam(self):
        centro = CentroCompetencia.objects.create(codigo="outro-centro", nome="Outro Centro")
        outro = Acompanhamento.objects.create(centro=centro, periodo_referencia="3T/2024")
        overrides.aplicar_overrides(self.acomp, "financeiro",
                                    [(2026, "PDI", "executado", Decimal("999"))], self.user)
        grade = overrides.grade_edicao_overrides(outro, "financeiro")
        pdi = next(l for l in grade[0]["linhas"] if l["codigo"] == "PDI")
        assert all(c["valor"] is None for c in pdi["celulas"])
        assert overrides.restaurar_tudo(outro, self.user) == 0


class OverrideGradeComplementarTestes(TestCase):
    setUpTestData = classmethod(_preparar)

    def test_grade_mostra_o_valor_efetivo_do_override(self):
        grade_vazia = overrides.grade_edicao_overrides(self.acomp, "financeiro")
        bloco = next(b for b in grade_vazia if b["titulo"] == "Recursos PPI, executado")
        pdi = next(l for l in bloco["linhas"] if l["codigo"] == "PDI")
        assert pdi["celulas"][2] == {"ano": 2026, "valor": None}  # sem TAB. 1.1 anual
        overrides.aplicar_overrides(self.acomp, "financeiro",
                                    [(2026, "PDI", "executado", Decimal("999"))], self.user)
        grade = overrides.grade_edicao_overrides(self.acomp, "financeiro")
        bloco = next(b for b in grade if b["titulo"] == "Recursos PPI, executado")
        pdi = next(l for l in bloco["linhas"] if l["codigo"] == "PDI")
        assert pdi["celulas"][2]["valor"] == Decimal("999")
        assert pdi["celulas"][0]["valor"] is None
        assert pdi["total"] == Decimal("999")

    def test_grade_fisica_mostra_efetivo_por_kpi(self):
        overrides.aplicar_overrides(self.acomp, "fisico",
                                    [(2025, "PE-01", "previsto", Decimal("100"))], self.user)
        fisica = overrides.grade_edicao_overrides(self.acomp, "fisico")
        bloco = next(b for b in fisica if b["titulo"].startswith("Metas por KPI, previsto"))
        pe01 = next(l for l in bloco["linhas"] if l["codigo"] == "PE-01")
        assert pe01["celulas"][1]["valor"] == Decimal("100")   # 2025 vence o importado
        assert pe01["celulas"][2]["valor"] == Decimal("5")     # meta_2026 importada
        assert pe01["campo"] == "previsto"

    def test_grade_respeita_o_escopo_de_codigos(self):
        grade = overrides.grade_edicao_overrides(self.acomp, "financeiro", {"PDI"})
        assert {l["codigo"] for b in grade for l in b["linhas"]} == {"PDI"}
        esperados = set(self.acomp.kpis.filter(pilar__codigo="OUTRASFONTES")
                        .values_list("codigo", flat=True))
        assert esperados  # PE-02 nasce em OUTRASFONTES
        fisica = overrides.grade_edicao_overrides(self.acomp, "fisico", {"OUTRASFONTES"})
        assert {l["codigo"] for b in fisica for l in b["linhas"]} == esperados


class OverridePainelComplementarTestes(TestCase):
    setUpTestData = classmethod(_preparar)

    def test_pct_saldo_faixa_sao_recalculados_dos_efetivos(self):
        overrides.aplicar_overrides(self.acomp, "fisico", [
            (2025, "PE-01", "previsto", Decimal("100")),
            (2025, "PE-01", "executado", Decimal("25")),
        ], self.user)
        p = panel.painel_acompanhamento(2025, "fisico", self.acomp)
        linha = next(l for g in p["tabela"]["grupos"] for l in g["linhas"]
                     if l["rotulo"].startswith("Projetos de PD&I"))
        assert linha["saldo"] == Decimal("75")
        assert linha["pct"] == 25
        assert linha["faixa"] == "critica"

    def test_override_preenche_ano_sem_executado_e_recalcula(self):
        # 2026 só tem projeção: executado importado é None; o override passa a
        # valer e saldo/pct saem dos efetivos (5 − 7 = −2; 140%).
        overrides.aplicar_overrides(self.acomp, "fisico",
                                    [(2026, "PE-01", "executado", Decimal("7"))], self.user)
        p = panel.painel_acompanhamento(2026, "fisico", self.acomp)
        linha = next(l for g in p["tabela"]["grupos"] for l in g["linhas"]
                     if l["rotulo"].startswith("Projetos de PD&I"))
        assert linha["previsto"] == Decimal("5")   # meta_2026 importada
        assert linha["executado"] == Decimal("7")
        assert linha["saldo"] == Decimal("-2")
        assert linha["pct"] == 140

    def test_acumulado_importado_nao_e_afetado_por_override_anual(self):
        # Decisão: o override cobre o ano; o consolidado (TAB. 1/TAB. 9) e o
        # acumulado do físico são figuras importadas próprias (SDD §8) e ficam.
        overrides.aplicar_overrides(self.acomp, "financeiro",
                                    [(2026, "PDI", "executado", Decimal("999"))], self.user)
        p = panel.painel_acompanhamento(None, "financeiro", self.acomp)
        linha = next(l for l in p["tabela"]["grupos"][0]["linhas"] if l["rotulo"] == "PDI")
        assert linha["executado"] == Decimal("17675109.56")

    def test_serie_anual_do_grafico_reflete_o_override(self):
        overrides.aplicar_overrides(self.acomp, "financeiro",
                                    [(2026, "PDI", "executado", Decimal("999"))], self.user)
        p = panel.painel_acompanhamento(None, "financeiro", self.acomp)
        assert p["graficos"]["ppi"]["serie_executado"][2] == Decimal("999")  # 2026


class OverrideViewComplementarTestes(TestCase):
    setUpTestData = classmethod(_preparar)

    def _dados(self, **kwargs):
        base = {"ano": "todos", "base": "fin", "acompanhamento": str(self.acomp.pk)}
        base.update(kwargs)
        return base

    def test_post_com_acompanhamento_grava_override_e_audita(self):
        self.client.force_login(self.user)
        resposta = self.client.post(reverse(APLICAR), self._dados(**{
            "v__2026__financeiro__PDI__executado": "999",
        }))
        self.assertRedirects(resposta, "/?ano=todos&base=fin", fetch_redirect_response=False)
        ovr = OverrideAcompanhamento.objects.get(acompanhamento=self.acomp)
        assert (ovr.chave, ovr.base, ovr.ano, ovr.campo) == ("fin|PDI|2026|executado", "financeiro", 2026, "executado")
        assert ovr.valor == Decimal("999")
        assert ovr.pilar.codigo == "PDI" and ovr.kpi is None
        assert ovr.usuario == self.user
        log = AuditLog.objects.get(acao="EDITAR_OVERRIDE_PRESTACAO")
        assert log.entidade == "OverrideAcompanhamento"
        assert Decimal(log.valor_novo) == Decimal("999")
        assert not PlanoAnual.objects.exists()  # legado intocado

    def test_valor_vazio_no_post_remove_o_override(self):
        overrides.aplicar_overrides(self.acomp, "financeiro",
                                    [(2026, "PDI", "executado", Decimal("999"))], self.user)
        self.client.force_login(self.user)
        resposta = self.client.post(reverse(APLICAR), self._dados(**{
            "v__2026__financeiro__PDI__executado": "",
        }))
        self.assertEqual(resposta.status_code, 302)
        assert not OverrideAcompanhamento.objects.filter(acompanhamento=self.acomp).exists()
        log = AuditLog.objects.filter(acao="EDITAR_OVERRIDE_PRESTACAO").order_by("pk").last()
        assert Decimal(log.valor_anterior) == Decimal("999")
        assert log.valor_novo == ""

    def test_acao_restaurar_limpa_tudo_e_audita(self):
        overrides.aplicar_overrides(self.acomp, "financeiro",
                                    [(2026, "PDI", "executado", Decimal("1"))], self.user)
        overrides.aplicar_overrides(self.acomp, "fisico",
                                    [(2025, "PE-01", "previsto", Decimal("2"))], self.user)
        self.client.force_login(self.user)
        resposta = self.client.post(reverse(APLICAR), self._dados(acao="restaurar"))
        self.assertRedirects(resposta, "/?ano=todos&base=fin", fetch_redirect_response=False)
        assert not OverrideAcompanhamento.objects.filter(acompanhamento=self.acomp).exists()
        assert AuditLog.objects.filter(acao="RESTAURAR_OVERRIDE_PRESTACAO").count() == 1

    def test_post_invalido_nao_grava_nada(self):
        self.client.force_login(self.user)
        for dados in (
            {"v__2026__financeiro__PDI__executado": "-1"},
            {"v__2026__fisico__PE-01__executado": "2.5"},
            {"v__2026__financeiro__PDI__executado": "abc"},
            {"v__2030__financeiro__PDI__executado": "5"},
            {"v__2026__financeiro__XX__executado": "5"},
            {"v__2026__financeiro__PDI__xxx": "5"},
        ):
            with self.subTest(dados=dados):
                resposta = self.client.post(reverse(APLICAR), self._dados(**dados))
                self.assertIn(resposta.status_code, (302, 400))
        assert not OverrideAcompanhamento.objects.filter(acompanhamento=self.acomp).exists()
        assert not PlanoAnual.objects.exists()

    def test_ponto_focal_nao_grava_override_alheio_pela_view(self):
        pf = adicionar_grupo(
            get_user_model().objects.create_user(username="ovrpf", password="x"), "PontoFocal")
        self.client.force_login(pf)
        resposta = self.client.post(reverse(APLICAR), self._dados(**{
            "v__2026__financeiro__AT__executado": "1",
        }))
        self.assertEqual(resposta.status_code, 403)
        assert not OverrideAcompanhamento.objects.filter(acompanhamento=self.acomp).exists()

    def test_ponto_focal_edita_kpi_do_proprio_pilar(self):
        # No físico o escopo do PontoFocal é o pilar do KPI (SDD §9).
        kpi = self.acomp.kpis.get(codigo="PE-01")
        pf = adicionar_grupo(
            get_user_model().objects.create_user(username="ovrpf2", password="x"), "PontoFocal")
        UsuarioPilar.objects.create(usuario=pf, pilar=kpi.pilar)
        self.client.force_login(pf)
        resposta = self.client.post(reverse(APLICAR), self._dados(**{
            "v__2025__fisico__PE-01__executado": "99",
        }))
        self.assertEqual(resposta.status_code, 302)
        ovr = OverrideAcompanhamento.objects.get(acompanhamento=self.acomp)
        assert ovr.kpi == kpi and ovr.pilar is None
        assert ovr.valor == Decimal("99")

    def test_lideranca_recebe_403_e_nada_muda(self):
        lider = adicionar_grupo(
            get_user_model().objects.create_user(username="ovrlid", password="x"), "Lideranca")
        self.client.force_login(lider)
        resposta = self.client.post(reverse(APLICAR), self._dados(**{
            "v__2026__financeiro__PDI__executado": "99",
        }))
        self.assertEqual(resposta.status_code, 403)
        assert not OverrideAcompanhamento.objects.filter(acompanhamento=self.acomp).exists()

    def test_aplicar_e_baixar_com_acompanhamento(self):
        self.client.force_login(self.user)
        resposta = self.client.post(reverse(APLICAR), self._dados(
            acao="baixar", **{"v__2026__financeiro__PDI__executado": "999"}))
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("attachment", resposta["Content-Disposition"])
        self.assertIn("dashboard_quiin", resposta["Content-Disposition"])
        assert OverrideAcompanhamento.objects.filter(acompanhamento=self.acomp).exists()

    def test_sem_acompanhamento_o_legado_continua_intocado(self):
        self.client.force_login(self.user)
        resposta = self.client.post(reverse(APLICAR), {
            "ano": "todos", "base": "fin",
            "v__2026__financeiro__PDI__executado": "9",
        })
        self.assertEqual(resposta.status_code, 302)
        assert not OverrideAcompanhamento.objects.filter(acompanhamento=self.acomp).exists()
        linha = PlanoAnual.objects.get(ano=2026, pilar__codigo="PDI", base="financeiro")
        assert linha.executado == Decimal("9")

    def test_editor_mostra_botao_restaurar_e_valores_efetivos(self):
        overrides.aplicar_overrides(self.acomp, "financeiro",
                                    [(2026, "PDI", "executado", Decimal("999"))], self.user)
        self.client.force_login(self.user)
        conteudo = self.client.get("/", {"ano": "2026", "base": "fin"}).content.decode()
        assert "Restaurar valores importados" in conteudo
        assert 'name="acompanhamento" value="%d"' % self.acomp.pk in conteudo
        assert re.search(r'value="999(\.0+)?" name="v__2026__financeiro__PDI__executado"', conteudo)

    def test_editor_sem_acompanhamento_nao_mostra_botao_restaurar(self):
        Acompanhamento.objects.all().delete()
        self.client.force_login(self.user)
        conteudo = self.client.get("/").content.decode()
        assert "Restaurar valores importados" not in conteudo
