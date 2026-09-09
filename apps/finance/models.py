"""Financeiro consolidado e importações (RF-080 a RF-087 / RN-003 a RN-009)."""
from django.conf import settings
from django.db import models


class FinanceiroConsolidado(models.Model):
    TIPOS = [
        ("EMBRAPII", "Embrapii"),
        ("AT", "Associação Tecnológica"),
        ("OUTRAS_FONTES", "Outras Fontes"),
    ]

    periodo = models.ForeignKey("periods.Periodo", on_delete=models.CASCADE, related_name="financeiro")
    pilar = models.ForeignKey("pillars.Pilar", on_delete=models.CASCADE, related_name="financeiro")
    tipo_recurso = models.CharField("Tipo de recurso", max_length=15, choices=TIPOS)
    valor_captado = models.DecimalField("Valor captado", max_digits=18, decimal_places=2, default=0)
    valor_executado = models.DecimalField("Valor executado", max_digits=18, decimal_places=2, default=0)
    observacao = models.TextField("Observação", blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("periodo", "pilar", "tipo_recurso")
        ordering = ["periodo", "pilar__ordem"]
        verbose_name = "Financeiro consolidado"
        verbose_name_plural = "Financeiro consolidado"

    def __str__(self):
        return f"{self.periodo.rotulo} · {self.pilar.codigo} · {self.tipo_recurso}"


class ImportacaoFinanceira(models.Model):
    STATUS = [
        ("SUCESSO", "Sucesso"),
        ("ERRO", "Erro"),
    ]

    periodo = models.ForeignKey("periods.Periodo", on_delete=models.CASCADE, related_name="importacoes")
    arquivo_nome = models.CharField("Arquivo", max_length=255)
    status = models.CharField("Status", max_length=10, choices=STATUS)
    log = models.TextField("Log", blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Importação financeira"
        verbose_name_plural = "Importações financeiras"

    def __str__(self):
        return f"{self.status} · {self.arquivo_nome} · {self.periodo.rotulo}"
