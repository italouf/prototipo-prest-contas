app_name = "finance"

from django.urls import path

from .views import consolidado, importar

urlpatterns = [
    path("importar/", importar, name="importar"),
    path("", consolidado, name="consolidado"),
]
