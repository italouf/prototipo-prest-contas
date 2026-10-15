"""Consulta e exportação da trilha real de auditoria, restritas por perfil."""
import csv
from datetime import date
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render
from apps.accounts.models import User
from apps.core.permissions import pode_ver_auditoria, sem_permissao
from .models import AuditLog

def tipo_acao(acao):
    acao = acao.upper()
    if "LOGIN" in acao or "LOGOUT" in acao or "ACESSO" in acao:
        return "Acesso"
    if "APROVAR" in acao or "APROVACAO" in acao:
        return "Aprovação"
    if "DEVOLVER" in acao or "DEVOLUCAO" in acao:
        return "Devolução"
    if "ENVIAR" in acao:
        return "Envio"
    if "IMPORT" in acao:
        return "Importação"
    if "EXPORT" in acao:
        return "Exportação"
    if "CRIAR" in acao or "CADASTR" in acao:
        return "Cadastro"
    return "Edição"

@login_required
def lista(request):
    if not pode_ver_auditoria(request.user):
        return sem_permissao(request)
    registros = AuditLog.objects.select_related("usuario").all()
    f_usuario = request.GET.get("usuario", "").strip()
    f_entidade = request.GET.get("entidade", "").strip()
    f_acao = request.GET.get("acao", "").strip()
    f_tipo = request.GET.get("tipo", "").strip()
    q = request.GET.get("q", "").strip()
    f_data_inicio = request.GET.get("data_inicio", "").strip()
    f_data_fim = request.GET.get("data_fim", "").strip()
    if f_usuario:
        registros = registros.filter(Q(usuario__username__icontains=f_usuario) | Q(usuario__nome__icontains=f_usuario))
    if f_entidade:
        registros = registros.filter(entidade__icontains=f_entidade)
    if f_acao:
        registros = registros.filter(acao=f_acao)
    acoes = list(AuditLog.objects.values_list("acao", flat=True).distinct())
    if f_tipo:
        registros = registros.filter(acao__in=[a for a in acoes if tipo_acao(a) == f_tipo])
    if q:
        registros = registros.filter(Q(entidade__icontains=q) | Q(registro_id__icontains=q) | Q(valor_anterior__icontains=q) | Q(valor_novo__icontains=q) | Q(justificativa__icontains=q) | Q(usuario__nome__icontains=q))
    for key, valor in (("data_inicio", f_data_inicio), ("data_fim", f_data_fim)):
        if valor:
            try:
                registros = registros.filter(**{"data_hora__date__" + ("gte" if key == "data_inicio" else "lte"): date.fromisoformat(valor)})
            except ValueError:
                pass
    if request.path.endswith("exportar.csv"):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="auditoria_quiin.csv"'
        response.write("\ufeff")
        writer = csv.writer(response, delimiter=";")
        writer.writerow(["Data e hora", "Usuário", "Ação", "Objeto", "Campo", "Valor anterior", "Valor novo", "Justificativa", "Origem"])
        def cell(value):
            value = str(value or "")
            return "'" + value if value.startswith(("=", "+", "-", "@")) else value
        for log in registros.iterator():
            writer.writerow([cell(v) for v in [log.data_hora.isoformat(), log.usuario.nome_exibicao if log.usuario else "Sistema", tipo_acao(log.acao), log.entidade + " #" + log.registro_id, log.campo, log.valor_anterior, log.valor_novo, log.justificativa, log.origem]])
        return response
    page_obj = Paginator(registros, 25).get_page(request.GET.get("page"))
    for log in page_obj:
        log.tipo = tipo_acao(log.acao)
    query = request.GET.copy()
    query.pop("page", None)
    return render(request, "audit/lista.html", {
        "page_obj": page_obj, "total": registros.count(), "usuarios": User.objects.filter(auditorias__isnull=False).distinct(),
        "tipos": ["Acesso", "Edição", "Envio", "Aprovação", "Devolução", "Importação", "Exportação", "Cadastro"],
        "f_usuario": f_usuario, "f_entidade": f_entidade, "f_acao": f_acao, "f_tipo": f_tipo, "q": q,
        "f_data_inicio": f_data_inicio, "f_data_fim": f_data_fim, "query": query.urlencode(),
        "total_logs": AuditLog.objects.count(), "total_usuarios": User.objects.filter(auditorias__isnull=False).distinct().count(),
        "total_edicoes": AuditLog.objects.filter(acao__in=[a for a in acoes if tipo_acao(a) == "Edição"]).count(),
        "total_validacoes": AuditLog.objects.filter(acao__in=[a for a in acoes if tipo_acao(a) in ("Aprovação", "Devolução")]).count(),
    })
