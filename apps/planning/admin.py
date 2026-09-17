from django.contrib import admin

from .models import PlanoAnual


@admin.register(PlanoAnual)
class PlanoAnualAdmin(admin.ModelAdmin):
    list_display = ("ano", "pilar", "base", "previsto", "executado", "atualizado_em")
    list_filter = ("ano", "base", "pilar")
