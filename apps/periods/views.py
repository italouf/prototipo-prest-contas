"""Ações de período: abrir, fechar e reabrir (RF-043 a RF-045)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect

from apps.core.permissions import pode_gerenciar_periodos, sem_permissao
from .models import Periodo
from .services import abrir_periodo, fechar_periodo, reabrir_periodo


@login_required
def acao_periodo(request, pk, acao):
    if not pode_gerenciar_periodos(request.user):
        return sem_permissao(request)
    periodo = get_object_or_404(Periodo, pk=pk)
    try:
        if acao == "abrir":
            abrir_periodo(periodo, request.user)
            messages.success(request, f"Período {periodo.rotulo} aberto para lançamentos.")
        elif acao == "fechar":
            fechar_periodo(periodo, request.user)
            messages.success(request, f"Período {periodo.rotulo} fechado com snapshot.")
        elif acao == "reabrir":
            reabrir_periodo(periodo, request.user, request.POST.get("justificativa", ""))
            messages.success(request, f"Período {periodo.rotulo} reaberto.")
        else:
            raise ValidationError("Ação desconhecida.")
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect(request.POST.get("next") or "core:dashboard")
