"""Compatibilidade dos filtros MM/AAAA com URLs e edições existentes."""
from django.test import SimpleTestCase

from .overview_period import resolver_periodo


class PeriodoAnaliseTestes(SimpleTestCase):
    def test_mes_ano_visivel_equivale_ao_formato_das_urls(self):
        for inicio, fim in (("01/2025", "12/2025"), ("02/2025", "08/2026")):
            with self.subTest(inicio=inicio, fim=fim):
                periodo = resolver_periodo({"mes_inicial": inicio, "mes_final": fim})
                iso = {"mes_inicial": inicio[3:] + "-" + inicio[:2],
                       "mes_final": fim[3:] + "-" + fim[:2]}
                self.assertEqual(periodo, resolver_periodo(iso))

    def test_campos_vazios_preservam_ciclo_completo(self):
        periodo = resolver_periodo({"mes_inicial": "", "mes_final": ""})
        self.assertTrue(periodo["ciclo"])
        self.assertEqual(periodo["mes_inicial"], "")
        self.assertEqual(periodo["mes_final"], "")

    def test_mes_invalido_e_intervalo_invertido_sao_rejeitados(self):
        for inicio, fim in (("13/2025", "12/2026"), ("08/2026", "02/2025")):
            with self.subTest(inicio=inicio, fim=fim):
                periodo = resolver_periodo({"mes_inicial": inicio, "mes_final": fim})
                self.assertFalse(periodo["valido"])
                self.assertTrue(periodo["erro"])
