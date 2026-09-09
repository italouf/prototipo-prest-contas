"""CRM e funil da Associação Tecnológica (LOOP 4)."""
import re

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class Empresa(models.Model):
    STATUS = [
        ("ASSOCIADA", "Associada"),
        ("EX_ASSOCIADA", "Ex-associada"),
        ("PROSPECT", "Prospect"),
    ]

    nome = models.CharField("Nome", max_length=150, unique=True)
    cnpj = models.CharField("CNPJ", max_length=18, unique=True)
    status = models.CharField("Status", max_length=12, choices=STATUS, default="PROSPECT")
    criada_em = models.DateTimeField("Criada em", auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"

    def __str__(self):
        return self.nome

    def clean(self):
        super().clean()
        digitos = re.sub(r"\D", "", self.cnpj or "")
        if len(digitos) != 14:
            raise ValidationError({"cnpj": "Informe um CNPJ válido com 14 dígitos."})


class Oportunidade(models.Model):
    FASES = [
        ("PROSPECCAO", "Prospecção"),
        ("QUALIFICACAO", "Qualificação"),
        ("REUNIAO_TECNICA", "Reunião técnica"),
        ("NEGOCIACAO", "Negociação"),
        ("FECHAMENTO", "Fechamento"),
        ("RENOVACAO", "Renovação"),
        ("PERDIDO", "Perdido"),
    ]
    TIPOS = [
        ("NOVO_CNPJ", "Novo CNPJ"),
        ("RENOVACAO", "Renovação"),
    ]

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="oportunidades",
        verbose_name="Empresa",
    )
    valor_previsto = models.DecimalField(
        "Valor previsto (R$)", max_digits=14, decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    fase = models.CharField("Fase", max_length=16, choices=FASES, default="PROSPECCAO")
    tipo = models.CharField("Tipo", max_length=10, choices=TIPOS, default="NOVO_CNPJ")
    observacao = models.TextField("Observação", blank=True)
    atualizada_em = models.DateTimeField("Atualizada em", auto_now=True)

    class Meta:
        ordering = ["-atualizada_em"]
        verbose_name = "Oportunidade"
        verbose_name_plural = "Oportunidades"

    def __str__(self):
        return f"{self.empresa.nome} — {self.get_fase_display()} (R$ {self.valor_previsto})"
