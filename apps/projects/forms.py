from django import forms

from .identity import normalizar_nome
from .models import BookPrograma, MaterialProjeto, Projeto


class ProjetoForm(forms.ModelForm):
    class Meta:
        model = Projeto
        fields = ["nome", "codigo_embrapii"]

    def clean_nome(self):
        nome = self.cleaned_data["nome"].strip()
        existentes = Projeto.objects.filter(centro_id=self.instance.centro_id,
            pilar_id=self.instance.pilar_id, nome_normalizado=normalizar_nome(nome)).exclude(pk=self.instance.pk)
        if existentes.exists():
            raise forms.ValidationError("Já existe um projeto com esse nome neste centro e pilar, inclusive entre os arquivados.")
        return nome


class MaterialForm(forms.ModelForm):
    class Meta:
        model = MaterialProjeto
        fields = ["titulo", "tipo", "url", "data_publicacao"]
        widgets = {"data_publicacao": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}


class BookForm(forms.ModelForm):
    class Meta:
        model = BookPrograma
        fields = ["titulo", "url", "data_publicacao"]
        widgets = {"data_publicacao": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}


class AssociacaoForm(forms.Form):
    projeto = forms.ModelChoiceField(label="Associar ao projeto", queryset=Projeto.objects.none())

    def __init__(self, *args, referencia, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["projeto"].queryset = Projeto.objects.filter(
            centro_id=referencia.centro_id, pilar_id=referencia.pilar_id, ativo=True,
        ).exclude(pk=referencia.projeto_id)
