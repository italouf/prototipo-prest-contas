"""Cumprimento de metas físicas: excedentes não compensam outras metas."""
from decimal import Decimal, ROUND_DOWN


def percentual_fisico(executado, previsto):
    if executado is None or previsto is None or previsto <= 0:
        return None
    return min(max(Decimal(executado) / Decimal(previsto) * 100, Decimal(0)), Decimal(100))


def saldo_fisico(previsto, executado):
    if previsto is None or executado is None:
        return None
    return max(previsto - executado, Decimal(0))


def resumo_fisico(pares):
    """Média dos percentuais individuais, com o mesmo peso por indicador.

    Unidades diferentes podem compor a média normalizada; seus valores
    absolutos não são somados. Dados ausentes ficam fora da média e são
    informados pela cobertura (com_dados / com_meta).
    """
    from .services import faixa

    pares = list(pares)
    percentuais = [percentual_fisico(executado, previsto) for previsto, executado in pares]
    disponiveis = [valor for valor in percentuais if valor is not None]
    media = sum(disponiveis, Decimal(0)) / len(disponiveis) if disponiveis else None
    return {
        "resumo_indicadores": True,
        "pct": media.quantize(Decimal("0.1"), rounding=ROUND_DOWN) if media is not None else None,
        "faixa": faixa(media),
        "barra": media if media is not None else 0,
        "atingidos": sum(valor == 100 for valor in disponiveis),
        "ok": sum(valor >= 90 for valor in disponiveis),
        "parcial": sum(50 <= valor < 90 for valor in disponiveis),
        "critica": sum(valor < 50 for valor in disponiveis),
        "neutra": len(percentuais) - len(disponiveis),
        "com_meta": sum(previsto is not None and previsto > 0 for previsto, _ in pares),
        "com_dados": len(disponiveis),
    }
