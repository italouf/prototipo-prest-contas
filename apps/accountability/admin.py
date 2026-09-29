from django.contrib import admin

from .models import (
    Acompanhamento,
    CentroCompetencia,
    DespesaAcompanhamento,
    ImportacaoAcompanhamento,
    KpiAcompanhamento,
    OverrideAcompanhamento,
    ProjetoFinanceiro,
    ResumoFinanceiro,
)


@admin.register(CentroCompetencia)
class CentroCompetenciaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "ativo")


@admin.register(Acompanhamento)
class AcompanhamentoAdmin(admin.ModelAdmin):
    list_display = ("centro", "periodo_referencia", "termo_cooperacao", "criado_em")


@admin.register(ImportacaoAcompanhamento)
class ImportacaoAcompanhamentoAdmin(admin.ModelAdmin):
    list_display = ("criado_em", "tipo_fonte", "arquivo_nome", "status", "acompanhamento")
    list_filter = ("status", "tipo_fonte")


@admin.register(ResumoFinanceiro)
class ResumoFinanceiroAdmin(admin.ModelAdmin):
    list_display = ("acompanhamento", "origem", "pilar", "ano", "realizado", "projetado", "farol")
    list_filter = ("origem",)


@admin.register(ProjetoFinanceiro)
class ProjetoFinanceiroAdmin(admin.ModelAdmin):
    list_display = ("acompanhamento", "origem", "pilar", "nome", "orcado", "realizado")
    list_filter = ("origem",)


@admin.register(KpiAcompanhamento)
class KpiAcompanhamentoAdmin(admin.ModelAdmin):
    list_display = ("acompanhamento", "codigo", "nome", "pilar", "meta_total", "acumulado")


@admin.register(DespesaAcompanhamento)
class DespesaAcompanhamentoAdmin(admin.ModelAdmin):
    list_display = ("acompanhamento", "aba", "linha", "tipo_recurso", "credor", "valor")


@admin.register(OverrideAcompanhamento)
class OverrideAcompanhamentoAdmin(admin.ModelAdmin):
    list_display = ("acompanhamento", "chave", "base", "ano", "campo", "valor")
    list_filter = ("base", "campo")
