"""Importação e visualização financeira (RF-080 a RF-087)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.permissions import pode_importar_financeiro, sem_permissao
from apps.core.utils import periodo_selecionado
from apps.periods.models import Periodo
from .models import FinanceiroConsolidado, ImportacaoFinanceira
from .services import importar_csv


@login_required
def importar(request):
    if not pode_importar_financeiro(request.user):
        return sem_permissao(request)
    periodos = Periodo.objects.order_by("-competencia")
    if request.method == "POST":
        periodo = get_object_or_404(Periodo, pk=request.POST.get("periodo"))
        arquivo = request.FILES.get("arquivo")
        if arquivo is None or not arquivo.name.lower().endswith(".csv"):
            messages.error(request, "Envie um arquivo .csv.")
        else:
            try:
                status, log = importar_csv(arquivo, periodo, request.user)
                if status == "SUCESSO":
                    messages.success(request, log)
                else:
                    messages.error(request, f"Importação rejeitada: {log}")
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
        return redirect("finance:importar")
    importacoes = ImportacaoFinanceira.objects.select_related("periodo").all()[:30]
    return render(request, "finance/importar.html", {"periodos": periodos, "importacoes": importacoes})


@login_required
def consolidado(request):
    periodo, periodos = periodo_selecionado(request)
    linhas, totais = [], {"tc": 0, "te": 0}
    if periodo is not None:
        linhas = FinanceiroConsolidado.objects.filter(periodo=periodo).select_related("pilar")
        totais = linhas.aggregate(tc=Sum("valor_captado"), te=Sum("valor_executado"))
    return render(
        request,
        "finance/consolidado.html",
        {
            "periodo": periodo,
            "periodos": periodos,
            "linhas": linhas,
            "total_captado": totais["tc"] or 0,
            "total_executado": totais["te"] or 0,
        },
    )
