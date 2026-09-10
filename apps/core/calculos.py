"""Cálculos de meta x realizado (RF-062, RF-093 / RN-002, RN-007).

Regras de cálculo:
- Percentual = realizado / meta * 100 (evitando divisão por zero).
- Meta ANUAL/ACUMULADA ou indicador acumulado usa o somatório YTD aprovado.
- Meta MENSAL usa apenas o valor do mês.
- Indicadores de texto (TXT) não possuem percentual.
"""
from decimal import Decimal

ZERO = Decimal("0")


def meta_aplicavel(indicador, competencia):
    """Meta ativa de maior versão com vigência cobrindo a competência (RF-031/RF-032)."""
    return (
        indicador.metas.filter(
            ativo=True,
            competencia_inicio__lte=competencia,
            competencia_fim__gte=competencia,
        )
        .order_by("-versao", "-competencia_inicio")
        .first()
    )


def lancamento_aprovado(indicador, periodo):
    from apps.entries.models import Lancamento

    return Lancamento.objects.filter(indicador=indicador, periodo=periodo, status="APROVADO").first()


def valor_mensal(indicador, periodo):
    """Valor aprovado do mês (RN-002)."""
    lc = lancamento_aprovado(indicador, periodo)
    if not lc:
        return None
    return lc.valor_texto if indicador.tipo == "TXT" else lc.valor_numerico


def valor_acumulado_ytd(indicador, periodo):
    """Somatório aprovado de jan/ano até o período (meta anual/acumulada)."""
    from apps.entries.models import Lancamento

    inicio = periodo.competencia.replace(month=1, day=1)
    qs = Lancamento.objects.filter(
        indicador=indicador,
        status="APROVADO",
        periodo__competencia__gte=inicio,
        periodo__competencia__lte=periodo.competencia,
    )
    return sum((l.valor_numerico or ZERO) for l in qs)


def meta_realizado_percentual(indicador, periodo):
    """Monta dict {meta, realizado, percentual, ytd, meta_obj, lc} para o indicador."""
    meta = meta_aplicavel(indicador, periodo.competencia)
    lc = lancamento_aprovado(indicador, periodo)

    if indicador.tipo == "TXT":
        return {
            "meta": None,
            "realizado": lc.valor_texto if lc else None,
            "percentual": None,
            "ytd": False,
            "meta_obj": meta,
            "lc": lc,
        }

    ytd = bool(indicador.acumulado) or (meta is not None and meta.periodicidade in ("ANUAL", "ACUMULADA"))
    realizado = valor_acumulado_ytd(indicador, periodo) if ytd else valor_mensal(indicador, periodo)
    percentual = None
    if meta is not None and meta.valor and realizado is not None:
        percentual = (realizado / meta.valor) * 100
    return {
        "meta": meta.valor if meta else None,
        "realizado": realizado,
        "percentual": percentual,
        "ytd": ytd,
        "meta_obj": meta,
        "lc": lc,
    }


def itens_do_periodo(indicadores, periodo):
    """Versão em lote de `meta_realizado_percentual` (3 queries, sem N+1).

    Usada em telas com muitos indicadores (dashboard, pilar, drawer).
    """
    from apps.entries.models import Lancamento
    from apps.indicators.models import Meta

    indicadores = list(indicadores)
    if not indicadores or periodo is None:
        return []
    ids = [i.pk for i in indicadores]

    metas = {}
    metas_qs = (
        Meta.objects.filter(
            indicador_id__in=ids,
            ativo=True,
            competencia_inicio__lte=periodo.competencia,
            competencia_fim__gte=periodo.competencia,
        )
        .order_by("indicador_id", "-versao", "-competencia_inicio")
    )
    for meta in metas_qs:
        metas.setdefault(meta.indicador_id, meta)

    lancamentos = {
        lc.indicador_id: lc
        for lc in Lancamento.objects.filter(indicador_id__in=ids, periodo=periodo, status="APROVADO")
    }

    inicio = periodo.competencia.replace(month=1, day=1)
    from django.db.models import Sum

    ytd_somas = {
        item["indicador_id"]: item["total"] or ZERO
        for item in Lancamento.objects.filter(
            indicador_id__in=ids,
            status="APROVADO",
            periodo__competencia__gte=inicio,
            periodo__competencia__lte=periodo.competencia,
        )
        .values("indicador_id")
        .annotate(total=Sum("valor_numerico"))
    }

    itens = []
    for ind in indicadores:
        meta = metas.get(ind.pk)
        lc = lancamentos.get(ind.pk)
        if ind.tipo == "TXT":
            itens.append(
                {
                    "indicador": ind,
                    "meta": None,
                    "realizado": lc.valor_texto if lc else None,
                    "percentual": None,
                    "ytd": False,
                    "meta_obj": meta,
                    "lc": lc,
                }
            )
            continue
        ytd = bool(ind.acumulado) or (meta is not None and meta.periodicidade in ("ANUAL", "ACUMULADA"))
        if ytd:
            realizado = ytd_somas.get(ind.pk, ZERO)
        else:
            realizado = lc.valor_numerico if lc else None
        percentual = None
        if meta is not None and meta.valor and realizado is not None:
            percentual = (realizado / meta.valor) * 100
        itens.append(
            {
                "indicador": ind,
                "meta": meta.valor if meta else None,
                "realizado": realizado,
                "percentual": percentual,
                "ytd": ytd,
                "meta_obj": meta,
                "lc": lc,
            }
        )
    return itens
