"""Plano plurianual do painel anual (2024–2027) — snapshot por pilar/base/ano.

`previsto` é o valor de referência pactuado: projetado nos pilares PPI
(PDI, Formação FCRH, ACS, Infraestrutura) e captado em AT e Outras fontes
(RN-018). A execução é materializada aqui (snapshot de plano), não derivada
do operacional — ver docs/sdd-dashboard-anual.md e docs/decisoes.md.
"""
from django.conf import settings
from django.db import models

ANOS = [(2024, "Ano 1: 2024"), (2025, "Ano 2: 2025"), (2026, "Ano 3: 2026"), (2027, "Ano 4: 2027")]
BASES = [("financeiro", "Financeiro"), ("fisico", "Físico")]


class PlanoAnual(models.Model):
    ano = models.PositiveSmallIntegerField("Ano", choices=ANOS)
    pilar = models.ForeignKey(
        "pillars.Pilar", on_delete=models.CASCADE, related_name="plano_anual", verbose_name="Pilar"
    )
    base = models.CharField("Base de análise", max_length=12, choices=BASES)
    previsto = models.DecimalField(
        "Previsto (projetado PPI / captado AT-Outras)", max_digits=12, decimal_places=2, default=0
    )
    executado = models.DecimalField("Executado", max_digits=12, decimal_places=2, default=0)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        verbose_name="Atualizado por",
    )

    class Meta:
        verbose_name = "Plano anual"
        verbose_name_plural = "Plano anual"
        ordering = ["ano", "pilar__ordem", "base"]
        unique_together = ("ano", "pilar", "base")
        constraints = [
            models.CheckConstraint(condition=models.Q(previsto__gte=0), name="plano_previsto_nao_negativo"),
            models.CheckConstraint(condition=models.Q(executado__gte=0), name="plano_executado_nao_negativo"),
        ]

    def __str__(self):
        return f"{self.get_ano_display()} · {self.pilar.codigo} · {self.get_base_display()}"
