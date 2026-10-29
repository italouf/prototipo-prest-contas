from django.contrib import admin

from .models import BaseOperacional, IndicadorOperacional, Lancamento, LancamentoOperacional, ProjetoFinanceiroFonte


class ConsultaOperacionalAdmin(admin.ModelAdmin):
    """Publicação e configuração passam pelos serviços auditados da Operação."""
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Lancamento)
class LancamentoAdmin(ConsultaOperacionalAdmin):
    list_display = ("periodo", "indicador", "valor_numerico", "status", "usuario_criacao", "usuario_aprovacao", "atualizado_em")
    list_filter = ("status", "periodo")
    search_fields = ("indicador__codigo", "indicador__nome", "comentario")


@admin.register(LancamentoOperacional)
class RevisaoAdmin(ConsultaOperacionalAdmin):
    list_display = ("indicador", "periodo", "versao", "valor", "status", "criado_por", "revisado_por")
    list_filter = ("status", "periodo", "indicador__base", "indicador__pilar")
    search_fields = ("indicador__nome", "comentario")


admin.site.register(BaseOperacional, ConsultaOperacionalAdmin)
admin.site.register(IndicadorOperacional, ConsultaOperacionalAdmin)
admin.site.register(ProjetoFinanceiroFonte, ConsultaOperacionalAdmin)
