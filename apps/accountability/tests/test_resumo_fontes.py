from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.overview_period import resolver_periodo
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.pillars.models import Pilar, UsuarioPilar
from apps.planning.views import contexto_pilar, _html_standalone

from .. import services
from ..models import Acompanhamento, ResumoFinanceiro
from .fixtures_financeiro import FINANCEIRO


class ResumoFinanceiroFontesTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        garantir_grupos()
        cls.user = adicionar_grupo(get_user_model().objects.create_user(username="resumo-fontes"), "Master")
        cls.pilares = {c: Pilar.objects.get_or_create(codigo=c, defaults={"nome": c})[0] for c in ("PDI", "FORMACAO", "STARTUPS", "INFRA", "AT", "OUTRASFONTES")}
        services.ingestar("FINANCEIRO_GERAL", FINANCEIRO, "Resumo fontes", "3T/2026", cls.user)
        cls.acomp = Acompanhamento.objects.get(centro__nome="Resumo fontes")

    def contexto(self, user=None, periodo=None):
        return contexto_pilar(self.pilares["AT"], "todos", "fin", user or self.user, self.acomp, periodo)

    def test_meta_e_diferenca_usam_captacao_at_e_execucao_outras(self):
        contexto = self.contexto()
        pp = contexto["painel_pilar"]
        at, outras = pp["blocos_cards_financeiros"]
        self.assertEqual([c["titulo"] for c in at["cards"]], ["Meta de captação do recurso", "Recurso captado total", "Diferença captação"])
        self.assertEqual([c["titulo"] for c in outras["cards"]], ["Meta de execução dos recursos", "Recurso executado total", "Diferença execução"])
        self.assertEqual([c["valor"] for c in at["cards"]], ["R$ 7,75", "R$ 5,62", "R$ 2,13"])
        self.assertEqual([c["valor"] for c in outras["cards"]], ["R$ 6,30", "R$ 242,11", "R$ 6,06"])
        self.assertEqual(outras["cards"][1]["unidade"], "mil")
        self.assertEqual(outras["cards"][1]["pct"], D("242112") / D("6300000") * 100)
        self.assertEqual(pp["total_captacao"]["captado"], D("15843468"))
        self.assertEqual(pp["total_captacao"]["realizado"], D("462709"))
        html = _html_standalone("todos", "fin", self.user, pilar=self.pilares["AT"], acompanhamento=self.acomp)
        self.assertIn('data-testid="resumo-financeiro-AT"', html)
        self.assertIn('data-testid="resumo-financeiro-OUTRASFONTES"', html)
        self.assertIn('class="overview-table pillar-capture-table"', html)

    def test_diferenca_negativa_indica_superacao_e_barra_limita_em_100(self):
        ResumoFinanceiro.objects.filter(acompanhamento=self.acomp, pilar=self.pilares["AT"]).update(recurso_ou_meta=D("100"), captado=D("120"))
        at = self.contexto()["painel_pilar"]["blocos_cards_financeiros"][0]
        self.assertEqual(at["cards"][2]["valor"], "R$ -20")
        self.assertEqual(at["cards"][2]["descricao"], "meta superada")
        self.assertEqual(at["cards"][1]["pct"], D("120"))
        self.assertEqual(at["cards"][1]["barra"], D("100"))

    def test_fonte_restrita_e_intervalo_sem_dados(self):
        user = adicionar_grupo(get_user_model().objects.create_user(username="resumo-somente-at"), "PontoFocal")
        UsuarioPilar.objects.create(usuario=user, pilar=self.pilares["AT"])
        blocos = self.contexto(user)["painel_pilar"]["blocos_cards_financeiros"]
        self.assertEqual([b["codigo"] for b in blocos], ["AT"])
        contexto = self.contexto(periodo=resolver_periodo({"mes_inicial": "2025-01", "mes_final": "2025-12"}))
        self.assertTrue(contexto["sem_dados_intervalo"])
        self.assertTrue(all(c["valor"] == "—" for c in contexto["painel_pilar"]["cards_overview"]))
        self.assertTrue(all(b["cards"][1]["pct"] is None for b in contexto["painel_pilar"]["blocos_cards_financeiros"]))
