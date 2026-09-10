"""Formulários do Banco de Talentos (Task A — Portal QuIIN)."""
from django import forms

from .models import Alocacao, Colaborador


class ColaboradorForm(forms.ModelForm):
    class Meta:
        model = Colaborador
        fields = ["nome", "cargo", "pilar_principal", "foto", "lattes_url", "competencias"]
        widgets = {
            "competencias": forms.CheckboxSelectMultiple,
        }


class AlocacaoForm(forms.ModelForm):
    class Meta:
        model = Alocacao
        fields = ["projeto_ou_area", "horas_semanais", "data_inicio", "data_fim"]
        widgets = {
            "data_inicio": forms.DateInput(attrs={"type": "date"}),
            "data_fim": forms.DateInput(attrs={"type": "date"}),
        }
