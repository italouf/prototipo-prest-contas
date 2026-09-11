"""Formulários de cadastro do CRM AT (Task A — Portal QuIIN)."""
from django import forms

from .models import Empresa, Oportunidade


class EmpresaForm(forms.ModelForm):
    class Meta:
        model = Empresa
        fields = ["nome", "cnpj", "status"]


class OportunidadeForm(forms.ModelForm):
    empresa_nome = forms.CharField(
        label="Empresa",
        max_length=150,
        widget=forms.TextInput(attrs={"list": "empresas-lista", "autocomplete": "off"}),
        help_text="Digite o nome exato de uma empresa cadastrada; sugestões aparecem enquanto você digita.",
    )

    class Meta:
        model = Oportunidade
        fields = ["valor_previsto", "fase", "tipo", "observacao"]
        widgets = {
            "observacao": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa = None
        if self.instance and self.instance.pk:
            self.initial["empresa_nome"] = self.instance.empresa.nome

    def clean_empresa_nome(self):
        nome = (self.cleaned_data.get("empresa_nome") or "").strip()
        empresa = Empresa.objects.filter(nome__iexact=nome).first()
        if empresa is None:
            raise forms.ValidationError(
                "Empresa não encontrada. Cadastre-a em “Nova empresa” e tente novamente."
            )
        self.empresa = empresa
        return nome

    def save(self, commit=True):
        instancia = super().save(commit=False)
        if self.empresa is not None:
            instancia.empresa = self.empresa
        if commit:
            instancia.save()
        return instancia
