"""Admin do Banco de Talentos com permissões por grupo."""
from django.contrib import admin

from apps.core.permissions import papel_do_usuario

from .models import Alocacao, Colaborador, Competencia

_GRUPOS_ESCRITA = {"Master", "Admin", "PontoFocal"}
_GRUPOS_LEITURA = {"Master", "Admin", "PontoFocal", "Lideranca", "Auditor"}


def _papel_pode_escrever(request):
    return getattr(request.user, "is_superuser", False) or papel_do_usuario(request.user) in _GRUPOS_ESCRITA


def _papel_pode_ver(request):
    return getattr(request.user, "is_superuser", False) or papel_do_usuario(request.user) in _GRUPOS_LEITURA


class _PermissaoPorGrupoMixin:
    def has_add_permission(self, request):
        return _papel_pode_escrever(request)

    def has_change_permission(self, request, obj=None):
        return _papel_pode_escrever(request)

    def has_delete_permission(self, request, obj=None):
        return _papel_pode_escrever(request)

    def has_view_permission(self, request, obj=None):
        return _papel_pode_ver(request)


@admin.register(Competencia)
class CompetenciaAdmin(_PermissaoPorGrupoMixin, admin.ModelAdmin):
    search_fields = ("nome",)


@admin.register(Colaborador)
class ColaboradorAdmin(_PermissaoPorGrupoMixin, admin.ModelAdmin):
    list_display = ("nome", "cargo", "pilar_principal")
    list_filter = ("pilar_principal",)
    search_fields = ("nome", "cargo")


@admin.register(Alocacao)
class AlocacaoAdmin(_PermissaoPorGrupoMixin, admin.ModelAdmin):
    list_display = ("colaborador", "projeto_ou_area", "horas_semanais", "data_inicio", "data_fim")
    list_filter = ("projeto_ou_area",)
