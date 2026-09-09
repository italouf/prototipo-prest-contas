from django.urls import path

from .views import OrganogramaView

app_name = "talentos"

urlpatterns = [
    path("organograma/", OrganogramaView.as_view(), name="organograma"),
]
