"""Relatório mensal HTML imprimível (RF-090 a RF-097)."""
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.core.calculos import meta_realizado_percentual
from apps.core.permissions import pilares_visiveis
from apps.finance.models import FinanceiroConsolidado
from apps.indicators.models import Indicador
from apps.periods.models import Periodo


@login_required
def relatorio_mensal(request, periodo_pk):
    periodo = get_object_or_404(Periodo, pk=periodo_pk)
    secoes = []
    pilares_ok = 0
    for pilar in pilares_visiveis(request.user):
        indicadores = Indicador.objects.filter(pilar=pilar, ativo=True)
        itens = [{"indicador": ind, **meta_realizado_percentual(ind, periodo)} for ind in indicadores]
        if itens and all(i["realizado"] is not None for i in itens if i["indicador"].tipo != "TXT"):
            pilares_ok += 1
        secoes.append({"pilar": pilar, "itens": itens})

    financeiro = FinanceiroConsolidado.objects.filter(periodo=periodo).select_related("pilar")
    totais = financeiro.aggregate(tc=Sum("valor_captado"), te=Sum("valor_executado"))
    total_aprovados = periodo.lancamentos.filter(status="APROVADO").count()
    return render(
        request,
        "reports/monthly.html",
        {
            "periodo": periodo,
            "secoes": secoes,
            "financeiro": financeiro,
            "total_captado": totais["tc"] or 0,
            "total_executado": totais["te"] or 0,
            "total_aprovados": total_aprovados,
            "pilares_ok": pilares_ok,
            "gerado_por": request.user,
            "gerado_em": timezone.now(),
        },
    )
