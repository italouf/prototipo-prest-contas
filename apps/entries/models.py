"""Lançamentos mensais (RF-050 a RF-058 / RN-010)."""
from django.conf import settings
from django.db import models
from django.core.serializers.json import DjangoJSONEncoder
import uuid


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


class BaseOperacional(models.Model):
    acompanhamento = models.OneToOneField("accountability.Acompanhamento", on_delete=models.PROTECT, related_name="base_operacional")
    competencia_corte = models.DateField()
    versao = models.PositiveIntegerField(default=1)
    snapshot = models.JSONField(encoder=DjangoJSONEncoder)
    confirmado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    confirmado_em = models.DateTimeField(auto_now_add=True)


class ProjetoFinanceiroFonte(models.Model):
    """Carteira financeira de AT/Outras Fontes; independente dos produtos da AT."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    centro = models.ForeignKey("accountability.CentroCompetencia", on_delete=models.PROTECT)
    pilar = models.ForeignKey("pillars.Pilar", on_delete=models.PROTECT)
    nome = models.CharField(max_length=255)
    ativo = models.BooleanField(default=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["pilar__ordem", "nome"]
        constraints = [models.UniqueConstraint(fields=["centro", "pilar", "nome"], name="uniq_projeto_financeiro_fonte")]

    def __str__(self):
        return self.nome


class IndicadorOperacional(models.Model):
    acompanhamento = models.ForeignKey("accountability.Acompanhamento", on_delete=models.PROTECT, related_name="indicadores_operacionais")
    pilar = models.ForeignKey("pillars.Pilar", on_delete=models.PROTECT)
    chave = models.CharField(max_length=160)
    nome = models.CharField(max_length=300)
    base = models.CharField(max_length=12, choices=[("fisico", "Física"), ("financeiro", "Financeira")])
    tipo = models.CharField(max_length=3, choices=[("QTD", "Quantidade"), ("MON", "Monetário"), ("PER", "Percentual")])
    unidade = models.CharField(max_length=50)
    alvo = models.CharField(max_length=20, choices=[("KPI", "Indicador físico"), ("PROJETO", "Projeto PPI"), ("FONTE", "Projeto da fonte"), ("PILAR", "Consolidado")])
    referencia = models.CharField(max_length=100)
    campo = models.CharField(max_length=20, default="realizado")
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["pilar__ordem", "base", "nome", "campo"]
        constraints = [models.UniqueConstraint(fields=["acompanhamento", "chave"], name="uniq_indicador_operacional")]

    def __str__(self):
        return self.nome


class LancamentoOperacional(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    indicador = models.ForeignKey(IndicadorOperacional, on_delete=models.PROTECT, related_name="revisoes")
    periodo = models.ForeignKey("periods.Periodo", on_delete=models.PROTECT, related_name="lancamentos_operacionais")
    versao = models.PositiveIntegerField()
    valor = models.DecimalField(max_digits=18, decimal_places=6)
    valor_base = models.DecimalField(max_digits=18, decimal_places=6, null=True)
    base_versao = models.PositiveIntegerField()
    comentario = models.TextField(blank=True)
    comentario_revisao = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Lancamento.STATUS, default="RASCUNHO")
    origem = models.CharField(max_length=30, default="Lançamento")
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="propostas_operacionais")
    revisado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="revisoes_operacionais")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    enviado_em = models.DateTimeField(null=True, blank=True)
    aprovado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-periodo__competencia", "-versao"]
        constraints = [
            models.UniqueConstraint(fields=["indicador", "periodo", "versao"], name="uniq_revisao_operacional"),
            models.UniqueConstraint(fields=["indicador", "periodo"], condition=models.Q(status__in=["RASCUNHO", "ENVIADO", "DEVOLVIDO"]), name="uniq_proposta_operacional_ativa"),
            models.CheckConstraint(condition=models.Q(valor__gte=0), name="valor_operacional_nao_negativo"),
        ]
