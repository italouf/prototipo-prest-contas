app_name = "planning"

from django.urls import path

from .views import aplicar, download_html, exportar_csv

urlpatterns = [
    path("aplicar/", aplicar, name="aplicar"),
    path("dados.csv", exportar_csv, name="csv"),
    path("dashboard.html", download_html, name="export_html"),
]
