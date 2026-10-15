"""Formulários do Banco de Talentos (Task A — Portal QuIIN)."""
from django import forms

from .models import Alocacao, Colaborador, Competencia


class ColaboradorForm(forms.ModelForm):
    formacao_texto = forms.CharField(label="Formação acadêmica", required=False, widget=forms.Textarea(attrs={"rows": 3}), help_text="Uma formação por linha: Nível | Área. Ex.: Doutorado | Física")
    novas_competencias = forms.CharField(
        label="Novas competências",
        required=False,
        help_text="Separadas por vírgula — ex.: Gestão de Eventos, Quantum ML",
        widget=forms.TextInput,
    )

    class Meta:
        model = Colaborador
        fields = ["nome", "cargo", "pilar_principal", "horas_semanais", "foto", "lattes_url", "competencias"]
        widgets = {
            "competencias": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["formacao_texto"].initial = "\n".join(" | ".join(f) for f in self.instance.formacoes)
        if user is not None:
            from apps.core.permissions import eh_pontofocal, pilares_visiveis

            if eh_pontofocal(user):
                self.fields["pilar_principal"].queryset = pilares_visiveis(user)
                self.fields["pilar_principal"].required = True

    def clean_formacao_texto(self):
        formacoes = []
        niveis = {"Graduação", "Especialização", "Mestrado", "Doutorado", "Pós-doutorado"}
        for linha in self.cleaned_data["formacao_texto"].splitlines():
            if not linha.strip():
                continue
            partes = [p.strip() for p in linha.split("|", 1)]
            if len(partes) != 2 or partes[0] not in niveis or not partes[1]:
                raise forms.ValidationError("Use Nível | Área, com Graduação, Especialização, Mestrado, Doutorado ou Pós-doutorado.")
            formacoes.append(partes)
        return formacoes

    def save(self, commit=True):
        self.instance.formacoes = self.cleaned_data["formacao_texto"]
        texto = self.cleaned_data.get("novas_competencias") or ""
        nomes = [n.strip() for n in texto.split(",")]
        nomes = [n for n in nomes if n]
        if commit:
            colaborador = super().save(commit=True)
            self._vincular_novas_competencias(colaborador, nomes)
            return colaborador
        colaborador = super().save(commit=False)
        save_m2m_original = self.save_m2m

        def save_m2m():
            save_m2m_original()
            self._vincular_novas_competencias(colaborador, nomes)

        self.save_m2m = save_m2m
        return colaborador

    @staticmethod
    def _vincular_novas_competencias(colaborador, nomes):
        novas = []
        for nome in nomes:
            competencia = Competencia.objects.filter(nome__iexact=nome).first()
            if competencia is None:
                competencia = Competencia.objects.create(nome=nome)
            novas.append(competencia)
        if novas and colaborador.pk:
            colaborador.competencias.add(*novas)


class AlocacaoForm(forms.ModelForm):
    def __init__(self, *args, colaborador=None, **kwargs):
        super().__init__(*args, **kwargs)
        if colaborador:
            self.instance.colaborador = colaborador
    class Meta:
        model = Alocacao
        fields = ["projeto_ou_area", "horas_semanais", "data_inicio", "data_fim"]
        widgets = {
            "data_inicio": forms.DateInput(attrs={"type": "date"}),
            "data_fim": forms.DateInput(attrs={"type": "date"}),
        }
