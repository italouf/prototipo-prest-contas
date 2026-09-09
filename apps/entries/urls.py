app_name = "entries"

from django.urls import path

from .views import aprovacao, formulario

urlpatterns = [
    path("lancamentos/<int:periodo_pk>/<int:pilar_pk>/", formulario, name="formulario"),
    path("aprovacao/<int:periodo_pk>/", aprovacao, name="aprovacao"),
]
