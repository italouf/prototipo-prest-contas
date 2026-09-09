"""Banco de Talentos e Organograma (LOOP 5)."""
from django.core.exceptions import ValidationError
from django.db import models


class Competencia(models.Model):
    nome = models.CharField("Nome", max_length=100, unique=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Competência"
        verbose_name_plural = "Competências"

    def __str__(self):
        return self.nome


class Colaborador(models.Model):
    nome = models.CharField("Nome", max_length=150)
    cargo = models.CharField("Cargo", max_length=120)
    pilar_principal = models.ForeignKey(
        "pillars.Pilar",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="colaboradores",
        verbose_name="Pilar principal",
    )
    foto = models.ImageField("Foto", upload_to="talentos/fotos/", blank=True)
    lattes_url = models.URLField("Currículo Lattes", blank=True)
    competencias = models.ManyToManyField(
        Competencia,
        blank=True,
        related_name="colaboradores",
        verbose_name="Competências",
    )

    class Meta:
        ordering = ["nome"]
        verbose_name = "Colaborador"
        verbose_name_plural = "Colaboradores"

    def __str__(self):
        return f"{self.nome} ({self.cargo})"


class Alocacao(models.Model):
    colaborador = models.ForeignKey(
        Colaborador,
        on_delete=models.CASCADE,
        related_name="alocacoes",
        verbose_name="Colaborador",
    )
    projeto_ou_area = models.CharField("Projeto ou área", max_length=150)
    horas_semanais = models.PositiveIntegerField("Horas semanais")
    data_inicio = models.DateField("Data de início")
    data_fim = models.DateField("Data de fim", null=True, blank=True)

    class Meta:
        ordering = ["-data_inicio"]
        verbose_name = "Alocação"
        verbose_name_plural = "Alocações"

    def __str__(self):
        return f"{self.colaborador.nome} → {self.projeto_ou_area} ({self.horas_semanais}h/sem)"

    def clean(self):
        super().clean()
        if self.data_fim is not None and self.data_inicio is not None and self.data_fim < self.data_inicio:
            raise ValidationError("A data de fim não pode ser anterior à data de início.")
