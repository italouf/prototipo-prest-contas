app_name = "reports"

from django.urls import path

from .views import relatorio_mensal

urlpatterns = [
    path("mensal/<int:periodo_pk>/", relatorio_mensal, name="mensal"),
]
