"""Rotas da prestação de contas (SDD §10)."""
from django.urls import path

from . import views

app_name = "accountability"

urlpatterns = [
    path("importar/", views.importar, name="importar"),
]
