from django.contrib import admin

from apps.core.permissions import eh_gestor

from .editorial import excluir_editorial, salvar_editorial
from .forms import ApresentacaoMensalForm, ConteudoApresentacaoForm
from .models import ApresentacaoMensal, ConteudoApresentacao


class EditorialAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return eh_gestor(request.user)

    def has_view_permission(self, request, obj=None):
        return eh_gestor(request.user)

    def has_add_permission(self, request):
        return eh_gestor(request.user)

    def has_change_permission(self, request, obj=None):
        return eh_gestor(request.user)

    def has_delete_permission(self, request, obj=None):
        return eh_gestor(request.user)

    def save_model(self, request, obj, form, change):
        salvar_editorial(obj, request.user)

    def delete_model(self, request, obj):
        excluir_editorial(obj, request.user)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            excluir_editorial(obj, request.user)


@admin.register(ApresentacaoMensal)
class ApresentacaoMensalAdmin(EditorialAdmin):
    form = ApresentacaoMensalForm
    list_display = ["competencia", "acompanhamento", "atualizado_em", "atualizado_por"]
    list_select_related = ["acompanhamento__centro", "atualizado_por"]


@admin.register(ConteudoApresentacao)
class ConteudoApresentacaoAdmin(EditorialAdmin):
    form = ConteudoApresentacaoForm
    # O formulário do portal obtém a apresentação pela URL; no Admin ela é explícita.
    fields = ["apresentacao", *ConteudoApresentacaoForm.Meta.fields, "arquivo_imagem", "remover_imagem"]
    list_display = ["titulo", "apresentacao", "tipo", "pilar", "ordem"]
    list_filter = ["tipo", "pilar", "apresentacao"]
    list_select_related = ["apresentacao", "pilar"]
    search_fields = ["titulo", "texto"]
