"""Formulários compartilhados pelo portal e pelo Admin; arquivos ficam no banco."""
from datetime import date

from django import forms

from apps.accountability.models import Acompanhamento
from apps.pillars.models import Pilar

from .models import ApresentacaoMensal, ConteudoApresentacao


class ApresentacaoMensalForm(forms.ModelForm):
    competencia = forms.DateField(
        label="Mês da apresentação", input_formats=["%Y-%m", "%Y-%m-%d"],
        widget=forms.DateInput(format="%Y-%m", attrs={"type": "month"}),
    )

    class Meta:
        model = ApresentacaoMensal
        fields = ["competencia", "acompanhamento", "titulo"]
        help_texts = {
            "acompanhamento": "Os números mantêm a referência deste acompanhamento. Novos acompanhamentos não alteram este vínculo.",
            "titulo": "Opcional. Em branco, usa Apresentação de acompanhamento mensal.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["acompanhamento"].queryset = Acompanhamento.objects.select_related("centro").order_by("-criado_em", "-pk")
        if self.instance.pk:
            self.fields["competencia"].disabled = True

    def clean_competencia(self):
        valor = self.cleaned_data["competencia"]
        return date(valor.year, valor.month, 1)


class ConteudoApresentacaoForm(forms.ModelForm):
    arquivo_imagem = forms.ImageField(
        label="Imagem opcional", required=False,
        help_text="JPEG, PNG ou WebP, até 5 MB.",
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )
    remover_imagem = forms.BooleanField(label="Remover imagem atual", required=False)

    class Meta:
        model = ConteudoApresentacao
        fields = ["tipo", "pilar", "titulo", "texto", "ordem", "imagem_alt"]
        widgets = {"texto": forms.Textarea(attrs={"rows": 5})}
        help_texts = {"ordem": "Itens com menor número aparecem primeiro.", "texto": "Texto simples; parágrafos são preservados e slides adicionais são gerados quando necessário."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pilar"].queryset = Pilar.objects.filter(ativo=True)

    def clean_arquivo_imagem(self):
        arquivo = self.cleaned_data.get("arquivo_imagem")
        if not arquivo:
            return arquivo
        formatos = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
        if arquivo.size > 5 * 1024 * 1024:
            raise forms.ValidationError("A imagem deve ter no máximo 5 MB.")
        if arquivo.image.format not in formatos:
            raise forms.ValidationError("Envie uma imagem JPEG, PNG ou WebP.")
        arquivo.content_type = formatos[arquivo.image.format]
        arquivo.seek(0)
        return arquivo

    def clean(self):
        dados = super().clean()
        arquivo = dados.get("arquivo_imagem")
        if arquivo and dados.get("remover_imagem"):
            self.add_error("remover_imagem", "Escolha substituir ou remover a imagem.")
        tem_imagem = arquivo or (self.instance.imagem_mime and not dados.get("remover_imagem"))
        if tem_imagem and dados.get("tipo") != "DESTAQUE":
            self.add_error("tipo", "Imagens são permitidas em destaques. Remova a imagem para alterar o tipo.")
        return dados

    def save(self, commit=True):
        obj = super().save(commit=False)
        arquivo = self.cleaned_data.get("arquivo_imagem")
        if self.cleaned_data.get("remover_imagem"):
            obj.imagem, obj.imagem_mime, obj.imagem_alt = b"", "", ""
        elif arquivo:
            obj.imagem = arquivo.read()
            obj.imagem_mime = arquivo.content_type
        if obj.imagem_mime and not obj.imagem_alt:
            obj.imagem_alt = obj.titulo
        if commit:
            obj.save()
        return obj
