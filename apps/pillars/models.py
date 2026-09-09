"""Pilares do programa e vínculo usuário–pilar (RF-010 a RF-012, RF-005)."""
from django.conf import settings
from django.db import models


class Pilar(models.Model):
    codigo = models.CharField("Código", max_length=30, unique=True)
    nome = models.CharField("Nome", max_length=120)
    descricao = models.TextField("Descrição", blank=True)
    ordem = models.PositiveIntegerField("Ordem", default=0)
    ativo = models.BooleanField("Ativo", default=True)

    class Meta:
        ordering = ["ordem", "nome"]
        verbose_name = "Pilar"
        verbose_name_plural = "Pilares"

    def __str__(self):
        return f"{self.codigo} — {self.nome}"


class UsuarioPilar(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="usuario_pilares",
    )
    pilar = models.ForeignKey(Pilar, on_delete=models.CASCADE, related_name="usuario_pilares")

    class Meta:
        unique_together = ("usuario", "pilar")
        verbose_name = "Vínculo usuário–pilar"
        verbose_name_plural = "Vínculos usuário–pilar"

    def __str__(self):
        return f"{self.usuario} → {self.pilar}"
