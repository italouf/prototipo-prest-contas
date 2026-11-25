from django.contrib import admin

from .models import (
    CicloSemestral,
    CompetenciaMensalPilar,
    ConfiguracaoPilarSemestral,
    IntegracaoSemestralOperacional,
    ListaDominioEmbrapii,
    LogNotificacaoSLA,
)
from .models_registros import (
    RegAcsEmpresa,
    RegAcsPedidoPi,
    RegAcsProfissional,
    RegAcsProjetoFormacao,
    RegAcsProjetoPdi,
    RegAcsPublicacao,
    RegAfcctPedidoPi,
    RegAfcctProfissional,
    RegAfcctProjetoFormacao,
    RegAfcctProjetoPdi,
    RegAfcctPublicacao,
    RegAtAtividade,
    RegAtProspeccao,
    RegFcrhProfissional,
    RegFcrhProjeto,
    RegFinAssociadas,
    RegFinConselho,
    RegFinCoopInternacional,
    RegFinCoopNacional,
    RegFinEquipe,
    RegFinEventos,
    RegFinLicenciamentoPI,
    RegFinMidia,
    RegFinOutrasFontes,
    RegOutrosComentarios,
)


@admin.register(CicloSemestral)
class CicloSemestralAdmin(admin.ModelAdmin):
    list_display = ("ano", "semestre", "centro_competencia", "abreviacao_cc", "termo_cooperacao", "status")
    list_filter = ("ano", "semestre", "status")


@admin.register(ConfiguracaoPilarSemestral)
class ConfiguracaoPilarSemestralAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "arquivo_embrapii", "responsavel_nome", "responsavel_email", "dia_limite_mensal", "ativo")
    list_filter = ("arquivo_embrapii", "ativo")


@admin.register(CompetenciaMensalPilar)
class CompetenciaMensalPilarAdmin(admin.ModelAdmin):
    list_display = ("ciclo", "configuracao_pilar", "competencia", "prazo_limite", "status", "its1_emitida_em")
    list_filter = ("status", "configuracao_pilar", "ciclo")
    readonly_fields = ("token_acesso",)


@admin.register(ListaDominioEmbrapii)
class ListaDominioEmbrapiiAdmin(admin.ModelAdmin):
    list_display = ("categoria", "valor", "codigo_auxiliar", "arquivo_origem", "referencia_celula", "ordem", "ativo")
    list_filter = ("categoria", "arquivo_origem", "ativo")
    search_fields = ("categoria", "valor", "codigo_auxiliar")


@admin.register(LogNotificacaoSLA)
class LogNotificacaoSLAAdmin(admin.ModelAdmin):
    list_display = ("tipo_evento", "codigo_ocorrencia", "competencia", "destinatario_email", "cc_emails", "enviado_em")
    list_filter = ("tipo_evento", "codigo_ocorrencia")
    search_fields = ("destinatario_email", "assunto", "mensagem")


@admin.register(IntegracaoSemestralOperacional)
class IntegracaoSemestralOperacionalAdmin(admin.ModelAdmin):
    list_display = (
        "competencia_mensal",
        "tipo_alvo",
        "modo",
        "status_execucao",
        "incremento_calculado",
        "valor_proposto",
        "executado_por",
        "executado_em",
    )
    list_filter = ("status_execucao", "modo", "tipo_alvo")
    search_fields = ("tipo_alvo", "justificativa")


for _model in (
    RegFinOutrasFontes,
    RegFinEquipe,
    RegFinLicenciamentoPI,
    RegFinAssociadas,
    RegFinCoopNacional,
    RegFinCoopInternacional,
    RegFinMidia,
    RegFinEventos,
    RegFinConselho,
    RegFcrhProjeto,
    RegFcrhProfissional,
    RegAcsProjetoPdi,
    RegAcsPedidoPi,
    RegAcsPublicacao,
    RegAcsProjetoFormacao,
    RegAcsProfissional,
    RegAcsEmpresa,
    RegAfcctProjetoPdi,
    RegAfcctPedidoPi,
    RegAfcctPublicacao,
    RegAfcctProjetoFormacao,
    RegAfcctProfissional,
    RegAtAtividade,
    RegAtProspeccao,
    RegOutrosComentarios,
):
    admin.site.register(_model)
