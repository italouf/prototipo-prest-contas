"""Testes de paridade entre dashboards (L22): invariantes numéricas.

Garante que Geral×Pilares, Mensal×Semestral e as duas implementações de
cálculo (único × lote) concordam onde devem concordar. I5 (captação = Σ
tipos) entra no L24 com o fix D6.
"""
from datetime import date
from decimal import Decimal as D

from django.test import TestCase

from apps.accounts.models import User
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.entries.models import Lancamento
from apps.finance.models import FinanceiroConsolidado
from apps.indicators.models import Indicador, Meta
from apps.periods.models import Periodo
from apps.pillars.models import Pilar


def _base(master):
    pdi = Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=1)
    ind = Indicador.objects.create(
        pilar=pdi, codigo="PDI-PROJ-INI", nome="Projetos iniciados", tipo="QTD")
    Meta.objects.create(
        indicador=ind, competencia_inicio=date(2026, 1, 1),
        competencia_fim=date(2026, 12, 31), periodicidade="MENSAL", valor=10)
    anual = Indicador.objects.create(
        pilar=pdi, codigo="PDI-ANUAL", nome="Anual", tipo="QTD")
    Meta.objects.create(
        indicador=anual, competencia_inicio=date(2026, 1, 1),
        competencia_fim=date(2026, 12, 31), periodicidade="ANUAL", valor=100)
    maio = Periodo.objects.create(competencia=date(2026, 5, 1), status="FECHADO")
    junho = Periodo.objects.create(
        competencia=date(2026, 6, 1), status="ABERTO", aberto_por=master)
    Lancamento.objects.create(
        periodo=maio, indicador=ind, valor_numerico=D(5), status="APROVADO")
    Lancamento.objects.create(
        periodo=maio, indicador=anual, valor_numerico=D(20), status="APROVADO")
    Lancamento.objects.create(
        periodo=junho, indicador=ind, valor_numerico=D(4), status="APROVADO")
    FinanceiroConsolidado.objects.create(
        periodo=maio, pilar=pdi, tipo_recurso="EMBRAPII",
        valor_captado=D(0), valor_executado=D(100))
    FinanceiroConsolidado.objects.create(
        periodo=junho, pilar=pdi, tipo_recurso="EMBRAPII",
        valor_captado=D(0), valor_executado=D(200))
    return pdi, ind, anual, maio, junho


class ParidadeCalculoTestes(TestCase):
    """I1: lote com 1 período == cálculo único (janela YTD é o ano, não a lista)."""

    def setUp(self):
        garantir_grupos()
        self.master = adicionar_grupo(
            User.objects.create_user(username="par_master", password="x"), "Master")
        _, _, _, self.maio, self.junho = _base(self.master)

    def test_lote_unitario_igual_ao_calculo_unico(self):
        from apps.core.calculos import itens_do_periodo, itens_por_periodo

        inds = list(Indicador.objects.filter(ativo=True))
        for periodo in (self.maio, self.junho):
            unico = {i["indicador"].codigo: i for i in itens_do_periodo(inds, periodo)}
            lote = itens_por_periodo(inds, [periodo])[periodo.pk]
            lote = {i["indicador"].codigo: i for i in lote}
            self.assertEqual(set(unico), set(lote))
            for codigo, item in unico.items():
                outro = lote[codigo]
                self.assertEqual(item["meta"], outro["meta"], codigo)
                self.assertEqual(item["realizado"], outro["realizado"], codigo)
                self.assertEqual(item["percentual"], outro["percentual"], codigo)

    def test_ytd_do_lote_ignora_janela_da_lista(self):
        from apps.core.calculos import itens_por_periodo

        inds = list(Indicador.objects.filter(ativo=True))
        mapa = itens_por_periodo(inds, [self.junho])
        anual = next(i for i in mapa[self.junho.pk] if i["indicador"].codigo == "PDI-ANUAL")
        self.assertEqual(anual["realizado"], D(20))  # só maio conta
        self.assertEqual(anual["percentual"], D(20))


class ParidadeAnualTestes(TestCase):
    """I2: Σ painel_pilar == bloco do painel geral (mesma fonte: PlanoAnual)."""

    def test_soma_dos_pilares_confere_com_geral(self):
        from apps.planning.services import ANOS, painel, painel_pilar
        from apps.planning.tests import criar_base_anual

        pilares = criar_base_anual()
        for base in ("financeiro", "fisico"):
            geral = painel(None, base)
            blocos = {g["bloco"]: g for g in geral["tabela"]["grupos"]}
            soma_ppi = sum(
                painel_pilar(pilares[c], None, base)["previsto"]
                for c in ("PDI", "FORMACAO", "STARTUPS", "INFRA"))
            self.assertEqual(
                soma_ppi,
                next(l["previsto"] for l in blocos["4.1 PPI"]["linhas"] if l.get("total")))
            for codigo, bloco, rotulo in (
                    ("AT", "4.2 Captação de recursos", "Associação Tecnológica (AT)"),
                    ("OUTRASFONTES", "4.3 Outras fontes", "Outras fontes")):
                pp = painel_pilar(pilares[codigo], None, base)
                linha = next(l for l in blocos[bloco]["linhas"] if l["rotulo"] == rotulo)
                self.assertEqual((pp["previsto"], pp["executado"]),
                                 (linha["previsto"], linha["executado"]))
        self.assertEqual(ANOS, [2024, 2025, 2026, 2027])


class ParidadeFinanceiroTestes(TestCase):
    """I3: financeiro do Mensal (último mês) == Semestral (mesma janela)."""

    def setUp(self):
        garantir_grupos()
        self.master = adicionar_grupo(
            User.objects.create_user(username="par_fin", password="x"), "Master")
        _base(self.master)

    def test_ytd_do_mes_igual_semestre(self):
        from apps.core.prestacao import contexto_mensal, painel_semestral
        from apps.periods.models import Periodo as P

        junho = P.objects.get(competencia=date(2026, 6, 1))
        cm = contexto_mensal(junho, self.master)
        cs = painel_semestral(2026, 1, self.master)
        self.assertEqual(cm["cards"]["execucao"], cs["cards"]["executado"])
        self.assertEqual(
            cm["cards"]["captacao_at"] + cm["cards"]["outras_fontes"],
            cs["cards"]["captado"])
        soma_serie = sum((p["captado"] for p in cm["chart_mensal"]), D(0))
        self.assertEqual(soma_serie, cs["cards"]["captado"])
