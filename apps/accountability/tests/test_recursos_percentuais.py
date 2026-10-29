"""Indicadores de recursos do PE pertencem à apresentação financeira das fontes."""
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.overview_period import resolver_periodo
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.pillars.models import Pilar, UsuarioPilar
from apps.planning.views import contexto_pilar, _html_standalone

from .. import overrides, services
from ..models import Acompanhamento, KpiAcompanhamento, OverrideAcompanhamento
from .fixtures_financeiro import FINANCEIRO


class RecursosPercentuaisTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        garantir_grupos()
        cls.master = adicionar_grupo(get_user_model().objects.create_user(username="recursos-master"), "Master")
        cls.pilares = {c: Pilar.objects.get_or_create(codigo=c, defaults={"nome": c})[0]
                       for c in ("PDI", "FORMACAO", "STARTUPS", "INFRA", "AT", "OUTRASFONTES")}
        services.ingestar("FINANCEIRO_GERAL", FINANCEIRO, "Recursos", "3T/2026", cls.master)
        services.ingestar("INDICADORES_PE", FINANCEIRO.with_name(
            "Indicadores Gerais do Termo de Retificação do PE.xlsx"), "Recursos", "3T/2026", cls.master)
        cls.acomp = Acompanhamento.objects.get(centro__nome="Recursos")

    def contexto(self, base="fin", usuario=None, periodo=None):
        return contexto_pilar(self.pilares["AT"], "todos", base, usuario or self.master, self.acomp, periodo)

    def visitar(self, base="fin", usuario=None, **params):
        self.client.force_login(usuario or self.master)
        return self.client.get(reverse("core:pilar", args=[self.pilares["AT"].pk]),
                               {"base": base, "acompanhamento": self.acomp.pk, **params})

    def enviar(self, base="fin", usuario=None, **campos):
        self.client.force_login(usuario or self.master)
        return self.client.post(reverse("planning:aplicar"), {
            "edicao_dashboard": "1", "base": base, "pilar": self.pilares["AT"].pk,
            "acompanhamento": self.acomp.pk, "ano": "todos", **campos})

    def focal(self, codigo):
        usuario = adicionar_grupo(get_user_model().objects.create_user(username=f"recursos-{codigo}"), "PontoFocal")
        UsuarioPilar.objects.create(usuario=usuario, pilar=self.pilares[codigo])
        return usuario

    def test_financeiro_preserva_percentuais_anos_e_resumo_monetario(self):
        resposta = self.visitar()
        pp = resposta.context["painel_pilar"]
        blocos = {b["codigo"]: b for b in pp["blocos_recursos_percentuais"]}
        self.assertEqual(set(blocos), {"AT", "OUTRASFONTES"})
        for codigo, meta, executado, saldo, meta2024, realizado2024 in (
            ("AT", "55,49%", "0,51%", "54,98%", "5,34%", "0,21%"),
            ("OUTRASFONTES", "62,51%", "0,16%", "62,35%", "0,29%", "0,16%"),
        ):
            b = blocos[codigo]
            self.assertEqual((b["meta_fmt"], b["valor_fmt"], b["saldo_fmt"]), (meta, executado, saldo))
            self.assertEqual(len(b["tabela"]), 5)
            self.assertEqual((b["tabela"][0]["previsto_fmt"], b["tabela"][0]["executado_fmt"]),
                             (meta2024, realizado2024))
            self.assertEqual(b["faixa"], "critica")
            self.assertContains(resposta, b["titulo_indicador"])
        self.assertEqual(pp["total_captacao"]["realizado"], D("462709"))
        self.assertEqual(len(pp["blocos_cards_financeiros"]), 2)

    def test_fisico_mantem_empresas_e_entregaveis_sem_recursos(self):
        resposta = self.visitar("fis")
        pp = resposta.context["painel_pilar"]
        self.assertEqual([b["unidade_indicador"] for b in pp["blocos_fisicos"]], ["Número absoluto"])
        self.assertEqual(len(pp["cards_overview"]), 1)
        self.assertEqual(pp["status_counts"]["com_meta"], 1)
        linhas = [l for g in pp["tabela_gerencial_fisica"]["grupos"] for l in g["linhas"]]
        self.assertEqual([l["codigo"] for l in linhas], ["PE-03"])
        self.assertContains(resposta, "Empresas associadas · número absoluto")
        self.assertContains(resposta, "Entregáveis da AT")
        self.assertNotContains(resposta, "Recursos de empresas da Associação · percentual")
        self.assertNotContains(resposta, "Recursos de outras fontes · percentual")
        self.assertNotContains(resposta, "v__0__fisico__PE-04__previsto")
        self.assertNotContains(resposta, "v__0__fisico__PE-02__previsto")

    def test_autorizacao_restringe_fontes_e_editor(self):
        for codigo, kpi in (("AT", "PE-04"), ("OUTRASFONTES", "PE-02")):
            user = self.focal(codigo)
            contexto = self.contexto(usuario=user)
            self.assertEqual([b["codigo"] for b in contexto["painel_pilar"]["blocos_recursos_percentuais"]], [codigo])
            nomes = [c["nome"] for b in contexto["grade_edicao_geral"] for l in b["linhas"] for c in l["celulas"]]
            self.assertIn(f"v__0__fisico__{kpi}__previsto", nomes)
            self.assertNotIn("v__0__fisico__PE-03__previsto", nomes)
            fisico = self.contexto("fis", user)["painel_pilar"]
            self.assertEqual(len(fisico["blocos_fisicos"]), 1 if codigo == "AT" else 0)

    def test_edicao_no_financeiro_preserva_fracao_e_auditoria_original(self):
        self.assertEqual(self.enviar(**{"v__2024__fisico__PE-04__executado": "0.42",
                                       "v__0__financeiro__AT__meta_captacao": "8000000"}).status_code, 302)
        ajuste = OverrideAcompanhamento.objects.get(acompanhamento=self.acomp, chave="fis|PE-04|2024|executado")
        self.assertEqual(ajuste.valor, D("0.0042"))
        at = next(b for b in self.contexto()["painel_pilar"]["blocos_recursos_percentuais"] if b["codigo"] == "AT")
        self.assertEqual(at["tabela"][0]["executado_fmt"], "0,42%")
        original = KpiAcompanhamento.objects.get(acompanhamento=self.acomp, codigo="PE-04")
        self.assertEqual(original.executado_2024, D("0.0021"))
        self.assertEqual(self.enviar(**{"v__2024__fisico__PE-04__executado": ""}).status_code, 302)
        self.assertFalse(OverrideAcompanhamento.objects.filter(pk=ajuste.pk).exists())

    def test_somente_outras_fontes_no_fisico_indica_destino_sem_tabela_vazia(self):
        resposta = self.visitar("fis", self.focal("OUTRASFONTES"))
        self.assertContains(resposta, "Os indicadores de recursos de Outras fontes estão na base")
        self.assertNotContains(resposta, 'data-testid="gerencial-accordion"')
        self.assertNotContains(resposta, 'data-testid="editor-dados"')

    def test_auditor_consulta_os_dois_quadros_sem_editor(self):
        auditor = adicionar_grupo(get_user_model().objects.create_user(username="recursos-auditor"), "Auditor")
        resposta = self.visitar(usuario=auditor)
        self.assertContains(resposta, "Recursos de empresas da Associação · percentual")
        self.assertContains(resposta, "Recursos de outras fontes · percentual")
        self.assertNotContains(resposta, 'data-testid="editor-dados"')

    def test_edicao_rejeita_indicadores_da_outra_base_ou_fonte(self):
        for base, campo in (("fis", "v__2024__fisico__PE-04__executado"),
                            ("fin", "v__2024__fisico__PE-03__executado"),
                            ("fis", "v__0__financeiro__AT__executado")):
            self.assertEqual(self.enviar(base, **{campo: "1"}).status_code, 403)
        self.assertEqual(self.enviar(usuario=self.focal("AT"), **{
            "v__2024__fisico__PE-02__executado": "1"}).status_code, 403)
        self.assertFalse(OverrideAcompanhamento.objects.filter(acompanhamento=self.acomp).exists())

    def test_restauracao_respeita_base_visivel_e_fonte(self):
        overrides.aplicar_overrides(self.acomp, "fisico", [
            (2024, "PE-04", "executado", D("0.0042")),
            (2024, "PE-02", "executado", D("0.0042")),
            (2024, "PE-03", "executado", D("5"))], self.master)
        overrides.aplicar_overrides(self.acomp, "financeiro", [(0, "AT", "executado", D("123"))], self.master)
        # Ponto focal propõe pela Operação; restauração direta é exclusiva do gestor.
        antes = set(OverrideAcompanhamento.objects.filter(acompanhamento=self.acomp).values_list("chave", flat=True))
        self.assertEqual(self.enviar(usuario=self.focal("AT"), acao="restaurar").status_code, 403)
        self.assertEqual(antes, set(OverrideAcompanhamento.objects.filter(acompanhamento=self.acomp).values_list("chave", flat=True)))
        self.enviar(acao="restaurar")
        chaves = set(OverrideAcompanhamento.objects.filter(acompanhamento=self.acomp).values_list("chave", flat=True))
        self.assertEqual(chaves, {"fis|PE-03|2024|executado"})
        self.enviar("fis", acao="restaurar")
        self.assertEqual(list(OverrideAcompanhamento.objects.filter(acompanhamento=self.acomp).values_list("chave", flat=True)),
                         [])

    def test_csv_e_html_exportam_recursos_no_financeiro(self):
        self.client.force_login(self.master)
        for base in ("fin", "fis"):
            resposta = self.client.get(reverse("planning:csv"), {
                "base": base, "pilar": self.pilares["AT"].pk, "acompanhamento": self.acomp.pk})
            self.assertEqual(resposta.status_code, 200)
            csv = resposta.content.decode("utf-8-sig")
            html = _html_standalone("todos", base, self.master, pilar=self.pilares["AT"], acompanhamento=self.acomp)
            if base == "fin":
                self.assertIn("Recursos de empresas da Associação · percentual", csv)
                self.assertIn("Recursos de outras fontes · percentual", csv)
                self.assertIn("55,49;0,51;54,98", csv)
                self.assertIn("62,51;0,16;62,35", csv)
                self.assertIn("Recursos de outras fontes · percentual", html)
            else:
                self.assertNotIn("Percentual", csv)
                self.assertNotIn("55,49", csv)
                self.assertIn("Número absoluto", csv)
                self.assertNotIn("Recursos de outras fontes · percentual", html)

    def test_intervalo_sem_dados_nao_exibe_valores_do_ciclo(self):
        contexto = self.contexto(periodo=resolver_periodo({"mes_inicial": "2025-02", "mes_final": "2025-05"}))
        self.assertTrue(contexto["sem_dados_intervalo"])
        for b in contexto["painel_pilar"]["blocos_recursos_percentuais"]:
            self.assertEqual((b["meta_fmt"], b["valor_fmt"], b["saldo_fmt"]), ("—", "—", "—"))
            self.assertTrue(all(l["executado"] is None for l in b["tabela"]))
