from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.pillars.models import Pilar

from ..models import Acompanhamento, CentroCompetencia, DespesaAcompanhamento
from ..temporal import agregar_despesas_por_ano


class AgregacaoTemporalTestes(TestCase):
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

    def despesa(self, *, pilar, tipo_recurso, valor, **datas):
        return DespesaAcompanhamento.objects.create(
            acompanhamento=self.acomp,
            aba="3. Conta Ação - AFCCT",
            linha=DespesaAcompanhamento.objects.count() + 1,
            pilar=self.pilares[pilar],
            tipo_recurso=tipo_recurso,
            valor=Decimal(valor),
            **datas,
        )

    def test_agrega_por_data_efetiva_e_segrega_lei_tics(self):
        self.despesa(
            pilar="PDI",
            tipo_recurso="EMBRAPII",
            valor="100",
            data_pagamento=date(2024, 4, 1),
            data_nota=date(2025, 4, 1),
        )
        self.despesa(
            pilar="FORMACAO",
            tipo_recurso="EMBRAPII",
            valor="50",
            data_nota=date(2025, 4, 1),
        )
        self.despesa(
            pilar="AT",
            tipo_recurso="AT",
            valor="30",
            data_movimento=date(2026, 2, 1),
        )
        self.despesa(
            pilar="AT",
            tipo_recurso="AT_LEI_TICS",
            valor="40",
            data_pagamento=date(2026, 3, 1),
        )
        self.despesa(
            pilar="OUTRASFONTES",
            tipo_recurso="OUTRAS_FONTES",
            valor="70",
            data_pagamento=date(2027, 1, 1),
        )
        self.despesa(
            pilar="INFRA",
            tipo_recurso="EMBRAPII",
            valor="9",
        )

        resultado = agregar_despesas_por_ano(self.acomp)

        assert resultado["fontes"]["ppi"] == {
            2024: Decimal("100"),
            2025: Decimal("50"),
            2026: Decimal("0"),
            2027: Decimal("0"),
        }
        assert resultado["fontes"]["at"] == {
            2024: Decimal("0"),
            2025: Decimal("0"),
            2026: Decimal("30"),
            2027: Decimal("0"),
        }
        assert resultado["fontes"]["at_lei_tics"][2026] == Decimal("40")
        assert resultado["fontes"]["outras"][2027] == Decimal("70")
        assert resultado["pilares"][("PDI", 2024)] == Decimal("100")
        assert resultado["linhas"] == 6
        assert resultado["linhas_sem_data"] == 1
        assert resultado["fontes_com_dados"] == {"ppi", "at", "at_lei_tics", "outras"}
