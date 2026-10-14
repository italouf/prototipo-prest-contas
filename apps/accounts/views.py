"""Login local auditado (RF-001, RF-100 a RF-106)."""
from django.contrib.auth.views import LoginView as BaseLoginView
from django.contrib.auth.views import PasswordResetConfirmView as BasePasswordResetConfirmView
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import FormView

from apps.audit.services import registrar_auditoria

from .forms import CadastroForm


class LoginView(BaseLoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        resposta = super().form_valid(form)
        registrar_auditoria(
            usuario=self.request.user,
            acao="LOGIN",
            entidade="Sessao",
            campo="login",
            valor_novo="sucesso",
        )
        return resposta


class CadastroView(FormView):
    template_name = "registration/cadastro.html"
    form_class = CadastroForm
    success_url = reverse_lazy("accounts:login")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("core:dashboard")
        return super().dispatch(request, *args, **kwargs)

    @transaction.atomic
    def form_valid(self, form):
        usuario = form.save()
        registrar_auditoria(
            usuario=usuario,
            acao="CADASTRO",
            entidade="Usuario",
            registro_id=usuario.pk,
            valor_novo="cadastro realizado",
        )
        messages.success(self.request, "Cadastro realizado com sucesso. Entre com seu usuário e senha.")
        return super().form_valid(form)


class PasswordResetConfirmView(BasePasswordResetConfirmView):
    template_name = "registration/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")

    @transaction.atomic
    def form_valid(self, form):
        resposta = super().form_valid(form)
        registrar_auditoria(
            usuario=self.user,
            acao="REDEFINICAO_SENHA",
            entidade="Usuario",
            registro_id=self.user.pk,
            valor_novo="senha redefinida",
        )
        return resposta
