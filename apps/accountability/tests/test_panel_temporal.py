from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.pillars.models import Pilar

from .. import panel
from ..models import (
    Acompanhamento,
    CentroCompetencia,
    DespesaAcompanhamento,
    ResumoFinanceiro,
)


class PainelTemporalTestes(TestCase):
    def setUp(self):
        self.pilares = {
            codigo: Pilar.objects.create(codigo=codigo, nome=codigo, ordem=indice)
            for indice, codigo in enumerate(
                ("PDI", "FORMACAO", "STARTUPS", "INFRA", "AT", "OUTRASFONTES"),
                start=1,
            )
        }
        centro = CentroCompetencia.objects.create(codigo="centro", nome="Centro")
        self.acomp = Acompanhamento.objects.create(
            centro=centro, periodo_referencia="2T/2024"
        )

    def _despesa(self, linha, pilar, tipo_recurso, valor, **datas):
        DespesaAcompanhamento.objects.create(
            acompanhamento=self.acomp,
            aba="3. Conta Ação - AFCCT",
            linha=linha,
            pilar=self.pilares[pilar],
            tipo_recurso=tipo_recurso,
            valor=Decimal(valor),
            **datas,
        )

    def test_painel_financeiro_usa_lancamentos_datados_no_ano(self):
        self._despesa(1, "PDI", "EMBRAPII", "100", data_pagamento=date(2024, 4, 1))
        self._despesa(2, "FORMACAO", "EMBRAPII", "200", data_pagamento=date(2025, 4, 1))
        self._despesa(3, "AT", "AT", "30", data_pagamento=date(2026, 4, 1))
        self._despesa(4, "OUTRASFONTES", "OUTRAS_FONTES", "50", data_pagamento=date(2027, 4, 1))

        painel = panel.painel_acompanhamento(None, "financeiro", self.acomp)
        ppi = painel["graficos"]["ppi"]["serie_executado"]
        at = painel["graficos"]["at"]["serie_executado"]
        outras = painel["graficos"]["outras"]["serie_executado"]

        assert ppi[:4] == [Decimal("100"), Decimal("200"), Decimal("0"), Decimal("0")]
        assert at[:4] == [Decimal("0"), Decimal("0"), Decimal("30"), Decimal("0")]
        assert outras[:4] == [Decimal("0"), Decimal("0"), Decimal("0"), Decimal("50")]
        assert painel["consolidado"]["series"][0]["valores"][:4] == ppi[:4]

        painel_2024 = panel.painel_acompanhamento(2024, "financeiro", self.acomp)
        linha_pdi = next(
            linha
            for linha in painel_2024["tabela"]["grupos"][0]["linhas"]
            if linha["rotulo"] == "PDI"
        )
        assert linha_pdi["executado"] == Decimal("100")

    def test_graficos_separam_anos_do_acumulado(self):
        ResumoFinanceiro.objects.create(
            acompanhamento=self.acomp,
            origem="TAB. 1",
            pilar=self.pilares["PDI"],
            recurso_ou_meta=Decimal("600"),
            realizado=Decimal("300"),
        )

        painel = panel.painel_acompanhamento(None, "financeiro", self.acomp)
        bloco = painel["graficos"]["ppi"]

        assert len(bloco["serie_previsto"]) == 4
        assert len(bloco["serie_executado"]) == 4
        assert bloco["acumulado_previsto"] == Decimal("600")
        assert bloco["acumulado_executado"] == Decimal("300")

    def test_lei_tics_nao_entra_na_serie_da_at(self):
        DespesaAcompanhamento.objects.create(
            acompanhamento=self.acomp,
            aba="3. Conta Ação - AFCCT",
            linha=1,
            pilar=self.pilares["AT"],
            tipo_recurso="AT",
            valor=Decimal("30"),
            data_pagamento=date(2026, 4, 1),
        )
        DespesaAcompanhamento.objects.create(
            acompanhamento=self.acomp,
            aba="6.1 Conta Ação - AT (Lei TICs)",
            linha=2,
            pilar=self.pilares["AT"],
            tipo_recurso="AT_LEI_TICS",
            valor=Decimal("40"),
            data_pagamento=date(2026, 4, 1),
        )

        painel = panel.painel_acompanhamento(None, "financeiro", self.acomp)

        assert painel["graficos"]["at"]["serie_executado"] == [
            Decimal("0"), Decimal("0"), Decimal("30"), Decimal("0")
        ]
