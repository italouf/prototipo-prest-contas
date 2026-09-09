"""Rotas locais do Portal QuIIN."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),
    path("", include("apps.core.urls", namespace="core")),
    path("periodos/", include("apps.periods.urls", namespace="periods")),
    path("", include("apps.entries.urls", namespace="entries")),
    path("financeiro/", include("apps.finance.urls", namespace="finance")),
    path("relatorio/", include("apps.reports.urls", namespace="reports")),
    path("crm-at/", include("apps.crm_at.urls", namespace="crm_at")),
    path("auditoria/", include("apps.audit.urls", namespace="audit")),
]
