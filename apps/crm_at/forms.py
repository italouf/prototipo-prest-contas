"""Formulários de cadastro do CRM AT (Task A — Portal QuIIN)."""
from django import forms

from .models import Empresa, Oportunidade


class EmpresaForm(forms.ModelForm):
    class Meta:
        model = Empresa
        fields = ["nome", "cnpj", "status"]


class OportunidadeForm(forms.ModelForm):
    class Meta:
        model = Oportunidade
        fields = ["empresa", "valor_previsto", "fase", "tipo", "observacao"]
        widgets = {
            "observacao": forms.Textarea(attrs={"rows": 3}),
        }
