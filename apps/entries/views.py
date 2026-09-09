"""Formulário de lançamento e painel de aprovação (RF-050 a RF-058, RF-054)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.permissions import pode_aprovar, pode_lancar, sem_permissao, usuario_pode_pilar
from apps.indicators.models import Indicador
from apps.periods.models import Periodo
from apps.pillars.models import Pilar
from .models import Lancamento
from .services import aprovar, devolver, salvar_ou_enviar


@login_required
def formulario(request, periodo_pk, pilar_pk):
    periodo = get_object_or_404(Periodo, pk=periodo_pk)
    pilar = get_object_or_404(Pilar, pk=pilar_pk)
    if not pode_lancar(request.user) or not usuario_pode_pilar(request.user, pilar):
        return sem_permissao(request)
    indicadores = Indicador.objects.filter(pilar=pilar, ativo=True)
    existentes = {lc.indicador_id: lc for lc in Lancamento.objects.filter(periodo=periodo, indicador__in=indicadores)}

    if request.method == "POST":
        dados = {
            str(ind.pk): {
                "valor": request.POST.get(f"valor_{ind.pk}", ""),
                "comentario": request.POST.get(f"comentario_{ind.pk}", ""),
            }
            for ind in indicadores
        }
        try:
            salvar_ou_enviar(periodo, pilar, request.user, dados, enviar=bool(request.POST.get("enviar")))
            if request.POST.get("enviar"):
                messages.success(request, "Lançamentos enviados para validação.")
            else:
                messages.success(request, "Rascunho salvo.")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        return redirect("entries:formulario", periodo_pk=periodo.pk, pilar_pk=pilar.pk)

    return render(
        request,
        "entries/lancamento.html",
        {
            "periodo": periodo,
            "pilar": pilar,
            "indicadores": indicadores,
            "existentes": existentes,
            "bloqueado": not periodo.permite_edicao,
        },
    )


@login_required
def aprovacao(request, periodo_pk):
    if not pode_aprovar(request.user):
        return sem_permissao(request)
    periodo = get_object_or_404(Periodo, pk=periodo_pk)

    if request.method == "POST":
        lc = get_object_or_404(Lancamento, pk=request.POST.get("lancamento_id"), periodo=periodo, status="ENVIADO")
        try:
            if "aprovar" in request.POST:
                aprovar(lc, request.user)
                messages.success(request, f"Lançamento {lc.indicador.codigo} aprovado.")
            elif "devolver" in request.POST:
                devolver(lc, request.user, request.POST.get("comentario_revisao", ""))
                messages.success(request, f"Lançamento {lc.indicador.codigo} devolvido.")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        return redirect("entries:aprovacao", periodo_pk=periodo.pk)

    enviados = periodo.lancamentos.filter(status="ENVIADO").select_related("indicador", "indicador__pilar", "usuario_criacao")
    return render(request, "entries/aprovacao.html", {"periodo": periodo, "enviados": enviados})
