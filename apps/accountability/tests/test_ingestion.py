import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.pillars.models import Pilar
from .. import services
from ..models import (Acompanhamento, ImportacaoAcompanhamento, KpiAcompanhamento,
                     ProjetoFinanceiro, ResumoFinanceiro)

RAIZ = Path(__file__).resolve().parents[3]
FINANCEIRO = RAIZ / "mockup" / "exemplos_arquivos" / "FINANCEIRO GERAL.xlsx"
INDICADORES = RAIZ / "mockup" / "exemplos_arquivos" / "Indicadores Gerais do Termo de Retificação do PE.xlsx"
V2 = RAIZ / "Acompanhamento Financeiro (v2).xlsx"

CENTRO = "Centro de Competência Embrapii CIMATEC em Tecnologias Quânticas - Quiin"
REFERENCIA = "2T/2024"


class DeteccaoTipoTestes(TestCase):
    def test_identifica_os_tres_tipos_pelas_abas(self):
        assert services.detejar_tipo_arquivo(["HEAD - INDICADORES - EMBRAPII"]) == "INDICADORES_PE"
        assert services.detejar_tipo_arquivo(["FINANCEIRO "]) == "FINANCEIRO_GERAL"
        assert services.detejar_tipo_arquivo(
            ["0. Sumário", "3. Conta Ação - AFCCT"]) == "ACOMPANHAMENTO_V2"
        assert services.detejar_tipo_arquivo(["Qualquer coisa"]) is None

    def test_arquivo_nao_identificado_vira_erro_amigavel(self):
        with self.assertRaises(services.IngestaoError) as ctx:
            services.ingestar("inventado", V2, CENTRO, REFERENCIA, None)
        self.assertIn("não foi possível identificar", str(ctx.exception))


class IngestaoFinanceiroTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        garantir_grupos()
        User = get_user_model()
        cls.user = adicionar_grupo(
            User.objects.create_user(username="ingest", password="x"), "Master")
        for codigo, nome in (("PDI", "PDI"), ("FORMACAO", "Formação FCRH"),
                             ("STARTUPS", "ACS"), ("INFRA", "Infraestrutura"),
                             ("AT", "AT"), ("OUTRASFONTES", "Outras Fontes")):
            Pilar.objects.create(codigo=codigo, nome=nome)

    def test_extrai_e_grava_os_valores_esperados(self):
        imp = services.ingestar("FINANCEIRO_GERAL", FINANCEIRO, CENTRO, REFERENCIA, self.user)
        self.assertEqual(imp.status, "SUCESSO")
        self.assertEqual(imp.resumo, {"resumos": 9, "projetos": 33})
        pdi = ResumoFinanceiro.objects.get(origem="TAB. 1", pilar__codigo="PDI", ano=None)
        self.assertEqual(pdi.recurso_ou_meta, Decimal("29000000"))
        self.assertEqual(pdi.realizado, Decimal("17675109.56"))
        self.assertEqual(ProjetoFinanceiro.objects.filter(origem="TAB. 2").count(), 18)
        self.assertEqual(ProjetoFinanceiro.objects.filter(origem="TAB. 6").count(), 7)
        at = ResumoFinanceiro.objects.get(origem="TAB. 9", pilar__codigo="AT", ano=None)
        self.assertEqual(at.captado, Decimal("5616700"))
        self.assertNotIn("erro", imp.status.lower())

    def test_reenvio_do_mesmo_arquivo_nao_duplica(self):
        services.ingestar("FINANCEIRO_GERAL", FINANCEIRO, CENTRO, REFERENCIA, self.user)
        services.ingestar("FINANCEIRO_GERAL", FINANCEIRO, CENTRO, REFERENCIA, self.user)
        self.assertEqual(ResumoFinanceiro.objects.count(), 9)
        self.assertEqual(ProjetoFinanceiro.objects.count(), 33)
        self.assertEqual(ImportacaoAcompanhamento.objects.filter(status="SUCESSO").count(), 2)

    def test_reimportar_uma_fonte_preserva_as_demas(self):
        services.ingestar("FINANCEIRO_GERAL", FINANCEIRO, CENTRO, REFERENCIA, self.user)
        services.ingestar("INDICADORES_PE", INDICADORES, CENTRO, REFERENCIA, self.user)
        services.ingestar("FINANCEIRO_GERAL", FINANCEIRO, CENTRO, REFERENCIA, self.user)
        self.assertEqual(ResumoFinanceiro.objects.count(), 9)
        self.assertEqual(KpiAcompanhamento.objects.count(), 10)

    def test_v2_real_grava_acompanhamento_com_metadados(self):
        services.ingestar("ACOMPANHAMENTO_V2", V2, CENTRO, REFERENCIA, self.user)
        acomp = Acompanhamento.objects.get()
        self.assertEqual(acomp.periodo_referencia, REFERENCIA)
        self.assertEqual(acomp.termo_cooperacao, "053/2023")
        self.assertEqual(acomp.despesas.count(), 0)

    def test_imprime_resumo_json_do_que_foi_extraido(self):
        payload = services.resumo_json("FINANCEIRO_GERAL", FINANCEIRO, CENTRO, REFERENCIA)
        texto = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        assert payload["tipo_fonte"] == "FINANCEIRO_GERAL"
        assert payload["periodo_referencia"] == REFERENCIA
        assert payload["contagens"] == {"resumos": 9, "projetos": 33}
        assert str(payload["exemplo_resumo"]["realizado"]) == "17675109.56"
        assert '"realizado": "17675109.56"' in texto

    def test_falha_na_gravacao_faz_rollback_total(self):
        Pilar.objects.all().delete()
        with self.assertRaises(ValidationError):
            services.ingestar("FINANCEIRO_GERAL", FINANCEIRO, CENTRO, REFERENCIA, self.user)
        self.assertEqual(ResumoFinanceiro.objects.count(), 0)
        self.assertEqual(ProjetoFinanceiro.objects.count(), 0)
        self.assertEqual(ImportacaoAcompanhamento.objects.filter(status="ERRO").count(), 1)
        self.assertEqual(Acompanhamento.objects.count(), 1)  # histórico de erro é preservado


# ---------------------------------------------------------------------------
# Adições ao piso do brief (Rulings 2, 5 e 7, metadados e auditoria). Os testes
# acima são mantidos literalmente como no brief; estes complementam — nunca
# substituem. Os imports extras ficam aqui para não tocar no bloco do brief.
import tempfile  # noqa: E402

from openpyxl import Workbook  # noqa: E402

from apps.audit.models import AuditLog  # noqa: E402

from ..models import CentroCompetencia, OverrideAcompanhamento  # noqa: E402


class RulingsIngestaoTestes(TestCase):
    """Comportamentos exigidos pelos rulings que o brief não cobre."""

    @classmethod
    def setUpTestData(cls):
        garantir_grupos()
        User = get_user_model()
        cls.user = adicionar_grupo(
            User.objects.create_user(username="rulings", password="x"), "Master")
        for codigo, nome in (("PDI", "PDI"), ("FORMACAO", "Formação FCRH"),
                             ("STARTUPS", "ACS"), ("INFRA", "Infraestrutura"),
                             ("AT", "AT"), ("OUTRASFONTES", "Outras Fontes")):
            Pilar.objects.create(codigo=codigo, nome=nome)

    def test_tipo_divergente_do_detectado_rejeita_com_mensagem_amigavel(self):
        with self.assertRaises(services.IngestaoError) as ctx:
            services.ingestar("INDICADORES_PE", FINANCEIRO, CENTRO, REFERENCIA, self.user)
        self.assertIn("não foi possível identificar", str(ctx.exception))
        self.assertEqual(ImportacaoAcompanhamento.objects.filter(status="ERRO").count(), 1)

    def test_tipo_none_do_upload_rejeita_com_a_mesma_mensagem(self):
        with self.assertRaises(services.IngestaoError) as ctx:
            services.ingestar(None, V2, CENTRO, REFERENCIA, self.user)
        self.assertIn("não foi possível identificar", str(ctx.exception))

    def test_rejeicao_registra_o_tipo_tentado_verbatim(self):
        with self.assertRaises(services.IngestaoError):
            services.ingestar("inventado", V2, CENTRO, REFERENCIA, self.user)
        log = ImportacaoAcompanhamento.objects.get(status="ERRO")
        self.assertEqual(log.tipo_fonte, "inventado")  # Ruling 20: sem coerção

    def test_ingestao_atribui_o_slug_do_centro_real(self):
        services.ingestar("FINANCEIRO_GERAL", FINANCEIRO, CENTRO, REFERENCIA, self.user)
        self.assertEqual(
            Acompanhamento.objects.get().centro.codigo,
            "centro-de-competencia-embrapii-cimatec-em-tecnologias-quanticas-quiin")

    def test_kpi_upsert_preserva_pk_e_overrides_do_usuario(self):
        services.ingestar("INDICADORES_PE", INDICADORES, CENTRO, REFERENCIA, self.user)
        kpi = KpiAcompanhamento.objects.get(codigo="PE-01")
        acomp = Acompanhamento.objects.get()
        OverrideAcompanhamento.objects.create(
            acompanhamento=acomp, base="fisico", kpi=kpi, ano=2025, campo="previsto",
            valor=Decimal("7"), chave="fis|PE-01|2025|previsto", usuario=self.user)
        services.ingestar("INDICADORES_PE", INDICADORES, CENTRO, REFERENCIA, self.user)
        self.assertEqual(KpiAcompanhamento.objects.get(codigo="PE-01").pk, kpi.pk)
        # recriar o KPI dispararia o CASCADE do override (Ruling 7)
        self.assertEqual(OverrideAcompanhamento.objects.get().kpi_id, kpi.pk)
        self.assertEqual(KpiAcompanhamento.objects.count(), 10)

    def test_kpi_que_sumiu_do_arquivo_e_apagado(self):
        services.ingestar("INDICADORES_PE", INDICADORES, CENTRO, REFERENCIA, self.user)
        KpiAcompanhamento.objects.create(
            acompanhamento=Acompanhamento.objects.get(), codigo="PE-99", sequencia=99,
            nome="Extinto", pilar=Pilar.objects.get(codigo="PDI"))
        services.ingestar("INDICADORES_PE", INDICADORES, CENTRO, REFERENCIA, self.user)
        self.assertFalse(KpiAcompanhamento.objects.filter(codigo="PE-99").exists())
        self.assertEqual(KpiAcompanhamento.objects.count(), 10)

    def test_metadado_divergente_rejeita_citando_aba_e_celula(self):
        with self.assertRaises(services.IngestaoError) as ctx:
            services.ingestar("ACOMPANHAMENTO_V2", V2, CENTRO, "1T/2024", self.user)
        mensagem = str(ctx.exception)
        self.assertIn("0. Sumário", mensagem)
        self.assertIn("2T/2024", mensagem)
        self.assertIn("1T/2024", mensagem)
        self.assertRegex(mensagem, r"\([A-Z]+\d+\)")  # cita a célula de origem
        self.assertEqual(Acompanhamento.objects.count(), 0)  # nada persiste
        self.assertEqual(ImportacaoAcompanhamento.objects.filter(status="ERRO").count(), 1)

    def test_auditoria_registrada_no_sucesso_e_no_erro(self):
        services.ingestar("FINANCEIRO_GERAL", FINANCEIRO, CENTRO, REFERENCIA, self.user)
        self.assertEqual(AuditLog.objects.filter(acao="IMPORTAR_PRESTACAO").count(), 1)
        Pilar.objects.all().delete()
        with self.assertRaises(ValidationError):
            services.ingestar("FINANCEIRO_GERAL", FINANCEIRO, CENTRO, REFERENCIA, self.user)
        self.assertEqual(AuditLog.objects.filter(acao="IMPORTAR_PRESTACAO_ERRO").count(), 1)

    def test_resumo_json_dos_indicadores(self):
        payload = services.resumo_json("INDICADORES_PE", INDICADORES, CENTRO, REFERENCIA)
        self.assertEqual(payload["tipo_fonte"], "INDICADORES_PE")
        self.assertEqual(payload["contagens"], {"kpis": 10})


class CentroCodigoTestes(TestCase):
    def test_codigo_do_centro_real_cabe_no_max_length(self):
        from django.core.exceptions import ValidationError
        centro = CentroCompetencia.objects.create(
            codigo="centro-de-competencia-embrapii-cimatec-em-tecnologias-quanticas-quiin",
            nome="Centro de Competência Embrapii CIMATEC em Tecnologias Quânticas - Quiin")
        centro.full_clean()   # levanta se codigo exceder max_length
        self.assertLessEqual(
            len(centro.codigo), CentroCompetencia._meta.get_field("codigo").max_length)


# ------------------------------------------------------- fixtures sintéticas

def _workbook_financeiro(caminho, nomes_projetos):
    """Workbook ``FINANCEIRO GERAL`` sintético (estilo das fixtures da suíte).

    A TAB. 1 traz uma única linha de resumo (INFRA) e a TAB. 2 traz os
    projetos PDI pedidos — assim o pilar dos projetos não aparece em nenhum
    ``resumo``/``kpi``/``despesa``. Os blocos obrigatórios restantes aparecem
    só com título (e rótulo de pilar em TAB. 3/5/8) para o parser não acusar
    bloco ausente nem rótulo desconhecido.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "FINANCEIRO "
    ws["C1"] = "TAB. 1 - Consolidado"
    ws["C2"] = "Ação"
    ws["C4"] = "INFRAESTRUTURA"
    ws["D4"] = 100
    ws["E4"] = 50
    ws["M6"] = "TAB. 1.1 - Anual"
    ws["M7"] = "Ação"
    ws["C9"] = "TAB. 2 - Projetos"
    ws["C10"] = "PROJETO"
    for indice, nome in enumerate(nomes_projetos):
        linha = 12 + indice
        ws[f"B{linha}"] = indice + 1
        ws[f"C{linha}"] = nome
        ws[f"D{linha}"] = "Em execução"
        ws[f"G{linha}"] = 10
        ws[f"H{linha}"] = 5
    proximo = 14 + len(nomes_projetos)
    ws[f"C{proximo}"] = "TAB. 3 - Reconciliação"
    ws[f"E{proximo}"] = "AFCCT / PD&I"
    ws[f"C{proximo + 2}"] = "TAB. 4 - Projetos FCRH"
    ws[f"C{proximo + 3}"] = "PROJETO"
    ws[f"C{proximo + 5}"] = "TAB. 5 - Reconciliação FCRH"
    ws[f"E{proximo + 5}"] = "FCRH"
    ws[f"C{proximo + 7}"] = "TAB. 6 - Projetos ACS"
    ws[f"C{proximo + 8}"] = "PROJETO"
    ws[f"C{proximo + 10}"] = "TAB. 8 - Reconciliação ACS"
    ws[f"E{proximo + 10}"] = "ACS"
    ws[f"C{proximo + 12}"] = "TAB. 9 - AT e Outras Fontes"
    ws[f"C{proximo + 13}"] = "Pilar"
    wb.save(caminho)


def _instantaneo():
    """Snapshot das linhas de resumo/projeto para comparar antes e depois."""
    resumos = list(ResumoFinanceiro.objects.order_by(
        "origem", "pilar__codigo", "ano").values_list(
            "origem", "pilar__codigo", "ano", "recurso_ou_meta", "captado",
            "realizado"))
    projetos = list(ProjetoFinanceiro.objects.order_by(
        "origem", "sequencia", "nome").values_list(
            "origem", "pilar__codigo", "sequencia", "nome", "orcado",
            "realizado"))
    return resumos, projetos


class PilarSoEmProjetosTestes(TestCase):
    """Pilar que só aparece em ``projetos`` precisa entrar na resolução."""

    @classmethod
    def setUpTestData(cls):
        garantir_grupos()
        User = get_user_model()
        cls.user = adicionar_grupo(
            User.objects.create_user(username="pilarprojeto", password="x"), "Master")
        Pilar.objects.create(codigo="INFRA", nome="Infraestrutura")

    def test_pilar_somente_de_projeto_e_resolvido(self):
        Pilar.objects.create(codigo="PDI", nome="PDI")
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "sintetico.xlsx"
            _workbook_financeiro(caminho, ["Projeto Alfa"])
            imp = services.ingestar("FINANCEIRO_GERAL", caminho, CENTRO, REFERENCIA, self.user)
        self.assertEqual(imp.status, "SUCESSO")
        self.assertEqual(imp.resumo, {"resumos": 1, "projetos": 1})
        self.assertEqual(ProjetoFinanceiro.objects.get().pilar.codigo, "PDI")
        self.assertEqual(ResumoFinanceiro.objects.get().pilar.codigo, "INFRA")

    def test_pilar_somente_de_projeto_ausente_vira_validation_error(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "sintetico.xlsx"
            _workbook_financeiro(caminho, ["Projeto Alfa"])
            with self.assertRaises(ValidationError) as ctx:
                services.ingestar("FINANCEIRO_GERAL", caminho, CENTRO, REFERENCIA, self.user)
        self.assertIn(  # mensagem mandatória, não KeyError
            "Pilar 'PDI' não encontrado. Cadastre o pilar antes de aplicar.",
            str(ctx.exception))
        self.assertEqual(ResumoFinanceiro.objects.count(), 0)
        self.assertEqual(ProjetoFinanceiro.objects.count(), 0)
        self.assertEqual(ImportacaoAcompanhamento.objects.filter(status="ERRO").count(), 1)


class RollbackNoMeioDaGravacaoTestes(TestCase):
    """Falha depois de gravar fatos dentro da transação não pode deixar parcial."""

    @classmethod
    def setUpTestData(cls):
        garantir_grupos()
        User = get_user_model()
        cls.user = adicionar_grupo(
            User.objects.create_user(username="rollbackreal", password="x"), "Master")
        for codigo, nome in (("PDI", "PDI"), ("FORMACAO", "Formação FCRH"),
                             ("STARTUPS", "ACS"), ("INFRA", "Infraestrutura"),
                             ("AT", "AT"), ("OUTRASFONTES", "Outras Fontes")):
            Pilar.objects.create(codigo=codigo, nome=nome)

    def test_falha_apos_gravar_fatos_restaura_as_linhas_anteriores(self):
        services.ingestar("FINANCEIRO_GERAL", FINANCEIRO, CENTRO, REFERENCIA, self.user)
        resumos_antes, projetos_antes = _instantaneo()
        self.assertEqual(len(resumos_antes), 9)
        self.assertEqual(len(projetos_antes), 33)

        # Dois projetos com o mesmo (origem, nome): o bulk_create dos projetos
        # estoura IntegrityError DEPOIS de os resumos já terem sido recriados
        # dentro da transação — o rollback tem que restaurar tudo.
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "duplicado.xlsx"
            _workbook_financeiro(caminho, ["Projeto Beta", "Projeto Beta"])
            with self.assertRaises(services.IngestaoError):
                services.ingestar("FINANCEIRO_GERAL", caminho, CENTRO, REFERENCIA, self.user)

        resumos_depois, projetos_depois = _instantaneo()
        self.assertEqual(resumos_depois, resumos_antes)   # linhas pré-existentes idênticas
        self.assertEqual(projetos_depois, projetos_antes)
        self.assertFalse(ProjetoFinanceiro.objects.filter(nome="Projeto Beta").exists())
        self.assertEqual(ResumoFinanceiro.objects.count(), 9)
        self.assertEqual(ProjetoFinanceiro.objects.count(), 33)
        self.assertEqual(ImportacaoAcompanhamento.objects.filter(status="SUCESSO").count(), 1)
        self.assertEqual(ImportacaoAcompanhamento.objects.filter(status="ERRO").count(), 1)
