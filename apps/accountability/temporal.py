"""Agregações temporais dos lançamentos financeiros importados."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from apps.planning.services import ANOS

from .models import DespesaAcompanhamento

FONTES_TEMPORAIS = ("ppi", "at", "at_lei_tics", "outras")
TIPO_RECURSO_FONTE = {
    "EMBRAPII": "ppi",
    "AT": "at",
    "AT_LEI_TICS": "at_lei_tics",
    "OUTRAS_FONTES": "outras",
}


def data_efetiva(despesa: DespesaAcompanhamento) -> date | None:
    """Retorna a melhor data de execução disponível para um lançamento."""
    return despesa.data_pagamento or despesa.data_nota or despesa.data_movimento


def agregar_despesas_por_ano(acompanhamento) -> dict:
    """Agrupa lançamentos datados por fonte e ano, sem inventar períodos.

    A soma usa ``data_pagamento`` como fonte primária, com fallback para data da
    nota e, por último, data do movimento. A ausência de data permanece
    contabilizada em ``linhas_sem_data`` e não é atribuída a nenhum ano.
    """
    fontes = {
        fonte: {ano: None for ano in ANOS}
        for fonte in FONTES_TEMPORAIS
    }
    pilares: dict[tuple[str, int], Decimal] = {}
    pilares_por_fonte = {fonte: {} for fonte in FONTES_TEMPORAIS}
    fontes_com_dados: set[str] = set()
    despesas = DespesaAcompanhamento.objects.filter(
        acompanhamento=acompanhamento
    ).select_related("pilar")
    linhas = 0
    linhas_sem_data = 0

    for despesa in despesas:
        linhas += 1
        data = data_efetiva(despesa)
        if data is None:
            linhas_sem_data += 1
            continue
        ano = data.year
        fonte = TIPO_RECURSO_FONTE.get(despesa.tipo_recurso)
        if fonte is None or ano not in ANOS or despesa.valor is None:
            continue
        valor = Decimal(despesa.valor)
        fontes[fonte][ano] = (fontes[fonte][ano] or Decimal("0")) + valor
        fontes_com_dados.add(fonte)
        chave = (despesa.pilar.codigo, ano)
        pilares[chave] = pilares.get(chave, Decimal("0")) + valor
        por_fonte = pilares_por_fonte[fonte]
        por_fonte[chave] = por_fonte.get(chave, Decimal("0")) + valor

    for fonte in fontes_com_dados:
        fontes[fonte] = {
            ano: (valor if valor is not None else Decimal("0"))
            for ano, valor in fontes[fonte].items()
        }

    return {
        "fontes": fontes,
        "pilares": pilares,
        "pilares_por_fonte": pilares_por_fonte,
        "linhas": linhas,
        "linhas_sem_data": linhas_sem_data,
        "fontes_com_dados": fontes_com_dados,
    }
