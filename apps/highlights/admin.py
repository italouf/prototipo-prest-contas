"""Admin dos destaques mensais com permissões por grupo."""
from django.contrib import admin

from apps.core.permissions import papel_do_usuario

from .models import DestaqueMensal

_GRUPOS_ESCRITA = {"Master", "Admin", "PontoFocal"}
_GRUPOS_LEITURA = {"Master", "Admin", "PontoFocal", "Lideranca", "Auditor"}


def _papel_pode_escrever(request):
    return getattr(request.user, "is_superuser", False) or papel_do_usuario(request.user) in _GRUPOS_ESCRITA


def _papel_pode_ver(request):
    return getattr(request.user, "is_superuser", False) or papel_do_usuario(request.user) in _GRUPOS_LEITURA


@admin.register(DestaqueMensal)
class DestaqueMensalAdmin(admin.ModelAdmin):
    list_display = ("titulo", "periodo", "pilar", "tipo", "criado_por", "criado_em")
    list_filter = ("tipo", "periodo", "pilar")
    search_fields = ("titulo", "descricao")

    def has_add_permission(self, request):
        return _papel_pode_escrever(request)

    def has_change_permission(self, request, obj=None):
        return _papel_pode_escrever(request)

    def has_delete_permission(self, request, obj=None):
        return _papel_pode_escrever(request)

    def has_view_permission(self, request, obj=None):
        return _papel_pode_ver(request)
