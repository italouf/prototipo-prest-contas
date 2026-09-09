from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("data_hora", "usuario", "acao", "entidade", "registro_id", "campo")
    list_filter = ("acao", "entidade", "data_hora")
    search_fields = ("usuario__username", "entidade", "registro_id")
    readonly_fields = [f.name for f in AuditLog._meta.fields]
