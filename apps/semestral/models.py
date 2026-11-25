"""Modelos de governança, SLA/ITS1 e domínio oficial da Prestação de Contas Semestral."""
import uuid
from datetime import date

from django.conf import settings
from django.db import models

from apps.pillars.models import Pilar


class CicloSemestral(models.Model):
    STATUS_CHOICES = [
        ("ABERTO", "Aberto"),
        ("CONSOLIDADO", "Consolidado"),
        ("ENVIADO", "Enviado à EMBRAPII"),
    ]
    SEMESTRE_CHOICES = [
        (1, "1º semestre"),
        (2, "2º semestre"),
    ]

    ano = models.PositiveIntegerField("Ano")
    semestre = models.PositiveSmallIntegerField("Semestre", choices=SEMESTRE_CHOICES)
    centro_competencia = models.CharField(
        "Centro de Competência EMBRAPII",
        max_length=120,
        default="QuIIN (SENAI CIMATEC)",
    )
    abreviacao_cc = models.CharField("Abreviação CC", max_length=16, default="QIN")
    termo_cooperacao = models.CharField(
        "Termo de Cooperação Nº", max_length=60, default="001/2023"
    )
    periodo_referencia_label = models.CharField(
        "Período de Referência do Acompanhamento",
        max_length=60,
        blank=True,
    )
    status = models.CharField(
        "Status", max_length=20, choices=STATUS_CHOICES, default="ABERTO"
    )
    coordenacao_nome = models.CharField(
        "Coordenação QuIIN", max_length=120, default="Mabel"
    )
    coordenacao_email = models.EmailField(
        "E-mail da Coordenação", default="mabel.gestao@quiin.local"
    )
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        unique_together = ("ano", "semestre")
        ordering = ["-ano", "-semestre"]
        verbose_name = "Ciclo Semestral"
        verbose_name_plural = "Ciclos Semestrais"

    def save(self, *args, **kwargs):
        if not self.periodo_referencia_label:
            self.periodo_referencia_label = f"{self.semestre}º semestre/{self.ano}"
        super().save(*args, **kwargs)

    @property
    def meses_indices(self):
        return (1, 2, 3, 4, 5, 6) if self.semestre == 1 else (7, 8, 9, 10, 11, 12)

    @property
    def competencias_datas(self):
        return [date(self.ano, m, 1) for m in self.meses_indices]

    @property
    def rotulo_painel(self):
        return f"{self.semestre}º semestre de {self.ano}"

    @property
    def bloqueado_para_edicao_focal(self):
        return self.status in ("CONSOLIDADO", "ENVIADO")

    @property
    def status_badge_variant(self):
        return {
            "ABERTO": "blue",
            "CONSOLIDADO": "purple",
            "ENVIADO": "green",
        }.get(self.status, "neutral")

    def __str__(self):
        return f"{self.abreviacao_cc} · {self.periodo_referencia_label}"


class ConfiguracaoPilarSemestral(models.Model):
    CODIGO_CHOICES = [
        ("FCRH", "FCRH — Formação e Capacitação de RH"),
        ("ACS", "ACS — Atração e Criação de Startups"),
        ("AFCCT", "AFCCT — Ampliação e Fortalecimento de Competências"),
        ("AT", "AT — Associação Tecnológica"),
        ("FIN_QUIIN", "Financeiro QuIIN (Aba 10 + Abas Azuis 11–18)"),
    ]
    ARQUIVO_CHOICES = [
        ("FIN", "Acompanhamento Financeiro (Abas 10 e 11–18)"),
        ("FCRH", "Acompanhamento Técnico - FCRH"),
        ("ACS", "Acompanhamento Técnico - ACS"),
        ("AFCCT", "Acompanhamento Técnico - AFCCT"),
        ("AT", "Acompanhamento Técnico - AT"),
    ]

    codigo = models.CharField("Código", max_length=20, choices=CODIGO_CHOICES, unique=True)
    nome = models.CharField("Nome do Pilar / Frente", max_length=160)
    arquivo_embrapii = models.CharField("Planilha EMBRAPII", max_length=16, choices=ARQUIVO_CHOICES)
    pilar = models.ForeignKey(
        Pilar,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="configuracoes_semestrais",
    )
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pilares_semestrais_responsavel",
    )
    responsavel_nome = models.CharField("Nome do Responsável", max_length=120)
    responsavel_email = models.EmailField("E-mail do Responsável")
    dia_limite_mensal = models.PositiveSmallIntegerField(
        "Dia limite (mês subsequente)",
        default=5,
        help_text="Dia do mês subsequente à competência em que vence o prazo de submissão.",
    )
    ordem = models.PositiveSmallIntegerField("Ordem", default=0)
    ativo = models.BooleanField("Ativo", default=True)

    class Meta:
        ordering = ["ordem", "codigo"]
        verbose_name = "Configuração de Pilar Semestral"
        verbose_name_plural = "Configurações de Pilares Semestrais"

    def __str__(self):
        return f"{self.codigo} — {self.responsavel_nome}"


class CompetenciaMensalPilar(models.Model):
    STATUS_CHOICES = [
        ("PENDENTE", "Pendente"),
        ("ALERTA_ENVIADO", "Alerta mensal enviado"),
        ("SUBMETIDO_NO_PRAZO", "Submetido no prazo"),
        ("ATRASADO_ITS1_EMITIDA", "Atrasado / Advertência ITS1"),
        ("REGULARIZADO", "Regularizado após ITS1"),
    ]
    STATUS_APROVACAO_CHOICES = [
        ("NAO_ENVIADO", "Não enviado"),
        ("EM_ANALISE", "Em análise"),
        ("APROVADO", "Aprovado"),
        ("DEVOLVIDO", "Devolvido para correção"),
    ]

    ciclo = models.ForeignKey(
        CicloSemestral, on_delete=models.CASCADE, related_name="competencias"
    )
    configuracao_pilar = models.ForeignKey(
        ConfiguracaoPilarSemestral,
        on_delete=models.CASCADE,
        related_name="competencias",
    )
    competencia = models.DateField("Competência (dia 01 do mês)")
    prazo_limite = models.DateTimeField("Prazo limite (Deadline)")
    token_acesso = models.UUIDField("Token de acesso direto", default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(
        "Status", max_length=30, choices=STATUS_CHOICES, default="PENDENTE", db_index=True
    )
    status_aprovacao = models.CharField(
        "Status de aprovação",
        max_length=20,
        choices=STATUS_APROVACAO_CHOICES,
        default="NAO_ENVIADO",
        db_index=True,
    )
    alerta_inicial_em = models.DateTimeField("Alerta inicial em", null=True, blank=True)
    submetido_em = models.DateTimeField("Submetido em", null=True, blank=True)
    its1_emitida_em = models.DateTimeField("Advertência ITS1 emitida em", null=True, blank=True)
    regularizado_em = models.DateTimeField("Regularizado em", null=True, blank=True)
    submetido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="competencias_semestrais_submetidas",
    )
    observacao_submissao = models.TextField("Observação da submissão", blank=True)
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="competencias_semestrais_revisadas",
    )
    revisado_em = models.DateTimeField("Revisado em", null=True, blank=True)
    comentario_revisao = models.TextField("Comentário / Justificativa da revisão", blank=True)
    arquivado_painel = models.BooleanField(
        "Arquivado no painel de aprovação", default=False, db_index=True
    )
    arquivado_em = models.DateTimeField("Arquivado em", null=True, blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        unique_together = ("ciclo", "configuracao_pilar", "competencia")
        ordering = ["competencia", "configuracao_pilar__ordem"]
        verbose_name = "Competência Mensal por Pilar"
        verbose_name_plural = "Competências Mensais por Pilar"

    @property
    def competencia_mm_aaaa(self):
        return self.competencia.strftime("%m/%Y")

    @property
    def competencia_yyyy_mm(self):
        return self.competencia.strftime("%Y-%m")

    @property
    def badge_variant(self):
        return {
            "PENDENTE": "neutral",
            "ALERTA_ENVIADO": "blue",
            "SUBMETIDO_NO_PRAZO": "green",
            "ATRASADO_ITS1_EMITIDA": "orange",
            "REGULARIZADO": "green",
        }.get(self.status, "neutral")

    @property
    def aprovacao_badge_variant(self):
        return {
            "NAO_ENVIADO": "neutral",
            "EM_ANALISE": "purple",
            "APROVADO": "green",
            "DEVOLVIDO": "orange",
        }.get(self.status_aprovacao, "neutral")

    @property
    def painel_badge_variant(self):
        if self.status_aprovacao in ("EM_ANALISE", "APROVADO", "DEVOLVIDO"):
            return self.aprovacao_badge_variant
        return self.badge_variant

    @property
    def rotulo_badge_painel(self):
        if self.status_aprovacao == "APROVADO":
            return "Aprovado"
        if self.status_aprovacao == "EM_ANALISE":
            return "Em análise"
        if self.status_aprovacao == "DEVOLVIDO":
            return "Devolvido"
        return {
            "SUBMETIDO_NO_PRAZO": "No prazo",
            "REGULARIZADO": "Regularizado",
            "ATRASADO_ITS1_EMITIDA": "ITS1 · Atrasado",
            "ALERTA_ENVIADO": "Alerta enviado",
        }.get(self.status, "Pendente")

    @property
    def bloqueada_por_ciclo(self):
        return self.ciclo.bloqueado_para_edicao_focal

    @property
    def bloqueada_para_focal(self):
        return self.status_aprovacao == "APROVADO" or self.ciclo.bloqueado_para_edicao_focal

    @property
    def concluida(self):
        return self.status in ("SUBMETIDO_NO_PRAZO", "REGULARIZADO")

    def __str__(self):
        return f"{self.configuracao_pilar.codigo} · {self.competencia_mm_aaaa} ({self.status})"


class ListaDominioEmbrapii(models.Model):
    categoria = models.CharField("Categoria", max_length=80, db_index=True)
    arquivo_origem = models.CharField("Arquivo de origem", max_length=20)
    aba_origem = models.CharField("Aba de origem", max_length=60, default="Listas")
    referencia_celula = models.CharField("Referência célula", max_length=32, blank=True)
    valor = models.CharField("Valor", max_length=255)
    codigo_auxiliar = models.CharField("Código auxiliar", max_length=60, blank=True)
    ordem = models.PositiveIntegerField("Ordem", default=0)
    ativo = models.BooleanField("Ativo", default=True)

    class Meta:
        unique_together = ("categoria", "valor")
        ordering = ["categoria", "ordem", "valor"]
        verbose_name = "Lista de Domínio EMBRAPII"
        verbose_name_plural = "Listas de Domínio EMBRAPII"

    def __str__(self):
        return f"{self.categoria}: {self.valor}"


class LogNotificacaoSLA(models.Model):
    TIPO_CHOICES = [
        ("ALERTA_MENSAL", "Alerta Mensal com Link Direto"),
        ("ADVERTENCIA_ITS1", "Advertência Formal ITS1"),
        ("COMUNICADO_COORDENACAO", "Comunicado Automático à Coordenação (Mabel / QuIIN)"),
        ("REGULARIZACAO", "Regularização após ITS1"),
        ("APROVACAO_SEMESTRAL", "Aprovação pela Coordenação"),
        ("DEVOLUCAO_SEMESTRAL", "Devolução para correção"),
    ]
    CANAL_CHOICES = [
        ("EMAIL_E_IN_APP", "E-mail + In-App"),
        ("IN_APP", "In-App"),
        ("EMAIL", "E-mail"),
    ]

    competencia = models.ForeignKey(
        CompetenciaMensalPilar, on_delete=models.CASCADE, related_name="logs_sla"
    )
    tipo_evento = models.CharField("Tipo de evento", max_length=30, choices=TIPO_CHOICES, db_index=True)
    codigo_ocorrencia = models.CharField("Código da ocorrência", max_length=20, blank=True)
    destinatario_nome = models.CharField("Destinatário", max_length=120)
    destinatario_email = models.EmailField("E-mail do destinatário")
    cc_emails = models.CharField("Em cópia (CC)", max_length=300, blank=True)
    link_direto = models.CharField("Link direto contextualizado", max_length=500, blank=True)
    assunto = models.CharField("Assunto", max_length=255)
    mensagem = models.TextField("Mensagem")
    canal = models.CharField("Canal", max_length=20, choices=CANAL_CHOICES, default="EMAIL_E_IN_APP")
    lida_em = models.DateTimeField("Lida em", null=True, blank=True)
    enviado_em = models.DateTimeField("Enviado em", auto_now_add=True)
    disparado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notificacoes_sla_disparadas",
    )
    metadados = models.JSONField("Metadados", default=dict, blank=True)

    class Meta:
        ordering = ["-enviado_em", "-id"]
        verbose_name = "Log de Notificação / SLA"
        verbose_name_plural = "Logs de Notificações / SLA"

    def __str__(self):
        tag = f"[{self.codigo_ocorrencia}] " if self.codigo_ocorrencia else ""
        return f"{tag}{self.get_tipo_evento_display()} -> {self.destinatario_email}"


class IntegracaoSemestralOperacional(models.Model):
    """Registro auditável da ponte assistida Semestral v3.1 -> Base Operacional."""

    MODO_CHOICES = [
        ("PROPOSTA", "Proposta enviada para o Painel de aprovação"),
        ("DIRETO", "Publicado diretamente nos Dashboards pelo gestor"),
    ]
    STATUS_CHOICES = [
        ("APLICADA", "Aplicada"),
        ("SUPERADA", "Superada"),
    ]

    competencia_mensal = models.ForeignKey(
        CompetenciaMensalPilar,
        on_delete=models.CASCADE,
        related_name="integracoes_operacionais",
    )
    acompanhamento = models.ForeignKey(
        "accountability.Acompanhamento",
        on_delete=models.PROTECT,
        related_name="integracoes_semestrais",
    )
    indicador_operacional = models.ForeignKey(
        "entries.IndicadorOperacional",
        on_delete=models.PROTECT,
        related_name="integracoes_semestrais",
    )
    lancamento_operacional = models.ForeignKey(
        "entries.LancamentoOperacional",
        on_delete=models.PROTECT,
        related_name="integracoes_semestrais",
    )
    tipo_alvo = models.CharField("Tipo de alvo", max_length=40, db_index=True)
    incremento_calculado = models.DecimalField(
        "Incremento calculado no Semestral", max_digits=18, decimal_places=6
    )
    valor_vigente_anterior = models.DecimalField(
        "Valor vigente anterior nos Dashboards",
        max_digits=18,
        decimal_places=6,
        null=True,
        blank=True,
    )
    valor_proposto = models.DecimalField(
        "Novo total proposto nos Dashboards", max_digits=18, decimal_places=6
    )
    modo = models.CharField("Modo de aplicação", max_length=20, choices=MODO_CHOICES, default="PROPOSTA")
    status_execucao = models.CharField(
        "Status da execução", max_length=20, choices=STATUS_CHOICES, default="APLICADA", db_index=True
    )
    justificativa = models.TextField("Justificativa", blank=True)
    executado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="integracoes_semestrais_executadas",
    )
    executado_em = models.DateTimeField("Executado em", auto_now_add=True)

    class Meta:
        ordering = ["-executado_em", "-id"]
        verbose_name = "Integração Semestral -> Base Operacional"
        verbose_name_plural = "Integrações Semestral -> Base Operacional"
        constraints = [
            models.UniqueConstraint(
                fields=["competencia_mensal", "acompanhamento", "tipo_alvo"],
                condition=models.Q(status_execucao="APLICADA"),
                name="uniq_integracao_semestral_aplicada",
            ),
        ]

    def __str__(self):
        return (
            f"{self.competencia_mensal.configuracao_pilar.codigo} "
            f"{self.competencia_mensal.competencia_mm_aaaa} · {self.tipo_alvo} ({self.status_execucao})"
        )
