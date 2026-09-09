"""Indicadores e metas configuráveis (RF-020 a RF-024, RF-030 a RF-033 / RN-013/RN-014)."""
from django.core.exceptions import ValidationError
from django.db import models


class Indicador(models.Model):
    TIPOS = [
        ("QTD", "Quantidade"),
        ("MON", "Monetário"),
        ("PER", "Percentual"),
        ("TXT", "Texto"),
    ]

    pilar = models.ForeignKey("pillars.Pilar", on_delete=models.CASCADE, related_name="indicadores")
    codigo = models.CharField("Código", max_length=30)
    nome = models.CharField("Nome", max_length=150)
    descricao = models.TextField("Descrição", blank=True)
    unidade = models.CharField("Unidade", max_length=50, blank=True)
    tipo = models.CharField("Tipo", max_length=3, choices=TIPOS, default="QTD")
    acumulado = models.BooleanField("Acumulado (YTD)", default=False)
    ativo = models.BooleanField("Ativo", default=True)

    class Meta:
        unique_together = ("pilar", "codigo")
        ordering = ["pilar__ordem", "codigo"]
        verbose_name = "Indicador"
        verbose_name_plural = "Indicadores"

    def __str__(self):
        return f"{self.codigo} — {self.nome}"


class Meta(models.Model):
    PERIODICIDADES = [
        ("MENSAL", "Mensal"),
        ("ANUAL", "Anual"),
        ("ACUMULADA", "Acumulada"),
    ]

    indicador = models.ForeignKey(Indicador, on_delete=models.CASCADE, related_name="metas")
    competencia_inicio = models.DateField("Início da vigência")
    competencia_fim = models.DateField("Fim da vigência")
    periodicidade = models.CharField("Periodicidade", max_length=10, choices=PERIODICIDADES, default="MENSAL")
    valor = models.DecimalField("Valor da meta", max_digits=18, decimal_places=2)
    versao = models.PositiveIntegerField("Versão", default=1)
    ativo = models.BooleanField("Ativa", default=True)
    observacao = models.TextField("Observação", blank=True)

    class Meta:
        ordering = ["indicador", "-versao"]
        verbose_name = "Meta"
        verbose_name_plural = "Metas"

    def __str__(self):
        return f"Meta {self.periodicidade} · {self.indicador} · v{self.versao}"

    def clean(self):
        if self.competencia_fim < self.competencia_inicio:
            raise ValidationError("O fim da vigência deve ser posterior ao início.")
