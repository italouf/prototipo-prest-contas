from django.urls import path

from .views import (
    OrganogramaView,
    alocacao_criar,
    alocacao_editar,
    colaborador_criar,
    colaborador_editar,
)

app_name = "talentos"

urlpatterns = [
    path("organograma/", OrganogramaView.as_view(), name="organograma"),
    path("colaboradores/novo/", colaborador_criar, name="colaborador_criar"),
    path("colaboradores/<int:pk>/editar/", colaborador_editar, name="colaborador_editar"),
    path(
        "colaboradores/<int:colaborador_pk>/alocacoes/nova/",
        alocacao_criar,
        name="alocacao_criar",
    ),
    path("alocacoes/<int:pk>/editar/", alocacao_editar, name="alocacao_editar"),
]
