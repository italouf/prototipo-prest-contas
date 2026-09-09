from django.contrib import admin

from .models import Periodo


@admin.register(Periodo)
class PeriodoAdmin(admin.ModelAdmin):
    list_display = ("rotulo", "status", "aberto_por", "fechado_por", "snapshot_gerado_em")
    list_filter = ("status",)
    readonly_fields = ("criado_em", "atualizado_em", "snapshot_gerado_em")
