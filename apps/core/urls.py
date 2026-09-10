app_name = "core"

from django.urls import path

from .search_views import busca
from .views import dashboard, pilar, pilar_drawer

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("pilar/<int:pk>/", pilar, name="pilar"),
    path("pilar/<int:pk>/drawer/", pilar_drawer, name="pilar_drawer"),
    path("busca/", busca, name="busca"),
]
