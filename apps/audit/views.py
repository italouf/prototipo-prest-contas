"""Consulta de auditoria (RF-007, RF-100 a RF-106).

Interface amigável: filtros por usuário/entidade/ação/data, paginação e
total de resultados. Permissão restrita a Master/Admin/Auditor.
"""
from datetime import date

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render

from apps.core.permissions import pode_ver_auditoria, sem_permissao
from .models import AuditLog


@login_required
def lista(request):
    if not pode_ver_auditoria(request.user):
        return sem_permissao(request)

    registros = AuditLog.objects.select_related("usuario").all()
    f_usuario = request.GET.get("usuario", "").strip()
    f_entidade = request.GET.get("entidade", "").strip()
    f_acao = request.GET.get("acao", "").strip()
    f_data_inicio = request.GET.get("data_inicio", "").strip()
    f_data_fim = request.GET.get("data_fim", "").strip()

    if f_usuario:
        registros = registros.filter(usuario__username__icontains=f_usuario)
    if f_entidade:
        registros = registros.filter(entidade__icontains=f_entidade)
    if f_acao:
        registros = registros.filter(acao=f_acao)
    if f_data_inicio:
        try:
            registros = registros.filter(data_hora__date__gte=date.fromisoformat(f_data_inicio))
        except ValueError:
            f_data_inicio = ""
    if f_data_fim:
        try:
            registros = registros.filter(data_hora__date__lte=date.fromisoformat(f_data_fim))
        except ValueError:
            f_data_fim = ""

    entidades = AuditLog.objects.values_list("entidade", flat=True).distinct().order_by("entidade")
    acoes = AuditLog.objects.values_list("acao", flat=True).distinct().order_by("acao")
    total = registros.count()
    page_obj = Paginator(registros, 25).get_page(request.GET.get("page"))

    return render(
        request,
        "audit/lista.html",
        {
            "page_obj": page_obj,
            "total": total,
            "entidades": entidades,
            "acoes": acoes,
            "f_usuario": f_usuario,
            "f_entidade": f_entidade,
            "f_acao": f_acao,
            "f_data_inicio": f_data_inicio,
            "f_data_fim": f_data_fim,
        },
    )
