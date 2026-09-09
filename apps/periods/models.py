"""Períodos mensais de competência (RF-040 a RF-045 / RN-001, RN-010)."""
from django.conf import settings
from django.db import models


class Periodo(models.Model):
    STATUS = [
        ("PLANEJADO", "Planejado"),
        ("ABERTO", "Aberto"),
        ("FECHADO", "Fechado"),
        ("REABERTO", "Reaberto"),
    ]

    competencia = models.DateField("Competência", unique=True)
    status = models.CharField("Status", max_length=12, choices=STATUS, default="PLANEJADO")
    aberto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="periodos_abertos",
    )
    fechado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="periodos_fechados",
    )
    reaberto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="periodos_reabertos",
    )
    justificativa_reabertura = models.TextField("Justificativa de reabertura", blank=True)
    snapshot_json = models.JSONField("Snapshot lógico", null=True, blank=True)
    snapshot_gerado_em = models.DateTimeField("Snapshot gerado em", null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-competencia"]
        verbose_name = "Período"
        verbose_name_plural = "Períodos"

    def __str__(self):
        return self.rotulo

    @property
    def rotulo(self):
        return self.competencia.strftime("%Y-%m")

    @property
    def permite_edicao(self):
        return self.status in ("ABERTO", "REABERTO")
