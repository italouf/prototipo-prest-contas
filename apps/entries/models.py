"""Lançamentos mensais (RF-050 a RF-058 / RN-010)."""
from django.conf import settings
from django.db import models


class Lancamento(models.Model):
    STATUS = [
        ("RASCUNHO", "Rascunho"),
        ("ENVIADO", "Enviado"),
        ("APROVADO", "Aprovado"),
        ("DEVOLVIDO", "Devolvido"),
    ]

    periodo = models.ForeignKey("periods.Periodo", on_delete=models.CASCADE, related_name="lancamentos")
    indicador = models.ForeignKey("indicators.Indicador", on_delete=models.CASCADE, related_name="lancamentos")
    valor_numerico = models.DecimalField("Valor", max_digits=18, decimal_places=2, null=True, blank=True)
    valor_texto = models.TextField("Texto", blank=True)
    comentario = models.TextField("Comentário", blank=True)
    comentario_revisao = models.TextField("Comentário da revisão", blank=True)
    status = models.CharField("Status", max_length=10, choices=STATUS, default="RASCUNHO")
    usuario_criacao = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lancamentos_criados",
    )
    usuario_aprovacao = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lancamentos_aprovados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("periodo", "indicador")
        ordering = ["indicador__pilar__ordem", "indicador__codigo"]
        verbose_name = "Lançamento"
        verbose_name_plural = "Lançamentos"

    def __str__(self):
        return f"{self.periodo.rotulo} · {self.indicador.codigo} · {self.status}"
