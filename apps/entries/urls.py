app_name = "entries"

from django.urls import path

from .operational_views import aprovacao, formulario, importar_legado as importar, detalhe as lancamento_drawer, mover_legado as lancamento_mover
from . import operational_views

urlpatterns = [
    path("operacao/", operational_views.iniciar, name="iniciar"),
    path("operacao/base/", operational_views.configurar, name="configurar"),
    path("operacao/projeto-fonte/", operational_views.projeto_fonte, name="projeto_fonte"),
    path("operacao/proposta/<int:periodo_pk>/<int:indicador_pk>/", operational_views.propor, name="propor"),
    path("lancamentos/<int:periodo_pk>/<int:pilar_pk>/importar/", importar, name="importar"),
    path("lancamentos/<int:periodo_pk>/<int:pilar_pk>/", formulario, name="formulario"),
    path("aprovacao/lancamento/<uuid:pk>/drawer/", lancamento_drawer, name="lancamento_drawer"),
    path("aprovacao/lancamento/<int:pk>/mover/", lancamento_mover, name="lancamento_mover"),
    path("aprovacao/<int:periodo_pk>/", aprovacao, name="aprovacao"),
]
