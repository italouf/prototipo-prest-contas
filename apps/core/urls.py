app_name = "core"

from django.urls import path
from django.http import HttpResponse

from .search_views import busca
from .views import dashboard, mensal, pilar, pilar_drawer, semestral, semestral_csv
from apps.reports import presentation_views

urlpatterns = [
    path("health/", lambda request: HttpResponse("ok", content_type="text/plain"), name="health"),
    path("", dashboard, name="dashboard"),
    path("prestacao/mensal/", mensal, name="mensal"),
    path("prestacao/mensal/editar/", presentation_views.editar_apresentacao, name="mensal_editar"),
    path("prestacao/mensal/<int:apresentacao_pk>/conteudo/novo/", presentation_views.editar_conteudo, name="mensal_conteudo_novo"),
    path("prestacao/mensal/<int:apresentacao_pk>/conteudo/<int:pk>/", presentation_views.editar_conteudo, name="mensal_conteudo_editar"),
    path("prestacao/mensal/<int:apresentacao_pk>/conteudo/<int:pk>/excluir/", presentation_views.excluir_conteudo, name="mensal_conteudo_excluir"),
    path("prestacao/mensal/imagens/<int:pk>/", presentation_views.imagem_conteudo, name="mensal_imagem"),
    path("prestacao/semestral/", semestral, name="semestral"),
    path("prestacao/semestral/dados.csv", semestral_csv, name="semestral_csv"),
    path("pilar/<int:pk>/", pilar, name="pilar"),
    path("pilar/<int:pk>/drawer/", pilar_drawer, name="pilar_drawer"),
    path("busca/", busca, name="busca"),
]
