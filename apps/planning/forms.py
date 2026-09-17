"""Formulário do filtro do painel anual (L3) — validação sempre no backend."""
from django import forms

from .services import ANOS, BASES

ANO_TODOS = "todos"
ANO_CHOICES = [(ANO_TODOS, "Todos os anos")] + [(str(a), f"Ano {i + 1}: {a}") for i, a in enumerate(ANOS)]
BASE_FIN, BASE_FIS = "fin", "fis"
ALIASES_BASE = {"financeiro": BASE_FIN, "fisico": BASE_FIS}
BASES_CANONICAS = {BASE_FIN: "financeiro", BASE_FIS: "fisico"}


class PainelFiltroForm(forms.Form):
    """`?ano=todos|2024..2027&base=fin|fis` (aceita aliases financeiro/fisico)."""

    ano = forms.CharField(required=False)
    base = forms.CharField(required=False)

    def clean_ano(self):
        valor = (self.cleaned_data.get("ano") or ANO_TODOS).strip()
        validos = {ANO_TODOS, *(str(a) for a in ANOS)}
        if valor not in validos:
            raise forms.ValidationError("Ano inválido.")
        return valor

    def clean_base(self):
        valor = (self.cleaned_data.get("base") or BASE_FIN).strip().lower()
        if valor in ALIASES_BASE:
            return ALIASES_BASE[valor]
        if valor not in BASES_CANONICAS:
            raise forms.ValidationError("Base inválida.")
        return valor

    def ano_inteiro(self):
        ano = self.cleaned_data.get("ano", ANO_TODOS)
        return None if ano == ANO_TODOS else int(ano)
