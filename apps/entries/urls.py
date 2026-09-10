app_name = "entries"

from django.urls import path

from .views import aprovacao, formulario, lancamento_drawer

urlpatterns = [
    path("lancamentos/<int:periodo_pk>/<int:pilar_pk>/", formulario, name="formulario"),
    path("aprovacao/lancamento/<int:pk>/drawer/", lancamento_drawer, name="lancamento_drawer"),
    path("aprovacao/<int:periodo_pk>/", aprovacao, name="aprovacao"),
]
