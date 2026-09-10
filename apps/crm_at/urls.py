from django.urls import path

from .views import FunilATView, empresa_criar, oportunidade_criar, oportunidade_editar

app_name = "crm_at"

urlpatterns = [
    path("funil/", FunilATView.as_view(), name="funil"),
    path("oportunidades/nova/", oportunidade_criar, name="oportunidade_criar"),
    path("oportunidades/<int:pk>/editar/", oportunidade_editar, name="oportunidade_editar"),
    path("empresas/nova/", empresa_criar, name="empresa_criar"),
]
