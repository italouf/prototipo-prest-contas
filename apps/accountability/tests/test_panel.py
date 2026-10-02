"""Painel anual alimentado pelos snapshots importados (Task 7, SDD §8)."""
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.planning.models import PlanoAnual
from apps.pillars.models import Pilar
from .. import panel, services
from ..models import Acompanhamento, CentroCompetencia, KpiAcompanhamento, ResumoFinanceiro

RAIZ = Path(__file__).resolve().parents[3]
FINANCEIRO = RAIZ / "mockup" / "exemplos_arquivos" / "FINANCEIRO GERAL - REFAT.xlsx"
INDICADORES = RAIZ / "mockup" / "exemplos_arquivos" / "Indicadores Gerais do Termo de Retificação do PE.xlsx"
CENTRO = "Centro de Competência Embrapii CIMATEC em Tecnologias Quânticas - Quiin"


class BasePanelTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        garantir_grupos()
        User = get_user_model()
        cls.user = adicionar_grupo(User.objects.create_user(username="panel", password="x"), "Master")
        for codigo, nome in (("PDI", "PDI"), ("FORMACAO", "Formação FCRH"),
                             ("STARTUPS", "ACS"), ("INFRA", "Infraestrutura"),
                             ("AT", "AT"), ("OUTRASFONTES", "Outras Fontes")):
            Pilar.objects.create(codigo=codigo, nome=nome)
        services.ingestar("FINANCEIRO_GERAL", FINANCEIRO, CENTRO, "2T/2024", cls.user)
        services.ingestar("INDICADORES_PE", INDICADORES, CENTRO, "2T/2024", cls.user)
        cls.acomp = Acompanhamento.objects.get()


class PainelFinanceiroTestes(BasePanelTestes):
    def test_painel_e_alimentado_pelo_acompanhamento(self):
        p = panel.painel_acompanhamento(None, "financeiro", self.acomp)
        assert set(p) >= {"ano", "base", "unidade", "rotulo_periodo", "cards",
                          "graficos", "tabela", "consolidado"}
        assert set(p["graficos"]) == {"ppi", "at", "outras"}
        assert len(p["cards"]) == 4

    def test_card_ppi_usa_somente_os_quatro_pilares_ppi(self):
        p = panel.painel_acompanhamento(None, "financeiro", self.acomp)
        ppi = next(c for c in p["cards"] if c["chave"] == "ppi")
        assert ppi["executado"] == Decimal("34975229.95")
        assert ppi["previsto"] == Decimal("60000000")

    def test_card_at_usa_captado_como_denominador(self):
        p = panel.painel_acompanhamento(None, "financeiro", self.acomp)
        at = next(c for c in p["cards"] if c["chave"] == "at")
        assert at["executado"] == Decimal("220597")
        assert at["previsto"] == Decimal("5616700")

    def test_ano_sem_linha_importada_exibe_traco(self):
        p = panel.painel_acompanhamento(2024, "financeiro", self.acomp)
        linha = next(l for l in p["tabela"]["grupos"][0]["linhas"] if l["rotulo"] == "PDI")
        assert linha["executado"] is None
        assert linha["pct"] is None
        assert linha["faixa"] == "neutra"

    def test_totais_de_reconciliacao_nao_sao_somados(self):
        p = panel.painel_acompanhamento(None, "financeiro", self.acomp)
        ppi = next(c for c in p["cards"] if c["chave"] == "ppi")
        # TAB. 3 repete o realizado do PDI; somá-la dobraria o total.
        assert ppi["executado"] == Decimal("34975229.95")


class PainelFisicoTestes(BasePanelTestes):
    def test_fisico_vira_lista_de_kpis_por_unidade(self):
        p = panel.painel_acompanhamento(None, "fisico", self.acomp)
        rotulos = [l["rotulo"] for g in p["tabela"]["grupos"] for l in g["linhas"]]
        assert any("Número absoluto" in r for r in rotulos)
        assert any("Percentual" in r for r in rotulos)

    def test_kpi_sem_executado_no_ano_exibe_traco(self):
        p = panel.painel_acompanhamento(2026, "fisico", self.acomp)
        linha = next(l for l in p["tabela"]["grupos"][0]["linhas"]
                     if l["rotulo"].startswith("Projetos de PD&I"))
        assert linha["previsto"] == Decimal("5")
        assert linha["executado"] is None
        assert linha["pct"] is None
        assert linha["faixa"] == "neutra"

    def test_acumulado_usa_meta_total_e_acumulado(self):
        p = panel.painel_acompanhamento(None, "fisico", self.acomp)
        linha = next(l for l in p["tabela"]["grupos"][0]["linhas"]
                     if l["rotulo"].startswith("Projetos de PD&I"))
        assert linha["previsto"] == Decimal("18")
        assert linha["executado"] == Decimal("15")


class PainelLegadoTestes(TestCase):
    def test_painel_sem_acompanhamento_usa_plano_legado(self):
        from apps.planning.views import contexto_painel
        garantir_grupos()
        user = adicionar_grupo(get_user_model().objects.create_user(username="leg", password="x"), "Master")
        pilar = Pilar.objects.create(codigo="PDI", nome="PDI", ordem=1)
        PlanoAnual.objects.create(ano=2026, pilar=pilar, base="financeiro",
                                  previsto=10, executado=9)
        contexto = contexto_painel("2026", "fin", user)
        assert contexto["painel"] is not None
        assert contexto.get("acompanhamento") is None
        linha = next(l for l in contexto["painel"]["tabela"]["grupos"][0]["linhas"]
                     if l["rotulo"] == "PDI")
        assert linha["previsto"] == Decimal("10")


# ---------------------------------------------------------------------------
# Testes complementares (Ruling 1/12: o brief é piso — asserções acima são
# verbatim e nunca são alteradas; as abaixo pinam decisões de implementação).
# ---------------------------------------------------------------------------

class PainelFinanceiroComplementarTestes(BasePanelTestes):
    def test_tabela_consolidada_usa_recurso_ou_meta_e_realizado(self):
        p = panel.painel_acompanhamento(None, "financeiro", self.acomp)
        linha = next(l for l in p["tabela"]["grupos"][0]["linhas"] if l["rotulo"] == "PDI")
        assert linha["previsto"] == Decimal("29000000")
        assert linha["executado"] == Decimal("17675109.56")

    def test_card_outras_fontes_usa_captado_da_tab9(self):
        p = panel.painel_acompanhamento(None, "financeiro", self.acomp)
        outras = next(c for c in p["cards"] if c["chave"] == "outras")
        assert outras["previsto"] == Decimal("10226768")
        assert outras["executado"] == Decimal("242112")

    def test_card_total_soma_os_tres_blocos(self):
        p = panel.painel_acompanhamento(None, "financeiro", self.acomp)
        total = next(c for c in p["cards"] if c["chave"] == "total")
        assert total["previsto"] == Decimal("75843468")
        assert total["executado"] == Decimal("35437938.95")

    def test_series_dos_graficos_preservam_indisponibilidade(self):
        # Ausência de TAB. 1.1 não pode ser fabricada como zero no gráfico.
        p = panel.painel_acompanhamento(2027, "financeiro", self.acomp)
        for bloco in p["graficos"].values():
            assert len(bloco["serie_previsto"]) == 4
            assert len(bloco["serie_executado"]) == 4
            for valor in bloco["serie_previsto"] + bloco["serie_executado"]:
                assert valor is None or isinstance(valor, Decimal)
        for serie in p["consolidado"]["series"]:
            assert len(serie["valores"]) == 4
            for valor in serie["valores"]:
                assert valor is None or isinstance(valor, Decimal)

    def test_acumulado_do_grafico_fica_separado_da_serie_anual(self):
        p = panel.painel_acompanhamento(None, "financeiro", self.acomp)
        assert p["graficos"]["ppi"]["acumulado_previsto"] == Decimal("60000000")
        assert p["graficos"]["ppi"]["acumulado_executado"] == Decimal("34975229.95")
        assert p["graficos"]["at"]["acumulado_previsto"] == Decimal("5616700")
        assert p["graficos"]["at"]["acumulado_executado"] == Decimal("220597")

    def test_linha_consolidada_da_tab11_nao_vira_ano(self):
        # Ruling 9: linhas TAB. 1.1 só alimentam anos quando `ano` está preenchido.
        pilar = Pilar.objects.get(codigo="PDI")
        ResumoFinanceiro.objects.create(
            acompanhamento=self.acomp, origem="TAB. 1.1", pilar=pilar, ano=None,
            recurso_ou_meta=Decimal("100"), projetado=Decimal("77"))
        p_2024 = panel.painel_acompanhamento(2024, "financeiro", self.acomp)
        linha = next(l for l in p_2024["tabela"]["grupos"][0]["linhas"] if l["rotulo"] == "PDI")
        assert linha["previsto"] is None
        assert linha["executado"] is None
        p_todos = panel.painel_acompanhamento(None, "financeiro", self.acomp)
        linha = next(l for l in p_todos["tabela"]["grupos"][0]["linhas"] if l["rotulo"] == "PDI")
        assert linha["previsto"] == Decimal("29000000")  # segue vindo da TAB. 1

    def test_rodape_dos_graficos_reflete_o_periodo(self):
        p = panel.painel_acompanhamento(None, "financeiro", self.acomp)
        bloco = p["graficos"]["ppi"]
        assert bloco["rodape_pct"] == 58  # 34.975.229,95 de 60.000.000
        assert bloco["rodape_faixa"] == "parcial"
        p_2024 = panel.painel_acompanhamento(2024, "financeiro", self.acomp)
        assert p_2024["graficos"]["ppi"]["rodape_pct"] is None
        assert p_2024["graficos"]["ppi"]["rodape_faixa"] == "neutra"


class PainelFisicoComplementarTestes(BasePanelTestes):
    def test_valores_kpi_nunca_sao_quantizados_para_duas_casas(self):
        # Ruling 11: KPIs são Decimal(18,6) — 0,0016 não pode virar 0,00.
        p = panel.painel_acompanhamento(None, "fisico", self.acomp)
        linhas = [l for g in p["tabela"]["grupos"] for l in g["linhas"]]
        linha = next(l for l in linhas
                     if l["rotulo"].startswith("Recursos financeiros realizados de outras fontes"))
        kpi = KpiAcompanhamento.objects.get(codigo="PE-02")
        assert linha["previsto"] == kpi.meta_total == Decimal("0.6251")
        assert linha["executado"] == kpi.acumulado == Decimal("0.0016")

    def test_cards_sem_executado_no_ano_ficam_neutros(self):
        # Review Focus #4: 2026/2027 só têm projeção — nunca "0%" nem "Execução crítica".
        p = panel.painel_acompanhamento(2026, "fisico", self.acomp)
        for card in p["cards"]:
            assert card["executado"] is None
            assert card["pct"] is None
            assert card["faixa"] == "neutra"
            assert card["barra"] == 0

    def test_blocos_de_grafico_somam_so_a_unidade_majoritaria(self):
        # PPI tem 5 KPIs "Número absoluto" e 2 "Percentual" — só os primeiros somam.
        p = panel.painel_acompanhamento(None, "fisico", self.acomp)
        assert p["graficos"]["ppi"]["acumulado_previsto"] == Decimal("903")
        assert p["graficos"]["ppi"]["acumulado_executado"] == Decimal("2198")

    def test_linha_acumulada_calcula_saldo_pct_e_faixa(self):
        p = panel.painel_acompanhamento(None, "fisico", self.acomp)
        linhas = [l for g in p["tabela"]["grupos"] for l in g["linhas"]]
        linha = next(l for l in linhas if l["rotulo"].startswith("Projetos de PD&I"))
        assert linha["saldo"] == Decimal("3")
        assert linha["pct"] == 83
        assert linha["faixa"] == "parcial"


class PainelPilarAcompanhamentoTestes(BasePanelTestes):
    def test_painel_do_pilar_usa_snapshot_e_separa_projetos_de_reais(self):
        from ..panel import painel_pilar_acompanhamento

        pilar = Pilar.objects.get(codigo="PDI")
        painel_pilar = painel_pilar_acompanhamento(
            pilar, None, "financeiro", self.acomp
        )

        assert painel_pilar["previsto"] == Decimal("29000000")
        assert painel_pilar["executado"] == Decimal("17675109.56")
        assert painel_pilar["projetos"] == 18
        assert painel_pilar["unidade_projetos"] == "projetos"
        assert painel_pilar["serie_previsto"] == [None, None, None, None]
        assert painel_pilar["grafico"]["acumulado_executado"] == Decimal("17675109.56")

    def test_painel_fisico_do_pilar_usa_kpi_importado(self):
        from ..panel import painel_pilar_acompanhamento

        pilar = Pilar.objects.get(codigo="PDI")
        painel_pilar = painel_pilar_acompanhamento(
            pilar, None, "fisico", self.acomp
        )

        assert painel_pilar["previsto"] == Decimal("27")
        assert painel_pilar["executado"] == Decimal("19")
        assert painel_pilar["serie_previsto"] == [Decimal("5"), Decimal("7"), Decimal("9"), Decimal("6")]
        assert painel_pilar["serie_executado"] == [Decimal("5"), Decimal("14"), None, None]


class AcompanhamentoPadraoTestes(TestCase):
    def test_padrao_e_o_mais_recente(self):
        centro_a = CentroCompetencia.objects.create(codigo="centro-a", nome="Centro A")
        centro_b = CentroCompetencia.objects.create(codigo="centro-b", nome="Centro B")
        Acompanhamento.objects.create(centro=centro_a, periodo_referencia="1T/2024")
        novo = Acompanhamento.objects.create(centro=centro_b, periodo_referencia="2T/2024")
        assert panel.acompanhamento_padrao() == novo

    def test_sem_acompanhamento_devolve_none(self):
        assert panel.acompanhamento_padrao() is None


class ContextoComAcompanhamentoTestes(BasePanelTestes):
    def test_contexto_painel_prefere_o_acompanhamento_importado(self):
        from apps.planning.views import contexto_painel
        contexto = contexto_painel("todos", "fin", self.user)
        assert contexto["acompanhamento"] == self.acomp
        assert list(contexto["acompanhamentos"]) == [self.acomp]
        # Task 8: a grade reflete os valores efetivos do acompanhamento
        # (override > importado > None — ver `overrides.grade_edicao_overrides`).
        assert contexto["grade_edicao"][0]["linhas"][0]["codigo"] == "PDI"
        assert contexto["painel"]["base"] == "financeiro"
        assert contexto["geo_fonte"] and contexto["geo_ppi"]
        assert "geo_consolidado" not in contexto
        linha = next(l for l in contexto["painel"]["tabela"]["grupos"][0]["linhas"]
                     if l["rotulo"] == "PDI")
        assert linha["previsto"] == Decimal("29000000")

    def test_contexto_painel_aceita_acompanhamento_explicito(self):
        from apps.planning.views import contexto_painel
        contexto = contexto_painel("2026", "fis", self.user, self.acomp)
        assert contexto["acompanhamento"] == self.acomp
        assert contexto["painel"]["base"] == "fisico"
        assert contexto["painel"]["ano"] == 2026

    def test_contexto_pilar_usa_acompanhamento_explicito(self):
        from apps.planning.views import contexto_pilar

        pilar = Pilar.objects.get(codigo="PDI")
        contexto = contexto_pilar(pilar, "todos", "fin", self.user, self.acomp)

        assert contexto["painel_pilar"]["previsto"] == Decimal("29000000")
        assert contexto["painel_pilar"]["projetos"] == 18

    def test_pagina_pilar_respeita_acompanhamento_importado(self):
        self.client.force_login(self.user)
        pilar = Pilar.objects.get(codigo="PDI")
        resposta = self.client.get(
            f"/pilar/{pilar.pk}/",
            {"acompanhamento": str(self.acomp.pk)},
        )

        assert resposta.status_code == 200
        assert resposta.context["painel_pilar"]["previsto"] == Decimal("29000000")
        assert resposta.context["painel_pilar"]["projetos"] == 18
        assert 'data-testid="pilar-projetos"' in resposta.content.decode()
        assert "Projetos financeiros" in resposta.content.decode()
        assert "18" in resposta.content.decode()
        assert "R$ 29 mi" in resposta.content.decode()
        assert "R$ 29.000.000 mi" not in resposta.content.decode()

    def test_controles_do_pilar_preservam_acompanhamento_selecionado(self):
        self.client.force_login(self.user)
        pilar = Pilar.objects.get(codigo="PDI")
        conteudo = self.client.get(
            f"/pilar/{pilar.pk}/",
            {"acompanhamento": str(self.acomp.pk)},
        ).content.decode()

        assert f'name="acompanhamento" value="{self.acomp.pk}"' in conteudo
        assert f"base=fin&acompanhamento={self.acomp.pk}" in conteudo
        assert f"base=fis&acompanhamento={self.acomp.pk}" in conteudo
        assert f"pilar={pilar.pk}&acompanhamento={self.acomp.pk}" in conteudo

    def test_pagina_pilar_sem_parametro_usa_acompanhamento_mais_recente(self):
        self.client.force_login(self.user)
        pilar = Pilar.objects.get(codigo="PDI")
        resposta = self.client.get(f"/pilar/{pilar.pk}/")

        assert resposta.status_code == 200
        assert resposta.context["acompanhamento"] == self.acomp
        assert resposta.context["painel_pilar"]["previsto"] == Decimal("29000000")


class PainelViewTestes(BasePanelTestes):
    def test_dashboard_oferece_seletor_de_acompanhamento(self):
        self.client.force_login(self.user)
        resposta = self.client.get("/")
        assert resposta.status_code == 200
        assert resposta.context["acompanhamento"] == self.acomp
        assert 'data-testid="acompanhamento-select"' in resposta.content.decode()

    def test_dashboard_aplica_o_acompanhamento_escolhido(self):
        self.client.force_login(self.user)
        resposta = self.client.get("/", {"acompanhamento": str(self.acomp.pk)})
        assert resposta.status_code == 200
        assert resposta.context["acompanhamento"] == self.acomp
        conteudo = resposta.content.decode()
        assert f'value="{self.acomp.pk}" selected' in conteudo
        # os links de base e de exportação propagam a seleção (deep-link)
        assert f"&acompanhamento={self.acomp.pk}" in conteudo

    def test_dashboard_rejeita_acompanhamento_desconhecido(self):
        self.client.force_login(self.user)
        for pk in (str(self.acomp.pk + 999), "abc"):
            with self.subTest(pk=pk):
                resposta = self.client.get("/", {"acompanhamento": pk})
                assert resposta.status_code == 404

    def test_ano_sem_executado_renderiza_traco_nunca_zero_porcento(self):
        # Review Focus #4 no render: 2026 (físico) só tem projeção.
        self.client.force_login(self.user)
        conteudo = self.client.get("/", {"ano": "2026", "base": "fis"}).content.decode()
        assert ">—<" in conteudo
        assert ">0%<" not in conteudo
        assert 'rotulo="0%"' not in conteudo

    def test_pagina_do_pilar_continua_legada_sem_seletor(self):
        self.client.force_login(self.user)
        pilar = Pilar.objects.get(codigo="PDI")
        conteudo = self.client.get(f"/pilar/{pilar.pk}/").content.decode()
        assert 'data-testid="acompanhamento-select"' not in conteudo

    def test_dashboard_sem_acompanhamento_nao_mostra_seletor(self):
        Acompanhamento.objects.all().delete()
        self.client.force_login(self.user)
        resposta = self.client.get("/")
        assert resposta.status_code == 200
        assert resposta.context["acompanhamento"] is None
        assert 'data-testid="acompanhamento-select"' not in resposta.content.decode()


# ---------------------------------------------------------------------------
# Ruling 25: exports CSV/HTML refletem a mesma fonte do painel da tela.
# ---------------------------------------------------------------------------

class ExportacoesComAcompanhamentoTestes(BasePanelTestes):
    def _semear_plano_diferente(self):
        """PlanoAnual com valores distintos — não pode vazar para as exportações."""
        pilar = Pilar.objects.get(codigo="PDI")
        PlanoAnual.objects.create(ano=2024, pilar=pilar, base="financeiro",
                                  previsto=Decimal("123456.78"), executado=Decimal("999999.99"))

    def test_csv_exporta_os_numeros_importados(self):
        from django.urls import reverse
        self._semear_plano_diferente()
        self.client.force_login(self.user)
        resposta = self.client.get(reverse("planning:csv"), {
            "ano": "todos", "base": "fin", "acompanhamento": str(self.acomp.pk)})
        assert resposta.status_code == 200
        conteudo = resposta.content.decode()
        assert "29.000.000" in conteudo       # PDI previsto (recurso_ou_meta, TAB. 1)
        assert "17.675.109,56" in conteudo    # PDI executado (realizado, TAB. 1)
        assert "5.616.700" in conteudo        # AT captado (TAB. 9)
        assert "123.456,78" not in conteudo   # PlanoAnual semeado não vaza
        assert "999.999,99" not in conteudo

    def test_html_standalone_exporta_os_numeros_importados(self):
        from django.urls import reverse
        self._semear_plano_diferente()
        self.client.force_login(self.user)
        resposta = self.client.get(reverse("planning:export_html"), {
            "ano": "todos", "base": "fin", "acompanhamento": str(self.acomp.pk)})
        assert resposta.status_code == 200
        conteudo = resposta.content.decode()
        assert "34.975.229,95" in conteudo
        assert "123.456,78" not in conteudo
        assert "999.999,99" not in conteudo

    def test_exportacoes_sem_parametro_usam_o_mais_recente(self):
        from django.urls import reverse
        self.client.force_login(self.user)
        for url in (reverse("planning:csv"), reverse("planning:export_html")):
            with self.subTest(url=url):
                resposta = self.client.get(url, {"ano": "todos", "base": "fin"})
                assert resposta.status_code == 200
                assert "29.000.000" in resposta.content.decode()  # PDI importado

    def test_exportacoes_rejeitam_acompanhamento_desconhecido(self):
        from django.urls import reverse
        self.client.force_login(self.user)
        for url in (reverse("planning:csv"), reverse("planning:export_html")):
            for pk in ("abc", str(self.acomp.pk + 999)):
                with self.subTest(url=url, pk=pk):
                    resposta = self.client.get(
                        url, {"ano": "todos", "base": "fin", "acompanhamento": pk})
                    assert resposta.status_code == 404

    def test_csv_do_pilar_reflete_o_acompanhamento_importado(self):
        # O recorte exportado deve usar a mesma fonte da página do pilar.
        from django.urls import reverse
        self._semear_plano_diferente()
        self.client.force_login(self.user)
        pilar = Pilar.objects.get(codigo="PDI")
        resposta = self.client.get(reverse("planning:csv"), {
            "ano": "todos", "base": "fin", "pilar": str(pilar.pk),
            "acompanhamento": str(self.acomp.pk)})
        assert resposta.status_code == 200
        conteudo = resposta.content.decode()
        assert "29.000.000" in conteudo
        assert "123.456,78" not in conteudo

    def test_html_do_pilar_respeita_acompanhamento_selecionado(self):
        from django.urls import reverse
        outro = Acompanhamento.objects.create(
            centro=self.acomp.centro, periodo_referencia="3T/2024"
        )
        ResumoFinanceiro.objects.create(
            acompanhamento=outro,
            origem="TAB. 1",
            pilar=Pilar.objects.get(codigo="PDI"),
            recurso_ou_meta=Decimal("99"),
            realizado=Decimal("11"),
        )
        self.client.force_login(self.user)
        pilar = Pilar.objects.get(codigo="PDI")
        resposta = self.client.get(reverse("planning:export_html"), {
            "ano": "todos", "base": "fin", "pilar": str(pilar.pk),
            "acompanhamento": str(self.acomp.pk),
        })

        assert resposta.status_code == 200
        conteudo = resposta.content.decode()
        assert "29.000.000" in conteudo
        assert "R$ 99" not in conteudo


class ExportacoesLegadasTestes(TestCase):
    def test_exportacoes_sem_acompanhamento_usam_plano_anual(self):
        from django.urls import reverse
        garantir_grupos()
        user = adicionar_grupo(
            get_user_model().objects.create_user(username="legexp", password="x"), "Master")
        pilar = Pilar.objects.create(codigo="PDI", nome="PDI", ordem=1)
        PlanoAnual.objects.create(ano=2024, pilar=pilar, base="financeiro",
                                  previsto=Decimal("123456.78"), executado=Decimal("999999.99"))
        self.client.force_login(user)
        for url in (reverse("planning:csv"), reverse("planning:export_html")):
            with self.subTest(url=url):
                resposta = self.client.get(url, {"ano": "todos", "base": "fin"})
                assert resposta.status_code == 200
                conteudo = resposta.content.decode()
                assert "123.456,78" in conteudo
                assert "999.999,99" in conteudo
