"""Banco de Talentos e Organograma (LOOP 5)."""
from django.core.exceptions import ValidationError
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone


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
    horas_semanais = models.PositiveIntegerField("Horas disponíveis por semana", default=40, db_default=40, validators=[MinValueValidator(1)])
    formacoes = models.JSONField("Formação acadêmica", default=list, db_default=[], blank=True)
    ativo = models.BooleanField(default=True, db_default=True)
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

    def clean(self):
        niveis = {"Graduação", "Especialização", "Mestrado", "Doutorado", "Pós-doutorado"}
        if not isinstance(self.formacoes, list) or any(not isinstance(f, list) or len(f) != 2 or f[0] not in niveis or not isinstance(f[1], str) or not f[1].strip() for f in self.formacoes):
            raise ValidationError({"formacoes": "Informe formações como pares de nível e área."})
        if self.pk:
            eventos = []
            for a in self.alocacoes.all():
                if a.data_fim and a.data_fim < timezone.localdate():
                    continue
                eventos.append((max(a.data_inicio, timezone.localdate()), a.horas_semanais))
                if a.data_fim:
                    from datetime import timedelta
                    eventos.append((a.data_fim + timedelta(days=1), -a.horas_semanais))
            carga = 0
            for _, delta in sorted(eventos, key=lambda e: (e[0], e[1])):
                carga += delta
                if carga > self.horas_semanais:
                    raise ValidationError({"horas_semanais": "As horas disponíveis não podem ser menores que as alocações existentes."})


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
        if self.colaborador_id and self.data_inicio and self.horas_semanais:
            from datetime import timedelta
            eventos = [(self.data_inicio, self.horas_semanais)]
            if self.data_fim:
                eventos.append((self.data_fim + timedelta(days=1), -self.horas_semanais))
            for a in self.colaborador.alocacoes.exclude(pk=self.pk):
                eventos.append((a.data_inicio, a.horas_semanais))
                if a.data_fim:
                    eventos.append((a.data_fim + timedelta(days=1), -a.horas_semanais))
            carga = 0
            for _, delta in sorted(eventos, key=lambda e: (e[0], e[1])):
                carga += delta
                if carga > self.colaborador.horas_semanais:
                    raise ValidationError("A soma das alocações excede as horas semanais disponíveis do colaborador.")
