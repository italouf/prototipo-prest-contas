import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import models

from .identity import PILARES, normalizar_nome


class RegistroEditavel(models.Model):
    ativo = models.BooleanField("Ativo", default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    atualizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        abstract = True


class Projeto(RegistroEditavel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    centro = models.ForeignKey("accountability.CentroCompetencia", on_delete=models.PROTECT, related_name="catalogo_projetos")
    pilar = models.ForeignKey("pillars.Pilar", on_delete=models.PROTECT, related_name="catalogo_projetos")
    nome = models.CharField("Nome do projeto", max_length=255)
    nome_normalizado = models.CharField(max_length=255, editable=False)
    codigo_embrapii = models.CharField("Código EMBRAPII", max_length=100, blank=True)

    class Meta:
        ordering = ["nome", "pk"]
        constraints = [models.UniqueConstraint(fields=["centro", "pilar", "nome_normalizado"], name="uniq_projeto_catalogo_nome")]

    def clean(self):
        super().clean()
        self.nome = self.nome.strip()
        self.nome_normalizado = normalizar_nome(self.nome)
        if self.pilar_id and self.pilar.codigo not in PILARES:
            raise ValidationError({"pilar": "Entregáveis disponíveis apenas para PDI, FCRH e ACS."})

    def save(self, *args, **kwargs):
        self.nome_normalizado = normalizar_nome(self.nome)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class ReferenciaImportacaoProjeto(models.Model):
    centro = models.ForeignKey("accountability.CentroCompetencia", on_delete=models.PROTECT)
    pilar = models.ForeignKey("pillars.Pilar", on_delete=models.PROTECT)
    projeto = models.ForeignKey(Projeto, on_delete=models.PROTECT, related_name="referencias_importacao")
    origem = models.CharField(max_length=32)
    nome_origem = models.CharField(max_length=255)
    nome_normalizado = models.CharField(max_length=255)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["centro", "pilar", "origem", "nome_normalizado"], name="uniq_referencia_projeto_origem")]


TIPOS_MATERIAL = (
    ("ARTIGO", "Artigo"), ("RELATORIO", "Relatório técnico"),
    ("FORMACAO", "Material de formação"), ("CERTIFICADO", "Certificado"),
    ("PROTOTIPO", "Protótipo/demonstração"), ("SOFTWARE", "Software/repositório"),
    ("OUTRO", "Outro"),
)


class MaterialProjeto(RegistroEditavel):
    projeto = models.ForeignKey(Projeto, on_delete=models.PROTECT, related_name="materiais")
    titulo = models.CharField("Título", max_length=255)
    tipo = models.CharField("Tipo", max_length=20, choices=TIPOS_MATERIAL)
    url = models.URLField("Link do material", max_length=2000, validators=[URLValidator(schemes=["http", "https"])])
    data_publicacao = models.DateField("Data de publicação/entrega", null=True, blank=True)

    class Meta:
        ordering = [models.F("data_publicacao").desc(nulls_last=True), "titulo", "pk"]

    def __str__(self):
        return self.titulo


class BookPrograma(RegistroEditavel):
    centro = models.ForeignKey("accountability.CentroCompetencia", on_delete=models.PROTECT, related_name="books")
    titulo = models.CharField("Título do Book", max_length=255)
    url = models.URLField("Link do Book", max_length=2000, validators=[URLValidator(schemes=["http", "https"])])
    data_publicacao = models.DateField("Data de publicação", null=True, blank=True)

    class Meta:
        ordering = ["-criado_em", "-pk"]
        constraints = [models.UniqueConstraint(fields=["centro"], condition=models.Q(ativo=True), name="uniq_book_vigente_centro")]

    def __str__(self):
        return self.titulo
