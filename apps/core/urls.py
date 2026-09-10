app_name = "core"

from django.urls import path

from .search_views import busca
from .views import dashboard, pilar

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("pilar/<int:pk>/", pilar, name="pilar"),
    path("busca/", busca, name="busca"),
]
