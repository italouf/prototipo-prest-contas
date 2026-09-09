"""Login local auditado (RF-001, RF-100 a RF-106)."""
from django.contrib.auth.views import LoginView as BaseLoginView

from apps.audit.services import registrar_auditoria


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
