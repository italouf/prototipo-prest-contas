from django.urls import path

from . import at_views as views
from . import library_views

app_name = "deliverables_at"

urlpatterns = [
    path("produtos/<uuid:pk>/", library_views.produto, name="detalhe"),
    path("produtos/<uuid:pk>/relatorio/", library_views.produto, {"modo": "relatorio"}, name="relatorio"),
    path("produtos/<uuid:pk>/materiais.csv", library_views.produto, {"modo": "csv"}, name="csv_consulta"),
    path("produtos/novo/", views.produto_form, name="novo"),
    path("gerenciar/", views.gerenciar, name="gerenciar"),
    path("entregaveis.csv", views.exportar_csv, name="csv"),
    path("produtos/<uuid:pk>/editar/", views.produto_form, name="editar"),
    path("produtos/<uuid:produto_pk>/materiais/novo/", views.material_form, name="material_novo"),
    path("produtos/<uuid:produto_pk>/materiais/<int:pk>/", views.material_form, name="material_editar"),
    path("produtos/<uuid:pk>/situacao/", views.situacao, {"recurso": "produto"}, name="produto_situacao"),
    path("materiais/<int:pk>/situacao/", views.situacao, {"recurso": "material"}, name="material_situacao"),
]
