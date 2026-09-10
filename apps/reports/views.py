"""Relatório mensal HTML imprimível (RF-090 a RF-097)."""
import hashlib
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.core.calculos import itens_do_periodo
from apps.core.dashboard import graficos_dados
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
        indicadores = list(Indicador.objects.filter(pilar=pilar, ativo=True).order_by("codigo"))
        itens = itens_do_periodo(indicadores, periodo)
        if itens and all(i["realizado"] is not None for i in itens if i["indicador"].tipo != "TXT"):
            pilares_ok += 1
        secoes.append({"pilar": pilar, "itens": itens})

    financeiro = list(
        FinanceiroConsolidado.objects.filter(periodo=periodo).select_related("pilar")
    )
    totais = {
        "tc": sum((f.valor_captado or Decimal("0") for f in financeiro), Decimal("0")),
        "te": sum((f.valor_executado or Decimal("0") for f in financeiro), Decimal("0")),
    }
    total_aprovados = periodo.lancamentos.filter(status="APROVADO").count()

    por_pilar = {}
    por_mes = {}
    for f in financeiro:
        dados = por_pilar.setdefault(
            f.pilar_id,
            {"nome": f.pilar.nome, "codigo": f.pilar.codigo, "captado": Decimal("0"), "executado": Decimal("0")},
        )
        dados["captado"] += f.valor_captado or Decimal("0")
        dados["executado"] += f.valor_executado or Decimal("0")
        mes = por_mes.setdefault(
            f.periodo.competencia, {"rotulo": f.periodo.rotulo, "captado": Decimal("0"), "executado": Decimal("0")}
        )
        mes["captado"] += f.valor_captado or Decimal("0")
        mes["executado"] += f.valor_executado or Decimal("0")
    chart_pilares = sorted(por_pilar.values(), key=lambda d: d["codigo"])
    chart_mensal = [por_mes[chave] for chave in sorted(por_mes)]
    chart_mensal_json, chart_pilares_json = graficos_dados(chart_mensal, chart_pilares)

    gerado_em = timezone.now()
    assinatura = hashlib.sha256(
        f"{periodo.pk}|{periodo.rotulo}|{totais['tc']}|{totais['te']}|{total_aprovados}|{gerado_em.isoformat()}".encode()
    ).hexdigest()[:16]

    return render(
        request,
        "reports/monthly.html",
        {
            "periodo": periodo,
            "secoes": secoes,
            "financeiro": financeiro,
            "total_captado": totais["tc"],
            "total_executado": totais["te"],
            "total_aprovados": total_aprovados,
            "pilares_ok": pilares_ok,
            "gerado_por": request.user,
            "gerado_em": gerado_em,
            "chart_pilares": chart_pilares,
            "chart_mensal": chart_mensal,
            "chart_mensal_json": chart_mensal_json,
            "chart_pilares_json": chart_pilares_json,
            "assinatura": assinatura,
        },
    )
