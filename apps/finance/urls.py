app_name = "finance"

from django.urls import path

from .views import consolidado, importar, modelo_csv

urlpatterns = [
    path("importar/", importar, name="importar"),
    path("modelo/", modelo_csv, name="modelo_csv"),
    path("", consolidado, name="consolidado"),
]
