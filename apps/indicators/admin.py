from django.contrib import admin

from .models import Indicador, Meta


@admin.register(Indicador)
class IndicadorAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "pilar", "tipo", "unidade", "acumulado", "ativo")
    list_filter = ("pilar", "tipo", "ativo", "acumulado")
    search_fields = ("codigo", "nome")


@admin.register(Meta)
class MetaAdmin(admin.ModelAdmin):
    list_display = ("indicador", "periodicidade", "valor", "competencia_inicio", "competencia_fim", "versao", "ativo")
    list_filter = ("periodicidade", "ativo")
    search_fields = ("indicador__codigo", "indicador__nome")
