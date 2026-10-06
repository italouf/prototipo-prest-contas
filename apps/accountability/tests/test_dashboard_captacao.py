"""Painel combinado, autorização por fonte e ocultação do dashboard INFRA."""
import csv
import io
from datetime import date
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.permissions import (
    adicionar_grupo, garantir_grupos, usuario_pode_pilar,
)
from apps.indicators.models import Indicador
from apps.periods.models import Periodo
from apps.pillars.models import Pilar, UsuarioPilar
from apps.planning.models import PlanoAnual
from apps.planning.views import contexto_pilar

from .. import overrides, panel, services
from ..models import Acompanhamento, OverrideAcompanhamento, ResumoFinanceiro
from .fixtures_financeiro import FINANCEIRO


class DashboardCaptacaoTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        garantir_grupos()
        cls.pilares = {
            codigo: Pilar.objects.create(codigo=codigo, nome=nome, ordem=i)
            for i, (codigo, nome) in enumerate((
                ("PDI", "PDI"), ("FORMACAO", "Formação FCRH"), ("STARTUPS", "ACS"),
                ("AT", "Associação Tecnológica"), ("INFRA", "Infraestrutura"),
                ("OUTRASFONTES", "Outras Fontes"),
            ))
        }
        cls.usuarios = {}
        for papel in ("Master", "Admin", "Lideranca", "Auditor"):
            cls.usuarios[papel] = adicionar_grupo(
                get_user_model().objects.create_user(username=f"captacao-{papel}"), papel)
        for nome, fontes in (("at", ("AT",)), ("outras", ("OUTRASFONTES",)),
                             ("ambas", ("AT", "OUTRASFONTES")), ("nenhuma", ("PDI",)),
                             ("infra", ("INFRA",))):
            usuario = adicionar_grupo(get_user_model().objects.create_user(
                username=f"captacao-{nome}"), "PontoFocal")
            cls.usuarios[nome] = usuario
            for fonte in fontes:
                UsuarioPilar.objects.create(usuario=usuario, pilar=cls.pilares[fonte])
        services.ingestar("FINANCEIRO_GERAL", FINANCEIRO, "Centro QuIIN", "2T/2024", cls.usuarios["Master"])
        indicadores = FINANCEIRO.with_name("Indicadores Gerais do Termo de Retificação do PE.xlsx")
        services.ingestar("INDICADORES_PE", indicadores, "Centro QuIIN", "2T/2024", cls.usuarios["Master"])
        cls.acomp = Acompanhamento.objects.get()
        Periodo.objects.create(competencia=date(2026, 6, 1), status="ABERTO")

    def url(self, codigo="AT"):
        return reverse("core:pilar", args=[self.pilares[codigo].pk])

    def visitar(self, usuario="Master", base="fin", **params):
        self.client.force_login(self.usuarios[usuario])
        return self.client.get(self.url(), {"base": base, "acompanhamento": self.acomp.pk, **params})

    def dto(self, fontes=("AT", "OUTRASFONTES")):
        return panel.painel_captacao(self.pilares["AT"], None, "fin", self.acomp,
                                    fontes_autorizadas=fontes)

    def test_cards_e_tabela_do_arquivo_real(self):
        resposta = self.visitar()
        self.assertEqual(resposta.status_code, 200)
        dto = resposta.context["painel_pilar"]
        self.assertEqual((dto["previsto"], dto["executado"], dto["saldo"], dto["pct"]),
                         (D("15843468"), D("462709"), D("15380759"), 3))
        self.assertEqual([c["titulo"] for c in dto["cards"]],
                         ["CAPTADO TOTAL", "REALIZADO TOTAL", "SALDO"])
        self.assertTrue(dto["cards"][0]["ocultar_progresso"])
        self.assertEqual(dto["cards"][2]["barra"], 97)
        tabela = dto["tabela_captacao"]
        self.assertEqual(len(tabela["cabecalhos"]), 8)
        self.assertEqual(len(tabela["linhas"]), 3)
        total = tabela["linhas"][-1]["celulas"]
        self.assertEqual(total[1]["valor"], D("14050000"))
        self.assertEqual(total[6]["valor"], D("15843468") / D("14050000") * 100)
        self.assertEqual(total[7]["valor"], D("462709") / D("15843468") * 100)
        self.assertContains(resposta, "AT e Outras Fontes")
        self.assertContains(resposta, 'data-testid="tbl_CaptaoATeOutros"')
        self.assertContains(resposta, "R$ 15.843.468,00")
        self.assertContains(resposta, 'style="width: 97%"')

    def test_layout_remove_elementos_anuais_mensais_e_projetos(self):
        resposta = self.visitar(ano="2026")
        for texto in ('data-testid="year-select"', 'data-testid="pilar-projetos"',
                      'data-testid="chart-fonte-pilar"', "Prestação mensal do pilar",
                      "Projetos financeiros", "Detalhamento anual", 'id="editor-dados"'):
            self.assertNotContains(resposta, texto)
        self.assertContains(resposta, 'data-testid="base-toggle"')
        self.assertEqual(resposta.context["ano_param"], "todos")
        self.assertIsNone(resposta.context["painel_pilar"]["ano"])

    def test_fontes_restritas_filtram_tabela_cards_e_totais(self):
        for usuario, codigo, captado, realizado, pct in (
            ("at", "AT", "5616700", "220597", 4),
            ("outras", "OUTRASFONTES", "10226768", "242112", 2),
        ):
            with self.subTest(usuario=usuario):
                resposta = self.visitar(usuario)
                dto = resposta.context["painel_pilar"]
                self.assertEqual((dto["previsto"], dto["executado"], dto["pct"]),
                                 (D(captado), D(realizado), pct))
                self.assertEqual(len(dto["tabela_captacao"]["linhas"]), 2)
                self.assertEqual(dto["tabela_captacao"]["linhas"][-1]["celulas"][4]["valor"], D(captado))
                self.assertFalse(usuario_pode_pilar(self.usuarios[usuario],
                                                  self.pilares["OUTRASFONTES" if codigo == "AT" else "AT"]))

    def test_vinculo_a_ambas_as_fontes_ve_total_completo(self):
        self.assertEqual(self.visitar("ambas").context["painel_pilar"]["previsto"], D("15843468"))

    def test_sem_vinculo_nao_acessa_painel_ou_downloads(self):
        self.client.force_login(self.usuarios["nenhuma"])
        self.assertEqual(self.client.get(self.url()).status_code, 403)
        for nome in ("planning:csv", "planning:export_html"):
            self.assertEqual(self.client.get(reverse(nome), {"pilar": self.pilares["AT"].pk}).status_code, 403)

    def test_navegacao_outras_fontes_tem_link_canonico_sem_ampliar_permissoes(self):
        resposta = self.visitar("outras")
        grupo = resposta.content.decode().split('id="grp-pilares"')[1].split("</ul>")[0]
        self.assertIn(f'href="{self.url()}"', grupo)
        self.assertIn("AT e Outras Fontes", grupo)
        self.assertNotIn(self.url("OUTRASFONTES"), grupo)
        self.assertNotIn("Infraestrutura", grupo)
        self.assertFalse(usuario_pode_pilar(self.usuarios["outras"], self.pilares["AT"]))

    def test_url_antiga_redireciona_preservando_parametros(self):
        self.client.force_login(self.usuarios["outras"])
        resposta = self.client.get(self.url("OUTRASFONTES"),
                                  {"ano": "2025", "base": "fis", "acompanhamento": self.acomp.pk})
        self.assertRedirects(resposta, f"{self.url()}?ano=2025&base=fis&acompanhamento={self.acomp.pk}",
                             fetch_redirect_response=False)

    def test_infra_oculta_somente_dashboard_para_todos_os_perfis(self):
        for papel in ("Master", "Admin", "Lideranca", "Auditor", "infra"):
            self.client.force_login(self.usuarios[papel])
            for base in ("fin", "fis"):
                with self.subTest(papel=papel, base=base):
                    self.assertEqual(self.client.get(self.url("INFRA"), {"base": base}).status_code, 403)
                    for nome in ("planning:csv", "planning:export_html"):
                        self.assertEqual(self.client.get(reverse(nome), {
                            "pilar": self.pilares["INFRA"].pk, "base": base}).status_code, 403)
        self.assertTrue(self.pilares["INFRA"].ativo)
        self.assertTrue(usuario_pode_pilar(self.usuarios["Master"], self.pilares["INFRA"]))

    def test_geral_preserva_linha_infra_valores_e_totais(self):
        self.client.force_login(self.usuarios["Master"])
        resposta = self.client.get(reverse("core:dashboard"), {"ano": "todos", "base": "fin"})
        self.assertEqual(resposta.status_code, 200)
        dto = resposta.context["painel"]
        self.assertEqual(dto["tabela_tab1"]["total"]["recurso"], D("60000000"))
        self.assertEqual(dto["tabela_tab1"]["total"]["realizado"], D("34975229.95"))
        infra = next(l for l in dto["tabela_tab1"]["linhas"] if l["rotulo"] == "INFRAESTRUTURA")
        self.assertEqual(infra["realizado"], D("7299414.35"))
        self.assertContains(resposta, "INFRAESTRUTURA")
        sidebar = resposta.content.decode().split('data-testid="sidebar"')[1].split("</aside>")[0]
        self.assertNotIn(self.url("INFRA"), sidebar)

    def test_drawer_infra_preserva_dados_sem_link_para_dashboard(self):
        self.client.force_login(self.usuarios["Master"])
        resposta = self.client.get(reverse("core:pilar_drawer", args=[self.pilares["INFRA"].pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, "Abrir página do pilar")

    def test_links_operacionais_infra_nao_apontam_para_dashboard_oculto(self):
        Indicador.objects.create(pilar=self.pilares["INFRA"], codigo="INFRA-BUSCA",
                                 nome="Equipamento infraestrutura", tipo="QTD")
        self.client.force_login(self.usuarios["Master"])
        for nome, filtros in (("core:mensal", {"periodo": "2026-06-01"}),
                              ("core:semestral", {"ano": "2026", "semestre": "1"}),
                              ("core:busca", {"q": "Equipamento"})):
            # Prestação e busca mantêm as informações operacionais de INFRA.
            resposta = self.client.get(reverse(nome), filtros)
            self.assertEqual(resposta.status_code, 200)
            self.assertContains(resposta, "Infraestrutura")
            self.assertNotContains(resposta, f'href="{self.url("INFRA")}"')

    def test_exports_financeiros_respeitam_escopo_e_url_antiga(self):
        for usuario in ("Master", "at", "outras"):
            self.client.force_login(self.usuarios[usuario])
            for codigo in ("AT", "OUTRASFONTES"):
                for nome in ("planning:csv", "planning:export_html"):
                    with self.subTest(usuario=usuario, codigo=codigo, nome=nome):
                        resposta = self.client.get(reverse(nome), {
                            "pilar": self.pilares[codigo].pk, "base": "fin", "ano": "2026"})
                        self.assertEqual(resposta.status_code, 200)
                        texto = resposta.content.decode("utf-8-sig")
                        self.assertIn("tbl_CaptaoATeOutros", texto)
                        if usuario == "at":
                            self.assertNotIn("10.226.768", texto)
                            self.assertNotIn("OUTRAS FONTES", texto)
                        if usuario == "outras":
                            self.assertNotIn("5.616.700", texto)
                            self.assertNotIn("ASSOCIAÇÃO TECNOLÓGICA", texto)
                        if nome == "planning:csv":
                            linhas = list(csv.reader(io.StringIO(texto), delimiter=";"))
                            self.assertEqual(len(linhas[1]), 8)

    def test_htmx_e_impressao_usam_painel_combinado(self):
        self.client.force_login(self.usuarios["outras"])
        resposta = self.client.get(self.url(), {"base": "fin"}, headers={"HX-Request": "true"})
        self.assertContains(resposta, 'hx-swap-oob="true"')
        self.assertContains(resposta, 'data-testid="tbl_CaptaoATeOutros"')
        self.assertNotContains(resposta, 'data-testid="app-header"')
        pagina = self.visitar("outras")
        cabecalho = pagina.content.decode().split('data-testid="print-cabecalho"')[1].split("</div>")[0]
        self.assertIn("AT e Outras Fontes", cabecalho)

    def test_realizado_maior_que_captado_tem_saldo_positivo_e_barras_limitadas(self):
        ResumoFinanceiro.objects.filter(origem="TAB. 9", pilar=self.pilares["AT"]).update(captado=100, realizado=150)
        dto = self.dto(("AT",))
        self.assertEqual((dto["saldo"], dto["pct"], dto["barra_percentual"]), (D(50), 150, 100))
        self.assertEqual(dto["cards"][1]["barra"], 100)
        self.assertEqual(dto["cards"][2]["barra"], 50)

    def test_valores_ausentes_e_denominador_zero_nao_fabricam_percentuais(self):
        for captado, realizado in ((None, None), (100, None), (0, 50)):
            with self.subTest(captado=captado, realizado=realizado):
                ResumoFinanceiro.objects.filter(origem="TAB. 9", pilar=self.pilares["AT"]).update(
                    captado=captado, realizado=realizado)
                dto = self.dto(("AT",))
                self.assertIsNone(dto["pct"])
                self.assertEqual(dto["barra_percentual"], 0)
                self.assertIsNone(dto["tabela_captacao"]["linhas"][-1]["celulas"][7]["valor"])

    def test_tabela_ausente_exibe_estado_vazio(self):
        ResumoFinanceiro.objects.filter(origem="TAB. 9").delete()
        resposta = self.visitar()
        dto = resposta.context["painel_pilar"]
        self.assertIsNone(dto["previsto"])
        self.assertIsNone(dto["executado"])
        self.assertEqual(dto["tabela_captacao"]["linhas"], [])
        self.assertContains(resposta, "Nenhuma informação financeira importada")

    def test_fisico_separa_fontes_e_unidades_sem_graficos(self):
        resposta = self.visitar(base="fis", ano="2024")
        blocos = resposta.context["painel_pilar"]["blocos_fisicos"]
        self.assertEqual({(b["codigo"], b["unidade_indicador"]) for b in blocos}, {
            ("AT", "Número absoluto"), ("AT", "Percentual"), ("OUTRASFONTES", "Percentual")})
        outras = next(b for b in blocos if b["codigo"] == "OUTRASFONTES")
        self.assertEqual(outras["previsto"], D("0.0029"))
        self.assertContains(resposta, 'data-testid="year-select"')
        self.assertContains(resposta, "Número absoluto")
        self.assertContains(resposta, "Percentual")
        self.assertNotContains(resposta, 'data-testid="chart-fonte-pilar"')
        self.assertNotContains(resposta, "Prestação mensal do pilar")
        self.assertNotContains(resposta, 'data-testid="pilar-projetos"')

    def test_fisico_e_editor_filtram_fontes_autorizadas(self):
        resposta = self.visitar("outras", base="fis")
        self.assertEqual({b["codigo"] for b in resposta.context["painel_pilar"]["blocos_fisicos"]}, {"OUTRASFONTES"})
        self.assertContains(resposta, "__PE-02__")
        self.assertNotContains(resposta, "__PE-03__")
        self.assertNotContains(resposta, "__PE-04__")
        self.assertTrue(resposta.context["pode_editar_pilar"])

    def test_gerencial_fisico_filtra_fontes_sem_duplicar_indicadores(self):
        for usuario, esperados in (
            ("Master", {"PE-02", "PE-03", "PE-04"}),
            ("ambas", {"PE-02", "PE-03", "PE-04"}),
            ("at", {"PE-03", "PE-04"}),
            ("outras", {"PE-02"}),
        ):
            for headers in ({}, {"HX-Request": "true"}):
                with self.subTest(usuario=usuario, headers=headers):
                    self.client.force_login(self.usuarios[usuario])
                    resposta = self.client.get(self.url(), {
                        "base": "fis", "ano": "2024", "acompanhamento": self.acomp.pk,
                    }, headers=headers)
                    self.assertEqual(resposta.status_code, 200)
                    grupos = resposta.context["painel_pilar"]["tabela_gerencial_fisica"]["grupos"]
                    linhas = [linha for grupo in grupos for linha in grupo["linhas"]]
                    self.assertEqual({r["codigo"] for r in linhas}, esperados)
                    self.assertEqual(len(linhas), len(esperados))
                    html = resposta.content.decode()
                    self.assertLess(html.index('data-testid="visao-gerencial-pilar"'),
                                    html.index('data-testid="pilar-tabela"'))
                    if "PE-02" in esperados:
                        self.assertIn("0,29%", html)
                        self.assertIn("0,16%", html)
                        self.assertIn("0,13 p.p.", html)

    def test_exports_fisicos_mantem_separacao_e_filtro(self):
        self.client.force_login(self.usuarios["outras"])
        for nome in ("planning:csv", "planning:export_html"):
            resposta = self.client.get(reverse(nome), {"pilar": self.pilares["AT"].pk, "base": "fis", "ano": "2024"})
            self.assertEqual(resposta.status_code, 200)
            texto = resposta.content.decode("utf-8-sig")
            self.assertIn("Percentual", texto)
            self.assertNotIn("Número absoluto", texto)
            self.assertNotIn("Associação Tecnológica (AT)", texto)

    def test_editor_fisico_aplica_somente_fontes_autorizadas(self):
        for usuario, codigo, status in (("outras", "PE-02", 302), ("outras", "PE-03", 403),
                                       ("Master", "PE-01", 403)):
            self.client.force_login(self.usuarios[usuario])
            resposta = self.client.post(reverse("planning:aplicar"), {
                "pilar": self.pilares["AT"].pk, "base": "fis", "ano": "2024",
                "acompanhamento": self.acomp.pk, f"v__2024__fisico__{codigo}__previsto": "1"})
            self.assertEqual(resposta.status_code, status)
        self.assertTrue(OverrideAcompanhamento.objects.filter(kpi__codigo="PE-02").exists())
        self.assertFalse(OverrideAcompanhamento.objects.filter(kpi__codigo__in=("PE-01", "PE-03")).exists())

    def test_restaurar_captacao_nao_remove_overrides_de_outros_paineis(self):
        usuario = self.usuarios["Master"]
        overrides.aplicar_overrides(self.acomp, "fisico", [(2024, "PE-02", "previsto", D(1)),
                                                           (2024, "PE-01", "previsto", D(10))], usuario)
        overrides.aplicar_overrides(self.acomp, "financeiro", [(2024, "AT", "executado", D(100))], usuario)
        self.client.force_login(usuario)
        resposta = self.client.post(reverse("planning:aplicar"), {
            "pilar": self.pilares["AT"].pk, "base": "fis", "ano": "2024",
            "acompanhamento": self.acomp.pk, "acao": "restaurar"})
        self.assertEqual(resposta.status_code, 302)
        self.assertFalse(OverrideAcompanhamento.objects.filter(kpi__codigo="PE-02").exists())
        self.assertTrue(OverrideAcompanhamento.objects.filter(kpi__codigo="PE-01").exists())
        self.assertTrue(OverrideAcompanhamento.objects.filter(base="financeiro", pilar__codigo="AT").exists())

    def test_sem_editor_financeiro_anual_e_post_rejeitado(self):
        self.client.force_login(self.usuarios["Master"])
        resposta = self.client.post(reverse("planning:aplicar"), {
            "pilar": self.pilares["AT"].pk, "base": "fin", "acompanhamento": self.acomp.pk,
            "v__2024__financeiro__AT__executado": "100"})
        self.assertEqual(resposta.status_code, 403)

    def test_fisico_legado_mantem_fontes_separadas(self):
        for codigo in ("AT", "OUTRASFONTES"):
            PlanoAnual.objects.create(pilar=self.pilares[codigo], ano=2026, base="fisico", previsto=5, executado=4)
        dto = panel.painel_captacao(self.pilares["AT"], 2026, "fis", None,
                                   fontes_autorizadas=("AT", "OUTRASFONTES"))
        self.assertEqual(len(dto["blocos_fisicos"]), 2)
        self.assertTrue(all(b["previsto"] == D(5) for b in dto["blocos_fisicos"]))

    def test_editor_fisico_legado_rejeita_campos_financeiros(self):
        self.client.force_login(self.usuarios["Master"])
        resposta = self.client.post(reverse("planning:aplicar"), {
            "pilar": self.pilares["AT"].pk, "base": "fis", "ano": "2026",
            "v__2026__financeiro__AT__executado": "100"})
        self.assertEqual(resposta.status_code, 403)
        self.assertFalse(PlanoAnual.objects.filter(pilar=self.pilares["AT"], base="financeiro").exists())

    def test_layout_dos_demais_pilares_financeiros_permanece(self):
        for codigo, nome, quantidade in (("PDI", "PDI", 18), ("FORMACAO", "FCRH", 8), ("STARTUPS", "ACS", 7)):
            self.client.force_login(self.usuarios["Master"])
            resposta = self.client.get(self.url(codigo), {"base": "fin"})
            self.assertEqual(resposta.status_code, 200)
            dto = resposta.context["painel_pilar"]
            self.assertEqual(dto["projetos"], quantidade)
            self.assertContains(resposta, f'data-testid="tbl_Visao{nome}"')
            self.assertContains(resposta, f'data-testid="tbl_Projetos{nome}"')
            self.assertNotContains(resposta, "Prestação mensal do pilar")

    def test_contexto_financeiro_nao_fornece_grade_de_fontes_invisiveis(self):
        contexto = contexto_pilar(self.pilares["AT"], "2026", "fin", self.usuarios["outras"], self.acomp)
        self.assertEqual(contexto["grade_edicao"], [])
        self.assertFalse(contexto["pode_editar_pilar"])
