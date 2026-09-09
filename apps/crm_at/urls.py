from django.urls import path

from .views import FunilATView

app_name = "crm_at"

urlpatterns = [
    path("funil/", FunilATView.as_view(), name="funil"),
]
