"""Busca global do shell (R1): indicadores, empresas e talentos."""
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render

from apps.crm_at.models import Empresa
from apps.indicators.models import Indicador
from apps.talentos.models import Colaborador

from .permissions import pilares_visiveis, pode_aprovar, pode_lancar


@login_required
def busca(request):
    termo = request.GET.get("q", "").strip()
    contexto = {
        "termo": termo,
        "indicadores": [],
        "empresas": [],
        "colaboradores": [],
    }
    if len(termo) >= 2:
        pilares = pilares_visiveis(request.user)
        contexto["indicadores"] = list(
            Indicador.objects.filter(pilar__in=pilares, ativo=True)
            .filter(Q(codigo__icontains=termo) | Q(nome__icontains=termo))
            .select_related("pilar")
            .order_by("pilar__ordem", "codigo")[:5]
        )
        if pode_lancar(request.user) or pode_aprovar(request.user):
            contexto["empresas"] = list(
                Empresa.objects.filter(Q(nome__icontains=termo) | Q(cnpj__icontains=termo))
                .order_by("nome")[:5]
            )
            colaboradores = Colaborador.objects.filter(
                Q(nome__icontains=termo) | Q(cargo__icontains=termo)
            ).select_related("pilar_principal")
            if not pode_aprovar(request.user):
                colaboradores = colaboradores.filter(pilar_principal__in=pilares)
            contexto["colaboradores"] = list(colaboradores.order_by("nome")[:5])

    if request.htmx:
        return render(request, "partials/busca_resultados.html", contexto)
    return render(request, "core/busca.html", contexto)
