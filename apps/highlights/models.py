"""Destaques qualitativos do período (LOOP 2)."""
from django.conf import settings
from django.db import models


class DestaqueMensal(models.Model):
    TIPOS = [
        ("DESTAQUE", "Destaque"),
        ("PENDENCIA_EMBRAPII", "Pendência EMBRAPII"),
        ("FOCO_30_DIAS", "Foco 30 dias"),
    ]

    periodo = models.ForeignKey(
        "periods.Periodo",
        on_delete=models.CASCADE,
        related_name="destaques",
        verbose_name="Período",
    )
    pilar = models.ForeignKey(
        "pillars.Pilar",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="destaques",
        verbose_name="Pilar",
        help_text="Vazio = destaque geral do período.",
    )
    titulo = models.CharField("Título", max_length=150)
    descricao = models.TextField("Descrição")
    tipo = models.CharField("Tipo", max_length=20, choices=TIPOS, default="DESTAQUE")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Criado por",
    )
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Destaque mensal"
        verbose_name_plural = "Destaques mensais"

    def __str__(self):
        rotulo = getattr(getattr(self, "periodo", None), "rotulo", "")
        return f"{self.titulo} ({rotulo})"
