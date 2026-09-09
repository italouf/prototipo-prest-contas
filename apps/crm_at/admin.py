"""Admin do CRM da Associação Tecnológica com permissões por grupo."""
from django.contrib import admin

from apps.core.permissions import papel_do_usuario

from .models import Empresa, Oportunidade

_GRUPOS_ESCRITA = {"Master", "Admin", "PontoFocal"}
_GRUPOS_LEITURA = {"Master", "Admin", "PontoFocal", "Lideranca", "Auditor"}


def _papel_pode_escrever(request):
    return getattr(request.user, "is_superuser", False) or papel_do_usuario(request.user) in _GRUPOS_ESCRITA


def _papel_pode_ver(request):
    return getattr(request.user, "is_superuser", False) or papel_do_usuario(request.user) in _GRUPOS_LEITURA


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("nome", "cnpj", "status")
    list_filter = ("status",)
    search_fields = ("nome", "cnpj")

    def has_add_permission(self, request):
        return _papel_pode_escrever(request)

    def has_change_permission(self, request, obj=None):
        return _papel_pode_escrever(request)

    def has_delete_permission(self, request, obj=None):
        return _papel_pode_escrever(request)

    def has_view_permission(self, request, obj=None):
        return _papel_pode_ver(request)


@admin.register(Oportunidade)
class OportunidadeAdmin(admin.ModelAdmin):
    list_display = ("empresa", "valor_previsto", "fase", "tipo", "atualizada_em")
    list_filter = ("fase", "tipo")
    search_fields = ("empresa__nome",)

    def has_add_permission(self, request):
        return _papel_pode_escrever(request)

    def has_change_permission(self, request, obj=None):
        return _papel_pode_escrever(request)

    def has_delete_permission(self, request, obj=None):
        return _papel_pode_escrever(request)

    def has_view_permission(self, request, obj=None):
        return _papel_pode_ver(request)
