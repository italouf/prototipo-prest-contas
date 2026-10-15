app_name = "audit"

from django.urls import path

from .views import lista

urlpatterns = [
    path("exportar.csv", lista, name="exportar"),
    path("", lista, name="lista"),
]
