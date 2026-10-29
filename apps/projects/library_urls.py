from django.urls import path
from . import library_views as views

app_name = "materials"
urlpatterns = [
    path("", views.biblioteca, name="biblioteca"),
    path("relatorio/", views.biblioteca, {"modo": "relatorio"}, name="relatorio"),
    path("dados.csv", views.biblioteca, {"modo": "csv"}, name="csv"),
]
