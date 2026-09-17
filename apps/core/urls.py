app_name = "core"

from django.urls import path

from .search_views import busca
from .views import dashboard, mensal, pilar, pilar_drawer

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("prestacao/mensal/", mensal, name="mensal"),
    path("pilar/<int:pk>/", pilar, name="pilar"),
    path("pilar/<int:pk>/drawer/", pilar_drawer, name="pilar_drawer"),
    path("busca/", busca, name="busca"),
]
