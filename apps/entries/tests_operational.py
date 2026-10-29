from datetime import date
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accountability import services as ingestion
from apps.accountability.models import Acompanhamento, KpiAcompanhamento, ProjetoFinanceiro, ResumoFinanceiro
from apps.accountability.tests.fixtures_financeiro import FINANCEIRO
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.periods.models import Periodo
from apps.pillars.models import Pilar, UsuarioPilar
from apps.planning.views import contexto_painel, contexto_pilar, _html_standalone
from . import operational as op
from .models import BaseOperacional, IndicadorOperacional, LancamentoOperacional


class OperacaoTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        garantir_grupos()
        cls.user = adicionar_grupo(get_user_model().objects.create_user(username="op-master"), "Master")
        cls.focal = adicionar_grupo(get_user_model().objects.create_user(username="op-focal"), "PontoFocal")
        cls.auditor = adicionar_grupo(get_user_model().objects.create_user(username="op-auditor"), "Auditor")
        cls.pilares = {c: Pilar.objects.get_or_create(codigo=c, defaults={"nome": c})[0]
                       for c in ("PDI", "FORMACAO", "STARTUPS", "INFRA", "AT", "OUTRASFONTES")}
        UsuarioPilar.objects.create(usuario=cls.focal, pilar=cls.pilares["PDI"])
        ingestion.ingestar("FINANCEIRO_GERAL", FINANCEIRO, "Operação", "3T/2026", cls.user)
        ingestion.ingestar("INDICADORES_PE", FINANCEIRO.with_name("Indicadores Gerais do Termo de Retificação do PE.xlsx"), "Operação", "3T/2026", cls.user)
        cls.acomp = Acompanhamento.objects.get(centro__nome="Operação")
        cls.periodo = Periodo.objects.create(competencia=date(2026, 10, 1), status="ABERTO")

    def base(self):
        return op.confirmar_base(self.acomp, date(2026, 9, 1), self.user)

    def item(self, codigo="PE-01"):
        self.base()
        return IndicadorOperacional.objects.get(acompanhamento=self.acomp, chave="kpi:" + codigo)

    def geral(self, base="fin"):
        return contexto_painel("todos", base, self.user, self.acomp)["painel"]

    def pilar(self, codigo="PDI", base="fin"):
        return contexto_pilar(self.pilares[codigo], "todos", base, self.user, self.acomp)["painel_pilar"]

    def test_confirmar_base_preserva_os_valores_de_todos_os_paineis(self):
        antes = {codigo: self.pilar(codigo)["executado"] for codigo in ("PDI", "FORMACAO", "STARTUPS", "AT")}
        fisicos = {k.codigo: k.acumulado for k in KpiAcompanhamento.objects.filter(acompanhamento=self.acomp)}
        self.base()
        self.assertEqual(antes, {codigo: self.pilar(codigo)["executado"] for codigo in antes})
        for codigo, valor in fisicos.items():
            self.assertEqual(op.valor_atual(IndicadorOperacional.objects.get(acompanhamento=self.acomp, chave="kpi:"+codigo)), valor)
        publicacoes = self.item("PE-09")
        self.assertEqual((publicacoes.tipo, publicacoes.unidade), ("QTD", "publicações"))
        self.assertEqual(self.item("PE-04").base, "financeiro")

    def test_rascunho_envio_devolucao_e_aprovacao(self):
        item = self.item()
        antes = self.pilar(base="fis")["executado"]
        r = op.salvar(item, self.periodo, self.focal, "18", "", enviar=False)
        self.assertEqual(self.pilar(base="fis")["executado"], antes)
        r = op.salvar(item, self.periodo, self.focal, "18", "", enviar=True)
        self.assertEqual(self.pilar(base="fis")["executado"], antes)
        with self.assertRaises(ValidationError):
            op.devolver(r, self.user, "")
        op.devolver(r, self.user, "Conferir evidência")
        self.assertEqual(op.valor_atual(item), D(15))
        r = op.salvar(item, self.periodo, self.focal, "18", "Conferido", enviar=True)
        op.aprovar(r, self.user)
        self.assertEqual(self.pilar(base="fis")["executado"], antes + 3)
        op.aprovar(r, self.user)
        self.assertEqual(op.valor_atual(item), D(18))

    def test_realizado_por_projeto_atualiza_linha_pilar_e_geral_sem_dupla_contagem(self):
        self.base()
        item = IndicadorOperacional.objects.filter(acompanhamento=self.acomp, alvo="PROJETO", pilar__codigo="PDI").first()
        antes = self.pilar()["executado"]
        original = op.valor_atual(item)
        r = op.salvar(item, self.periodo, self.focal, str(original + 100), "Avanço", enviar=True)
        op.aprovar(r, self.user)
        pp = self.pilar()
        self.assertEqual(pp["executado"], antes + 100)
        projeto = next(p for p in pp["registros_projetos"] if str(p["projeto_id"]) == item.referencia)
        self.assertEqual(projeto["realizado"], original + 100)
        geral = self.geral()
        self.assertEqual(geral["tabela_tab1"]["linhas"][0]["realizado"], antes + 100)
        fonte = ProjetoFinanceiro.objects.get(acompanhamento=self.acomp, projeto_id=item.referencia)
        self.assertEqual(fonte.realizado, original)

    def test_nova_competencia_substitui_acumulado_e_mais_antiga_nao_regride_atual(self):
        item = self.item()
        nov = Periodo.objects.create(competencia=date(2026, 11, 1), status="ABERTO")
        r = op.salvar(item, nov, self.user, "20", "", enviar=True)
        op.aprovar(r, self.user)
        r = op.salvar(item, self.periodo, self.user, "18", "", enviar=True)
        op.aprovar(r, self.user)
        self.assertEqual(op.valor_atual(item), D(20))
        self.assertEqual(op.valor_atual(item, self.periodo.competencia), D(18))

    def test_revisao_direta_exige_gestor_e_mantem_historico(self):
        item = self.item()
        with self.assertRaises(PermissionDenied):
            op.salvar(item, self.periodo, self.focal, "18", "Justificativa", direto=True)
        r = op.salvar(item, self.periodo, self.user, "18", "Ajuste documentado", direto=True)
        r2 = op.salvar(item, self.periodo, self.user, "17", "Retificação", direto=True)
        r.refresh_from_db()
        self.assertEqual(r.valor, D(18))
        self.assertEqual(r2.versao, 2)
        self.assertEqual(op.valor_atual(item), D(17))

    def test_percentual_quantidade_periodo_e_escopo(self):
        self.assertEqual(op.parse_valor(self.item("PE-04"), "0,51"), D("0.0051"))
        self.assertEqual(op.parse_valor(self.item("PE-09"), "9"), D(9))
        with self.assertRaises(ValidationError):
            op.parse_valor(self.item(), "1.5")
        with self.assertRaises(ValidationError):
            op.salvar(self.item(), self.periodo, self.focal, "14", "", enviar=True)
        with self.assertRaises(PermissionDenied):
            op.salvar(self.item("PE-07"), self.periodo, self.focal, "2200", "")
        self.periodo.status = "FECHADO"
        self.periodo.save()
        with self.assertRaises(ValidationError):
            op.salvar(self.item(), self.periodo, self.user, "18", "")

    def test_base_alterada_exige_revisao_da_proposta(self):
        item = self.item()
        r = op.salvar(item, self.periodo, self.focal, "18", "", enviar=True)
        op.confirmar_base(self.acomp, date(2026, 9, 1), self.user, "Conciliação", reconciliar=True)
        with self.assertRaises(ValidationError):
            op.aprovar(r, self.user)
        self.assertEqual(op.valor_atual(item), D(15))

    def test_reimportacao_nao_apaga_homologacao(self):
        item = self.item()
        r = op.salvar(item, self.periodo, self.user, "18", "", enviar=True)
        op.aprovar(r, self.user)
        ingestion.ingestar("INDICADORES_PE", FINANCEIRO.with_name("Indicadores Gerais do Termo de Retificação do PE.xlsx"), "Operação", "3T/2026", self.user)
        self.assertEqual(op.valor_atual(item), D(18))
        self.assertEqual(self.pilar(base="fis")["executado"], D(22))

    def test_carteira_at_preserva_abertura_e_aprovacao_atualiza_fonte(self):
        base = self.base()
        antes = self.pilar("AT")["total_captacao"]["captado"]
        projeto = op.criar_projeto_fonte(base, self.pilares["AT"], "Projeto de associação", "1000", "100", self.user)
        self.assertEqual(self.pilar("AT")["total_captacao"]["captado"], antes)
        item = IndicadorOperacional.objects.get(acompanhamento=self.acomp, chave=f"fonte:{projeto.pk}:captado")
        op.salvar(item, self.periodo, self.user, "1200", "Aporte confirmado", direto=True)
        pp = self.pilar("AT")
        self.assertEqual(pp["total_captacao"]["captado"], antes + 200)
        self.assertEqual(next(p["captado"] for p in pp["carteira_fontes"] if p["nome"] == projeto.nome), D(1200))

    def test_rotas_catalogo_aprovacao_e_bloqueio_das_escritas_legadas(self):
        self.base()
        self.client.force_login(self.user)
        url = reverse("entries:formulario", args=[self.periodo.pk, self.pilares["PDI"].pk])
        response = self.client.get(url, {"acompanhamento": self.acomp.pk})
        self.assertContains(response, 'data-testid="catalogo-operacional"')
        self.assertNotContains(response, "PDI-ARTIGOS")
        self.assertEqual(self.client.post(url, {"valor_1": "2"}).status_code, 400)
        response = self.client.get(reverse("entries:aprovacao", args=[self.periodo.pk]))
        self.assertContains(response, 'data-testid="operation-board"')
        self.client.force_login(self.auditor)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.get(reverse("entries:aprovacao", args=[self.periodo.pk])).status_code, 403)

    def test_paginacao_por_coluna_e_aprovados_recolhidos(self):
        item = self.item()
        LancamentoOperacional.objects.bulk_create([LancamentoOperacional(indicador=item, periodo=self.periodo,
            versao=n, valor=n, valor_base=15, base_versao=1, status="APROVADO", criado_por=self.user) for n in range(1, 51)])
        self.client.force_login(self.user)
        url = reverse("entries:aprovacao", args=[self.periodo.pk])
        response = self.client.get(url)
        self.assertNotContains(response, 'data-testid="operational-card"')
        response = self.client.get(url, {"aprovados_abertos": "1"})
        self.assertContains(response, 'data-testid="operational-card"', count=10)

    def test_competencia_mensal_publica_a_posicao_acumulada_sem_rateio(self):
        from apps.core.overview_period import resolver_periodo
        item = self.item()
        op.salvar(item, self.periodo, self.user, "18", "Conferido", direto=True)
        periodo = resolver_periodo({"mes_inicial": "2026-10", "mes_final": "2026-10"})
        contexto = contexto_pilar(self.pilares["PDI"], "todos", "fis", self.user, self.acomp, periodo)
        self.assertFalse(contexto["sem_dados_intervalo"])
        self.assertEqual(contexto["painel_pilar"]["executado"], D(22))
        self.assertIn("Posição acumulada", contexto["nota_operacional"])

    def test_anuais_derivam_do_acumulado_sem_inventar_referencia_financeira(self):
        from .effective import estado
        item = self.item()
        op.salvar(item, self.periodo, self.user, "18", "Conferido", direto=True)
        e = estado(self.acomp)
        self.assertEqual(e.kpi("PE-01", 2026), D(3))
        # O Excel não fornece a execução financeira anual do pilar.
        self.assertIsNone(e.anual("PDI", 2026))
        self.assertIsNone(e.total("PDI", limite=date(2026, 8, 1)))

    def test_exports_e_apresentacao_usam_o_mesmo_resultado_homologado(self):
        item = self.item()
        op.salvar(item, self.periodo, self.user, "18", "Conferido", direto=True)
        self.client.force_login(self.user)
        response = self.client.get(reverse("planning:csv"), {"acompanhamento": self.acomp.pk, "base": "fis", "pilar": self.pilares["PDI"].pk})
        self.assertEqual(response.status_code, 200)
        # A visão resumida de PDI combina projetos e pedidos de PI (PE-09 não entra no agregado).
        self.assertIn("22", response.content.decode("utf-8-sig"))
        response = self.client.get(reverse("planning:export_html"), {"acompanhamento": self.acomp.pk, "base": "fis", "pilar": self.pilares["PDI"].pk})
        self.assertEqual(response.status_code, 200)
        self.assertIn("22", response.content.decode())
        from apps.reports.models import ApresentacaoMensal
        from apps.reports.presentation import compor_apresentacao
        apresentacao = ApresentacaoMensal.objects.create(competencia=date(2026, 11, 1), acompanhamento=self.acomp)
        slides = compor_apresentacao(apresentacao, self.user)["slides"]
        linhas = [linha for slide in slides if slide["tipo"] == "pilar" and slide["chave"] == "pdi" for linha in slide["indicadores"]]
        self.assertEqual(next(linha["executado"] for linha in linhas if linha["codigo"] == "PE-01"), D(18))

    def test_limpeza_legada_preserva_importacoes_e_auditoria_com_backup(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        import json
        from django.core.management import call_command
        from apps.indicators.models import Indicador
        from apps.audit.models import AuditLog
        from .models import Lancamento
        indicador = Indicador.objects.create(pilar=self.pilares["PDI"], codigo="LEGADO-TESTE", nome="Antigo", tipo="QTD", unidade="un")
        Lancamento.objects.create(indicador=indicador, periodo=self.periodo, valor_numerico=9, usuario_criacao=self.user)
        before = list(ResumoFinanceiro.objects.filter(acompanhamento=self.acomp).order_by("pk").values())
        auditorias = set(AuditLog.objects.values_list("pk", flat=True))
        with TemporaryDirectory() as directory:
            call_command("limpar_lancamentos_legados", executar=True, confirmar_quantidade=1, diretorio=directory, verbosity=0)
            backup = json.loads(next(Path(directory).glob("*.json")).read_text(encoding="utf-8"))
            self.assertEqual(len(backup["lancamentos"]), 1)
        self.assertEqual(Lancamento.objects.count(), 0)
        self.assertEqual(before, list(ResumoFinanceiro.objects.filter(acompanhamento=self.acomp).order_by("pk").values()))
        self.assertTrue(auditorias.issubset(set(AuditLog.objects.values_list("pk", flat=True))))

    def test_projeto_sem_abertura_nao_e_aprovado_com_impacto_desconhecido(self):
        base = self.base()
        item = IndicadorOperacional.objects.filter(acompanhamento=self.acomp, alvo="PROJETO").first()
        base.snapshot["alvos"][item.chave]["valor"] = None
        base.save()
        with self.assertRaisesMessage(ValidationError, "não se presume zero"):
            op.salvar(item, self.periodo, self.user, "1000", "Atualização", direto=True)
        self.assertFalse(LancamentoOperacional.objects.filter(indicador=item).exists())
