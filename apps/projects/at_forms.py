from django import forms

from .identity import normalizar_nome
from .models import MaterialProdutoAT, ProdutoAT


class ProdutoATForm(forms.ModelForm):
    class Meta:
        model = ProdutoAT
        fields = ["nome", "ordem"]
        widgets = {"ordem": forms.NumberInput(attrs={"min": 0})}

    def clean_nome(self):
        nome = self.cleaned_data["nome"].strip()
        if ProdutoAT.objects.filter(centro_id=self.instance.centro_id,
            nome_normalizado=normalizar_nome(nome)).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Já existe um produto com esse nome neste centro, inclusive entre os arquivados.")
        return nome


class MaterialProdutoATForm(forms.ModelForm):
    class Meta:
        model = MaterialProdutoAT
        fields = ["titulo", "tipo", "url", "data_publicacao"]
        widgets = {"data_publicacao": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}
