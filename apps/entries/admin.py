from django.contrib import admin

from .models import Lancamento


@admin.register(Lancamento)
class LancamentoAdmin(admin.ModelAdmin):
    list_display = ("periodo", "indicador", "valor_numerico", "status", "usuario_criacao", "usuario_aprovacao", "atualizado_em")
    list_filter = ("status", "periodo")
    search_fields = ("indicador__codigo", "indicador__nome", "comentario")
