"""Formulários públicos de acesso ao SIG QuIIN."""
from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User


class CadastroForm(UserCreationForm):
    nome = forms.CharField(label="Nome completo", max_length=150)
    email = forms.EmailField(label="E-mail")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("nome", "username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        atributos = {
            "nome": {"autocomplete": "name", "placeholder": "Seu nome completo"},
            "username": {"autocomplete": "username", "placeholder": "nome.sobrenome"},
            "email": {"autocomplete": "email", "placeholder": "seu.email@exemplo.com"},
            "password1": {"autocomplete": "new-password", "placeholder": "Crie uma senha"},
            "password2": {"autocomplete": "new-password", "placeholder": "Repita a senha"},
        }
        self.fields["username"].label = "Usuário"
        self.fields["password1"].label = "Senha"
        self.fields["password2"].label = "Confirmar senha"
        for nome, campo in self.fields.items():
            campo.widget.attrs.update(atributos[nome])

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Este e-mail já está cadastrado. Entre ou recupere sua senha.")
        return email
