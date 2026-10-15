from django import forms
from .models import Associado, Solicitacao

class AssociadoEmailForm(forms.Form):
    email = forms.EmailField(required=False, max_length=254, widget=forms.EmailInput(attrs={"placeholder": "cadastrar e-mail da empresa", "aria-label": "E-mail da associada"}))

class AssociadoForm(forms.ModelForm):
    class Meta:
        model = Associado
        fields = ["nome", "tipo", "plano", "email", "inicio_vigencia", "fim_vigencia", "primeira_reuniao"]
        widgets = {c: forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}) for c in ("inicio_vigencia", "fim_vigencia", "primeira_reuniao")}

class SolicitacaoForm(forms.ModelForm):
    class Meta:
        model = Solicitacao
        fields = ["associado", "categoria", "data", "beneficio", "assunto"]
        widgets = {"data": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}), "assunto": forms.Textarea(attrs={"rows": 3})}
