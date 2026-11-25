"""Rotas da Prestação de Contas SEMESTRAL (QuIIN / EMBRAPII v3.1)."""
from django.urls import path

from . import views

app_name = "semestral"

urlpatterns = [
    path("acesso/<uuid:token>/", views.acesso_direto, name="acesso_direto"),
    path("competencia/<int:pk>/", views.competencia_form, name="competencia_form"),
    path(
        "competencia/<int:pk>/submeter/",
        views.submeter_competencia_view,
        name="submeter_competencia",
    ),
    path(
        "competencia/<int:pk>/aprovar/",
        views.aprovar_competencia_view,
        name="aprovar_competencia",
    ),
    path(
        "competencia/<int:pk>/devolver/",
        views.devolver_competencia_view,
        name="devolver_competencia",
    ),
    path(
        "competencia/<int:pk>/arquivar/",
        views.arquivar_competencia_view,
        name="arquivar_competencia",
    ),
    path(
        "aprovados/arquivar-todos/",
        views.arquivar_aprovados_em_lote_view,
        name="arquivar_aprovados_lote",
    ),
    path(
        "competencia/<int:pk>/registro/<str:aba>/excluir/<int:reg_id>/",
        views.excluir_registro,
        name="excluir_registro",
    ),
    path("exportar/<str:arquivo>/", views.exportar_xlsx_view, name="exportar_xlsx"),
    path("exportar-pacote/", views.exportar_pacote_zip_view, name="exportar_pacote"),
    path(
        "sla/disparar-alertas/",
        views.sla_disparar_alertas_view,
        name="sla_disparar_alertas",
    ),
    path(
        "sla/verificar-its1/",
        views.sla_verificar_its1_view,
        name="sla_verificar_its1",
    ),
    path("configurar/", views.configurar_ciclo_view, name="configurar_ciclo"),
]
