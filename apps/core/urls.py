app_name = "core"

from django.urls import path

from .views import dashboard, pilar

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("pilar/<int:pk>/", pilar, name="pilar"),
]
