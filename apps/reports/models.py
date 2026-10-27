"""Apresentações mensais: referência importada e conteúdo editorial no banco."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ApresentacaoMensal(models.Model):
    competencia = models.DateField("Mês da apresentação", unique=True)
    acompanhamento = models.ForeignKey(
        "accountability.Acompanhamento", on_delete=models.PROTECT,
        related_name="apresentacoes", verbose_name="Acompanhamento dos dados",
    )
    titulo = models.CharField("Título", max_length=150, blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="apresentacoes_criadas", editable=False,
    )
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="apresentacoes_atualizadas", editable=False,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-competencia"]
        verbose_name = "Apresentação mensal"
        verbose_name_plural = "Apresentações mensais"

    def clean(self):
        super().clean()
        if self.competencia and self.competencia.day != 1:
            raise ValidationError({"competencia": "Informe o primeiro dia do mês."})

    def __str__(self):
        return self.competencia.strftime("%m/%Y")


class ConteudoApresentacao(models.Model):
    TIPOS = [
        ("DESTAQUE", "Destaque"),
        ("PENDENCIA", "Pendência"),
        ("PROXIMA_ACAO", "Próximos 30 dias"),
    ]
    apresentacao = models.ForeignKey(
        ApresentacaoMensal, on_delete=models.CASCADE, related_name="conteudos",
        verbose_name="Apresentação",
    )
    pilar = models.ForeignKey(
        "pillars.Pilar", on_delete=models.PROTECT, null=True, blank=True,
        related_name="conteudos_apresentacao", verbose_name="Pilar",
        help_text="Vazio = conteúdo geral, visível a todos os leitores da apresentação.",
    )
    tipo = models.CharField("Tipo", max_length=16, choices=TIPOS, default="DESTAQUE")
    titulo = models.CharField("Título", max_length=150)
    texto = models.TextField("Texto", max_length=6000)
    ordem = models.PositiveIntegerField("Ordem", default=0)
    imagem = models.BinaryField("Imagem no banco", blank=True, default=bytes, editable=False)
    imagem_mime = models.CharField(max_length=32, blank=True, editable=False)
    imagem_alt = models.CharField("Descrição da imagem", max_length=200, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ordem", "pk"]
        verbose_name = "Conteúdo de apresentação"
        verbose_name_plural = "Conteúdos de apresentação"

    def __str__(self):
        return self.titulo
