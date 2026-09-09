"""Trilha de auditoria (RF-100 a RF-106 / RN-011)."""
from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auditorias",
    )
    acao = models.CharField("Ação", max_length=50)
    entidade = models.CharField("Entidade", max_length=100)
    registro_id = models.CharField("Registro", max_length=40, blank=True)
    campo = models.CharField("Campo", max_length=100, blank=True)
    valor_anterior = models.TextField("Valor anterior", blank=True)
    valor_novo = models.TextField("Valor novo", blank=True)
    justificativa = models.TextField("Justificativa", blank=True)
    data_hora = models.DateTimeField("Data/hora", auto_now_add=True)

    class Meta:
        ordering = ["-data_hora"]
        verbose_name = "Registro de auditoria"
        verbose_name_plural = "Registros de auditoria"

    def __str__(self):
        return f"{self.acao} · {self.entidade} · {self.usuario}"
