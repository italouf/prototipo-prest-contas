from django.contrib import admin

from .models import FinanceiroConsolidado, ImportacaoFinanceira


@admin.register(FinanceiroConsolidado)
class FinanceiroConsolidadoAdmin(admin.ModelAdmin):
    list_display = ("periodo", "pilar", "tipo_recurso", "valor_captado", "valor_executado")
    list_filter = ("tipo_recurso", "periodo")


@admin.register(ImportacaoFinanceira)
class ImportacaoFinanceiraAdmin(admin.ModelAdmin):
    list_display = ("criado_em", "periodo", "arquivo_nome", "status", "usuario")
    list_filter = ("status", "periodo")
