from django.contrib import admin

from .models import Pilar, UsuarioPilar


@admin.register(Pilar)
class PilarAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "ordem", "ativo")
    list_filter = ("ativo",)
    list_editable = ("ordem", "ativo")
    search_fields = ("nome", "codigo")


@admin.register(UsuarioPilar)
class UsuarioPilarAdmin(admin.ModelAdmin):
    list_display = ("usuario", "pilar")
    search_fields = ("usuario__username", "pilar__nome")
