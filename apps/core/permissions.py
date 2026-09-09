"""Permissões por perfil e pilar (RF-002 a RF-007, RF-058, RF-071 / RN-012).

Toda regra de autorização do portal passa por este módulo e é validada
nas views (backend), nunca apenas no template.
"""
from django.contrib.auth.models import Group
from django.shortcuts import render

GRUPOS = ["Master", "Admin", "PontoFocal", "Lideranca", "Auditor"]


def garantir_grupos():
    """Cria os grupos padrão caso não existam (RF-003)."""
    for nome in GRUPOS:
        Group.objects.get_or_create(name=nome)


def adicionar_grupo(usuario, nome):
    """Vincula o usuário a um grupo padrão (criando-o se necessário)."""
    grupo, _ = Group.objects.get_or_create(name=nome)
    usuario.groups.add(grupo)
    return usuario


def papel_do_usuario(usuario):
    if not usuario or not usuario.is_authenticated:
        return None
    for nome in GRUPOS:
        if usuario.groups.filter(name=nome).exists():
            return nome
    return None


def eh_master(usuario):
    return papel_do_usuario(usuario) == "Master"


def eh_admin(usuario):
    return papel_do_usuario(usuario) == "Admin"


def eh_gestor(usuario):
    return papel_do_usuario(usuario) in ("Master", "Admin")


def eh_pontofocal(usuario):
    return papel_do_usuario(usuario) == "PontoFocal"


def eh_lideranca(usuario):
    return papel_do_usuario(usuario) == "Lideranca"


def eh_auditor(usuario):
    return papel_do_usuario(usuario) == "Auditor"


def pode_lancar(usuario):
    """Master/Admin/PontoFocal podem lançar (RF-058)."""
    return eh_gestor(usuario) or eh_pontofocal(usuario)


def pode_aprovar(usuario):
    return eh_gestor(usuario)


def pode_importar_financeiro(usuario):
    return eh_gestor(usuario)


def pode_gerenciar_periodos(usuario):
    return eh_gestor(usuario)


def pode_ver_auditoria(usuario):
    return eh_gestor(usuario) or eh_auditor(usuario)


def pilares_visiveis(usuario):
    """Pilares visíveis ao usuário (RF-004/RF-005/RF-071)."""
    from apps.pillars.models import Pilar

    if not usuario or not usuario.is_authenticated:
        return Pilar.objects.none()
    if eh_gestor(usuario) or eh_lideranca(usuario) or eh_auditor(usuario):
        return Pilar.objects.filter(ativo=True)
    return Pilar.objects.filter(ativo=True, usuario_pilares__usuario=usuario).distinct()


def usuario_pode_pilar(usuario, pilar):
    return pilares_visiveis(usuario).filter(pk=pilar.pk).exists()


def sem_permissao(request):
    return render(request, "403.html", status=403)
