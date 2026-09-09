app_name = "periods"

from django.urls import path

from .views import acao_periodo

urlpatterns = [
    path("<int:pk>/<str:acao>/", acao_periodo, name="acao"),
]
