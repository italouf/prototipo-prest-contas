app_name = "entries"

from django.urls import path

from .views import aprovacao, formulario, importar, lancamento_drawer, lancamento_mover

urlpatterns = [
    path("lancamentos/<int:periodo_pk>/<int:pilar_pk>/importar/", importar, name="importar"),
    path("lancamentos/<int:periodo_pk>/<int:pilar_pk>/", formulario, name="formulario"),
    path("aprovacao/lancamento/<int:pk>/drawer/", lancamento_drawer, name="lancamento_drawer"),
    path("aprovacao/lancamento/<int:pk>/mover/", lancamento_mover, name="lancamento_mover"),
    path("aprovacao/<int:periodo_pk>/", aprovacao, name="aprovacao"),
]
