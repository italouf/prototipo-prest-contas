from django import forms
from .models import Associado, Solicitacao

class AssociadoEmailForm(forms.Form):
    email = forms.EmailField(required=False, max_length=254, widget=forms.EmailInput(attrs={"placeholder": "cadastrar e-mail da empresa", "aria-label": "E-mail da associada"}))

class AssociadoLogoForm(forms.Form):
    logo = forms.ImageField(label="Imagem da logo", widget=forms.FileInput(attrs={"accept": "image/png,image/jpeg,image/webp,image/gif"}))

    def clean_logo(self):
        imagem = self.cleaned_data["logo"]
        if imagem.size > 2 * 1024 * 1024:
            raise forms.ValidationError("A imagem deve ter no máximo 2 MB.")
        tipos = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp", "GIF": "image/gif"}
        if imagem.image.format not in tipos:
            raise forms.ValidationError("Use uma imagem PNG, JPEG, WebP ou GIF.")
        imagem.tipo_logo = tipos[imagem.image.format]
        imagem.seek(0)
        return imagem

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
