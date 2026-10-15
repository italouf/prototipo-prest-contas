from django.contrib import admin
from apps.core.permissions import eh_gestor
from .models import Associado, Beneficio, HistoricoSolicitacao, Plano, PlanoBeneficio, Solicitacao, UsoBeneficio

class PermissaoATMixin:
    def has_module_permission(self, request):
        return request.user.is_superuser or eh_gestor(request.user)
    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)
    def has_add_permission(self, request, obj=None):
        return self.has_module_permission(request)
    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)
    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)

class PlanoBeneficioInline(PermissaoATMixin, admin.TabularInline):
    model = PlanoBeneficio
    extra = 0

@admin.register(Plano)
class PlanoAdmin(PermissaoATMixin, admin.ModelAdmin):
    list_display = ["nome", "valor_anual"]
    inlines = [PlanoBeneficioInline]

@admin.register(Associado)
class AssociadoAdmin(PermissaoATMixin, admin.ModelAdmin):
    list_display = ["nome", "tipo", "plano", "fim_vigencia", "email"]
    list_filter = ["tipo", "plano"]
    search_fields = ["nome", "email"]

class HistoricoInline(admin.TabularInline):
    model = HistoricoSolicitacao
    extra = 0
    can_delete = False
    readonly_fields = ["usuario", "data", "descricao", "status"]
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Solicitacao)
class SolicitacaoAdmin(PermissaoATMixin, admin.ModelAdmin):
    list_display = ["id", "associado", "data", "categoria", "responsavel_tecnico", "status", "respondida_em"]
    list_filter = ["status", "categoria"]
    search_fields = ["associado__nome", "assunto"]
    inlines = [HistoricoInline]
    readonly_fields = ["status", "respondida_em"]

class CadastroATAdmin(PermissaoATMixin, admin.ModelAdmin):
    pass

admin.site.register(Beneficio, CadastroATAdmin)
admin.site.register(UsoBeneficio, CadastroATAdmin)
