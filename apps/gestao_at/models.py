from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

class Plano(models.Model):
    nome = models.CharField(max_length=40, unique=True)
    valor_anual = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    ordem = models.PositiveSmallIntegerField(default=0)
    class Meta:
        ordering = ["ordem", "nome"]
    def __str__(self):
        return self.nome

class Beneficio(models.Model):
    codigo = models.SlugField(unique=True)
    nome = models.CharField(max_length=150)
    categoria = models.CharField(max_length=60)
    unidade = models.CharField(max_length=40, blank=True)
    quantitativo = models.BooleanField(default=False)
    ordem = models.PositiveSmallIntegerField(default=0)
    class Meta:
        ordering = ["ordem", "nome"]
    def __str__(self):
        return self.nome

class PlanoBeneficio(models.Model):
    plano = models.ForeignKey(Plano, on_delete=models.CASCADE, related_name="beneficios")
    beneficio = models.ForeignKey(Beneficio, on_delete=models.PROTECT)
    incluido = models.BooleanField(default=True)
    cota = models.PositiveIntegerField(default=0)
    condicao = models.CharField(max_length=60, blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["plano", "beneficio"], name="at_plano_beneficio_unico")]

class Associado(models.Model):
    TIPOS = [("Empresa", "Empresa"), ("Startup", "Startup"), ("ICT", "ICT")]
    nome = models.CharField(max_length=150, unique=True)
    tipo = models.CharField(max_length=10, choices=TIPOS)
    plano = models.ForeignKey(Plano, on_delete=models.PROTECT, related_name="associados")
    email = models.EmailField(blank=True)
    logo = models.BinaryField(null=True, blank=True, editable=False)
    logo_tipo = models.CharField(max_length=20, blank=True, editable=False)
    inicio_vigencia = models.DateField()
    fim_vigencia = models.DateField()
    primeira_reuniao = models.DateField(null=True, blank=True)
    demonstracao = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["pk"]
    def __str__(self):
        return self.nome
    def clean(self):
        if self.inicio_vigencia and self.fim_vigencia and self.fim_vigencia < self.inicio_vigencia:
            raise ValidationError({"fim_vigencia": "O fim da vigência deve ser posterior ao início."})
    @property
    def dias_vigencia(self):
        return (self.fim_vigencia - timezone.localdate()).days
    @property
    def situacao_vigencia(self):
        d = self.dias_vigencia
        if d < 0:
            return "Vencido"
        for limite in (10, 30, 60, 90):
            if d <= limite:
                return f"Vence em até {limite} dias"
        return "Vigente"

class ContatoAssociado(models.Model):
    associado = models.ForeignKey(Associado, on_delete=models.CASCADE, related_name="contatos")
    nome = models.CharField(max_length=150, blank=True)
    email = models.EmailField()

    class Meta:
        ordering = ["pk"]
        constraints = [models.UniqueConstraint(fields=["associado", "email"], name="at_contato_email_unico")]

class UsoBeneficio(models.Model):
    associado = models.ForeignKey(Associado, on_delete=models.CASCADE, related_name="usos")
    beneficio = models.ForeignKey(Beneficio, on_delete=models.PROTECT)
    quantidade = models.PositiveIntegerField(default=0)
    atualizado_em = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["associado", "beneficio"], name="at_uso_beneficio_unico")]

class Solicitacao(models.Model):
    STATUS = [(s, s) for s in ("Recebida", "Encaminhada", "Em andamento", "Respondida", "Concluída")]
    CATEGORIAS = [(s, s) for s in ("PDI", "Formação", "Infraestrutura", "Plataformas e PI", "Mentoria", "Estudos", "Startups")]
    associado = models.ForeignKey(Associado, on_delete=models.PROTECT, related_name="solicitacoes")
    data = models.DateField(default=timezone.localdate)
    categoria = models.CharField(max_length=40, choices=CATEGORIAS)
    beneficio = models.CharField(max_length=150)
    assunto = models.CharField(max_length=500)
    responsavel_tecnico = models.CharField(max_length=150)
    responsavel_pilar = models.ForeignKey("pillars.Pilar", null=True, blank=True, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS, default="Recebida")
    respondida_em = models.DateField(null=True, blank=True)
    recebida_por = models.CharField(max_length=150, default="Cintia Pereira")
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    origem_prototipo = models.CharField(max_length=40, unique=True, null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["-data", "-pk"]
        constraints = [models.CheckConstraint(condition=~models.Q(status__in=["Respondida", "Concluída"]) | models.Q(respondida_em__isnull=False), name="at_resposta_exige_data")]
    @property
    def dias(self):
        return max(0, ((self.respondida_em or timezone.localdate()) - self.data).days)
    @property
    def atrasada(self):
        return self.respondida_em is None and self.dias > 10
    def clean(self):
        if self.respondida_em and self.data and self.respondida_em < self.data:
            raise ValidationError("A resposta não pode ser anterior ao pedido.")
        if self.status in ("Respondida", "Concluída") and not self.respondida_em:
            raise ValidationError("Informe a data da resposta.")
    def __str__(self):
        return f"Solicitação nº {self.pk} · {self.associado}"

class HistoricoSolicitacao(models.Model):
    solicitacao = models.ForeignKey(Solicitacao, on_delete=models.CASCADE, related_name="historico")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    data = models.DateTimeField(default=timezone.now)
    descricao = models.TextField()
    status = models.CharField(max_length=20, blank=True)
    class Meta:
        ordering = ["data", "pk"]
