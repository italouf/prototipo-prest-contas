from django.urls import path
from . import views
app_name = "gestao_at"
urlpatterns = [
    path("associados/", views.acompanhamento, name="associados"),
    path("acompanhamento/", views.acompanhamento, name="acompanhamento"),
    path("associados/novo/", views.associado_form, name="associado_criar"),
    path("associados/<int:pk>/", views.associado, name="associado"),
    path("associados/<int:pk>/logo/", views.associado_logo, name="associado_logo"),
    path("associados/<int:pk>/editar/", views.associado_form, name="associado_editar"),
    path("solicitacoes/", views.solicitacoes, name="solicitacoes"),
    path("solicitacoes/nova/", views.solicitacao_criar, name="solicitacao_criar"),
    path("solicitacoes/<int:pk>/", views.solicitacao, name="solicitacao"),
]
