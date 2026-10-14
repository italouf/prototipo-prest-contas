app_name = "accounts"

from django.contrib.auth.views import (
    LogoutView,
    PasswordResetCompleteView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.urls import path, reverse_lazy

from .views import CadastroView, LoginView, PasswordResetConfirmView

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="accounts:login"), name="logout"),
    path("cadastro/", CadastroView.as_view(), name="cadastro"),
    path(
        "esqueceu-senha/",
        PasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.txt",
            subject_template_name="registration/password_reset_subject.txt",
            success_url=reverse_lazy("accounts:password_reset_done"),
        ),
        name="password_reset",
    ),
    path("esqueceu-senha/enviado/", PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("redefinir-senha/concluido/", PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    path("redefinir-senha/<uidb64>/<token>/", PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
]
