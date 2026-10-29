from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("pilar/<int:pilar_pk>/novo/", views.projeto_form, name="novo"),
    path("pilar/<int:pilar_pk>/gerenciar/", views.gerenciar, name="gerenciar"),
    path("pilar/<int:pilar_pk>/book/", views.book_form, name="book"),
    path("pilar/<int:pilar_pk>/entregaveis.csv", views.exportar_csv, name="csv"),
    path("pilar/<int:pilar_pk>/<uuid:pk>/editar/", views.projeto_form, name="editar"),
    path("pilar/<int:pilar_pk>/<uuid:projeto_pk>/materiais/novo/", views.material_form, name="material_novo"),
    path("pilar/<int:pilar_pk>/<uuid:projeto_pk>/materiais/<int:pk>/", views.material_form, name="material_editar"),
    path("pilar/<int:pilar_pk>/referencia/<int:pk>/", views.referencia_form, name="referencia"),
    path("pilar/<int:pilar_pk>/projeto/<uuid:pk>/situacao/", views.situacao, {"recurso": "projeto"}, name="projeto_situacao"),
    path("pilar/<int:pilar_pk>/material/<int:pk>/situacao/", views.situacao, {"recurso": "material"}, name="material_situacao"),
    path("pilar/<int:pilar_pk>/book/<int:pk>/situacao/", views.situacao, {"recurso": "book"}, name="book_situacao"),
]
