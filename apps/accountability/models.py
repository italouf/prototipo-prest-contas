"""Prestação de contas: ingestão dos Excel oficiais, KPIs e overrides (SDD §3).

Espelha o schema aprovado em docs/superpowers/specs/2026-09-29-upload-ingestao-prestacao-design.md §3.
Valores monetários ficam `NULL` quando o Excel traz célula vazia — nunca 0
implícito. Os fluxos mensais (`Periodo`, `FinanceiroConsolidado`, `Lancamento`)
e o plano anual legado (`PlanoAnual`) permanecem intactos.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

TIPOS_FONTE = [
    ("FINANCEIRO_GERAL", "FINANCEIRO GERAL"),
    ("INDICADORES_PE", "Indicadores Gerais do PE"),
    ("ACOMPANHAMENTO_V2", "Acompanhamento Financeiro (v2)"),
]

STATUS_IMPORTACAO = [
    ("SUCESSO", "Sucesso"),
    ("ERRO", "Erro"),
]

BASES_OVERRIDE = [
    ("financeiro", "Financeiro"),
    ("fisico", "Físico"),
]


class CentroCompetencia(models.Model):
    """Centro de competência citado nos arquivos (código = nome normalizado em slug)."""

    # max_length=200 = nome (CharField(200)), fonte do slug (Ruling 19): o slug
    # real do centro tem 68 caracteres e estourava 50 no Postgres (o SQLite não
    # valida varchar). Nunca truncar — centros distintos colidiriam.
    codigo = models.SlugField("Código", max_length=200, unique=True)
    nome = models.CharField("Nome", max_length=200)
    ativo = models.BooleanField("Ativo", default=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Centro de competência"
        verbose_name_plural = "Centros de competência"

    def __str__(self):
        return f"{self.codigo} — {self.nome}"


class Acompanhamento(models.Model):
    """Par (centro, período de referência) que agrupa uma prestação de contas."""

    centro = models.ForeignKey(
        CentroCompetencia, on_delete=models.CASCADE, related_name="acompanhamentos",
        verbose_name="Centro de competência",
    )
    periodo_referencia = models.CharField("Período de referência", max_length=20)  # ex.: "2T/2024"
    termo_cooperacao = models.CharField("Termo de cooperação", max_length=50, blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        ordering = ["centro__nome", "periodo_referencia"]
        verbose_name = "Acompanhamento"
        verbose_name_plural = "Acompanhamentos"
        constraints = [
            models.UniqueConstraint(
                fields=["centro", "periodo_referencia"],
                name="uniq_centro_periodo_acompanhamento",
            ),
        ]

    def __str__(self):
        return f"{self.centro.nome} · {self.periodo_referencia}"


class ImportacaoAcompanhamento(models.Model):
    """Log de cada upload (.xlsx): SUCESSO com contagens ou ERRO com motivos."""

    acompanhamento = models.ForeignKey(
        Acompanhamento, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="importacoes", verbose_name="Acompanhamento",
    )
    tipo_fonte = models.CharField("Tipo de fonte", max_length=20, choices=TIPOS_FONTE)
    arquivo_nome = models.CharField("Arquivo", max_length=255)
    status = models.CharField("Status", max_length=10, choices=STATUS_IMPORTACAO)
    log = models.TextField("Log", blank=True)  # erros unidos por " | "
    avisos = models.TextField("Avisos", blank=True)  # avisos unidos por " | "
    resumo = models.JSONField("Resumo", null=True, blank=True)  # ex.: {"resumos": 9, "projetos": 33}
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Usuário",
    )
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Importação de acompanhamento"
        verbose_name_plural = "Importações de acompanhamento"

    def __str__(self):
        return f"{self.status} · {self.arquivo_nome} · {self.get_tipo_fonte_display()}"


class ResumoFinanceiro(models.Model):
    """Linhas consolidadas do FINANCEIRO GERAL (TAB. 1/1.1/3/5/8/9)."""

    acompanhamento = models.ForeignKey(
        Acompanhamento, on_delete=models.CASCADE, related_name="resumos", verbose_name="Acompanhamento"
    )
    origem = models.CharField("Origem", max_length=32)  # "TAB. 1" | "TAB. 1.1" | "TAB. 3" | "TAB. 5" | "TAB. 8" | "TAB. 9"
    pilar = models.ForeignKey(
        "pillars.Pilar", on_delete=models.CASCADE, related_name="resumos_financeiros", verbose_name="Pilar"
    )
    ano = models.PositiveSmallIntegerField("Ano", null=True, blank=True)  # vazio = consolidado geral
    recurso_ou_meta = models.DecimalField(
        "Recurso ou meta", max_digits=18, decimal_places=2, null=True, blank=True
    )
    captado_anos_1_2 = models.DecimalField(
        "Captado anos 1–2", max_digits=18, decimal_places=2, null=True, blank=True
    )
    captado_ano3_ytd = models.DecimalField(
        "Captado ano 3 (YTD)", max_digits=18, decimal_places=2, null=True, blank=True
    )
    captado = models.DecimalField("Captado", max_digits=18, decimal_places=2, null=True, blank=True)
    realizado = models.DecimalField("Realizado", max_digits=18, decimal_places=2, null=True, blank=True)
    projetado = models.DecimalField("Projetado", max_digits=18, decimal_places=2, null=True, blank=True)
    realizado_mais_projetado = models.DecimalField(
        "Realizado + projetado", max_digits=18, decimal_places=2, null=True, blank=True
    )
    diferenca = models.DecimalField("Diferença", max_digits=18, decimal_places=2, null=True, blank=True)
    percentual = models.DecimalField("Percentual", max_digits=10, decimal_places=6, null=True, blank=True)
    percentual_meta = models.DecimalField(
        "Percentual da meta", max_digits=10, decimal_places=6, null=True, blank=True
    )
    percentual_captado = models.DecimalField(
        "Percentual captado", max_digits=10, decimal_places=6, null=True, blank=True
    )
    farol = models.CharField("Farol", max_length=20, blank=True)

    class Meta:
        ordering = ["acompanhamento", "origem", "pilar__ordem", "ano"]
        verbose_name = "Resumo financeiro"
        verbose_name_plural = "Resumos financeiros"
        constraints = [
            models.UniqueConstraint(
                fields=["acompanhamento", "origem", "pilar", "ano"],
                name="uniq_resumo_acomp_origem_pilar_ano",
            ),
        ]

    def __str__(self):
        ano = self.ano if self.ano is not None else "geral"
        return f"{self.acompanhamento} · {self.origem} · {self.pilar.codigo} · {ano}"


class ProjetoFinanceiro(models.Model):
    """Projetos por pilar do FINANCEIRO GERAL (TAB. 2/4/6)."""

    acompanhamento = models.ForeignKey(
        Acompanhamento, on_delete=models.CASCADE, related_name="projetos", verbose_name="Acompanhamento"
    )
    origem = models.CharField("Origem", max_length=32)  # "TAB. 2" | "TAB. 4" | "TAB. 6"
    pilar = models.ForeignKey(
        "pillars.Pilar", on_delete=models.CASCADE, related_name="projetos_financeiros", verbose_name="Pilar"
    )
    sequencia = models.PositiveIntegerField("Sequência", null=True, blank=True)
    nome = models.CharField("Nome", max_length=255)
    status = models.CharField("Status", max_length=120, blank=True)
    inicio = models.DateField("Início", null=True, blank=True)
    fim = models.DateField("Fim", null=True, blank=True)
    orcado = models.DecimalField("Orçado", max_digits=18, decimal_places=2, null=True, blank=True)
    realizado = models.DecimalField("Realizado", max_digits=18, decimal_places=2, null=True, blank=True)
    projetado_2026 = models.DecimalField(
        "Projetado 2026", max_digits=18, decimal_places=2, null=True, blank=True
    )
    projetado_2027 = models.DecimalField(
        "Projetado 2027", max_digits=18, decimal_places=2, null=True, blank=True
    )
    realizado_mais_projetado = models.DecimalField(
        "Realizado + projetado", max_digits=18, decimal_places=2, null=True, blank=True
    )
    diferenca = models.DecimalField("Diferença", max_digits=18, decimal_places=2, null=True, blank=True)
    percentual = models.DecimalField("Percentual", max_digits=10, decimal_places=6, null=True, blank=True)

    class Meta:
        ordering = ["acompanhamento", "origem", "pilar__ordem", "sequencia", "nome"]
        verbose_name = "Projeto financeiro"
        verbose_name_plural = "Projetos financeiros"
        constraints = [
            models.UniqueConstraint(
                fields=["acompanhamento", "origem", "nome"],
                name="uniq_projeto_acomp_origem_nome",
            ),
        ]

    def __str__(self):
        return f"{self.acompanhamento} · {self.origem} · {self.nome}"


class KpiAcompanhamento(models.Model):
    """KPIs físicos do Termo de Retificação do PE (PE-01..PE-10)."""

    acompanhamento = models.ForeignKey(
        Acompanhamento, on_delete=models.CASCADE, related_name="kpis", verbose_name="Acompanhamento"
    )
    codigo = models.CharField("Código", max_length=40)  # "PE-01".."PE-10"
    sequencia = models.PositiveIntegerField("Sequência")
    nome = models.CharField("Nome", max_length=255)
    pilar = models.ForeignKey(
        "pillars.Pilar", on_delete=models.CASCADE, related_name="kpis_acompanhamento", verbose_name="Pilar"
    )
    descricao = models.TextField("Descrição", blank=True)
    unidade = models.CharField("Unidade", max_length=50, blank=True)
    meta_2024 = models.DecimalField("Meta 2024", max_digits=18, decimal_places=6, null=True, blank=True)
    meta_2025 = models.DecimalField("Meta 2025", max_digits=18, decimal_places=6, null=True, blank=True)
    meta_2026 = models.DecimalField("Meta 2026", max_digits=18, decimal_places=6, null=True, blank=True)
    meta_2027 = models.DecimalField("Meta 2027", max_digits=18, decimal_places=6, null=True, blank=True)
    meta_total = models.DecimalField("Meta total", max_digits=18, decimal_places=6, null=True, blank=True)
    executado_2024 = models.DecimalField(
        "Executado 2024", max_digits=18, decimal_places=6, null=True, blank=True
    )
    executado_2025 = models.DecimalField(
        "Executado 2025", max_digits=18, decimal_places=6, null=True, blank=True
    )
    acumulado = models.DecimalField("Acumulado", max_digits=18, decimal_places=6, null=True, blank=True)
    gap = models.DecimalField("Gap", max_digits=18, decimal_places=6, null=True, blank=True)
    projecao_2026 = models.DecimalField(
        "Projeção 2026", max_digits=18, decimal_places=6, null=True, blank=True
    )
    projecao_2027 = models.DecimalField(
        "Projeção 2027", max_digits=18, decimal_places=6, null=True, blank=True
    )

    class Meta:
        ordering = ["acompanhamento", "sequencia", "codigo"]
        verbose_name = "KPI de acompanhamento"
        verbose_name_plural = "KPIs de acompanhamento"
        constraints = [
            models.UniqueConstraint(
                fields=["acompanhamento", "codigo"],
                name="uniq_kpi_acomp_codigo",
            ),
        ]

    def __str__(self):
        return f"{self.codigo} — {self.nome}"


class DespesaAcompanhamento(models.Model):
    """Lançamentos de despesa das abas 3–9 do Acompanhamento Financeiro (v2)."""

    acompanhamento = models.ForeignKey(
        Acompanhamento, on_delete=models.CASCADE, related_name="despesas", verbose_name="Acompanhamento"
    )
    aba = models.CharField("Aba", max_length=80)
    linha = models.PositiveIntegerField("Linha")
    pilar = models.ForeignKey(
        "pillars.Pilar", on_delete=models.CASCADE, related_name="despesas_acompanhamento", verbose_name="Pilar"
    )
    tipo_recurso = models.CharField("Tipo de recurso", max_length=15)  # EMBRAPII|AT|AT_LEI_TICS|OUTRAS_FONTES
    acao_relacionada = models.CharField("Ação relacionada", max_length=120, blank=True)
    codigo_projeto = models.CharField("Código do projeto", max_length=60, blank=True)
    conta_projeto = models.CharField("Conta do projeto", max_length=60, blank=True)
    marco = models.CharField("Marco", max_length=120, blank=True)
    tipo_despesa = models.CharField("Tipo de despesa", max_length=120, blank=True)
    credor = models.CharField("Credor", max_length=200, blank=True)
    documento = models.CharField("Documento", max_length=120, blank=True)
    numero_nota = models.CharField("Número da nota", max_length=60, blank=True)
    link_documento = models.CharField("Link do documento", max_length=500, blank=True)
    numero_patrimonial = models.CharField("Número patrimonial", max_length=60, blank=True)
    descricao = models.TextField("Descrição", blank=True)
    descricao_atividade = models.TextField("Descrição da atividade", blank=True)
    observacao = models.TextField("Observação", blank=True)
    fonte_recurso = models.CharField("Fonte do recurso", max_length=200, blank=True)
    data_nota = models.DateField("Data da nota", null=True, blank=True)
    data_pagamento = models.DateField("Data do pagamento", null=True, blank=True)
    data_movimento = models.DateField("Data do movimento", null=True, blank=True)
    quantidade = models.DecimalField("Quantidade", max_digits=18, decimal_places=2, null=True, blank=True)
    valor_unitario = models.DecimalField(
        "Valor unitário", max_digits=18, decimal_places=6, null=True, blank=True
    )
    valor = models.DecimalField("Valor", max_digits=18, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["acompanhamento", "aba", "linha"]
        verbose_name = "Despesa de acompanhamento"
        verbose_name_plural = "Despesas de acompanhamento"
        constraints = [
            models.UniqueConstraint(
                fields=["acompanhamento", "aba", "linha"],
                name="uniq_despesa_acomp_aba_linha",
            ),
        ]

    def __str__(self):
        return f"{self.acompanhamento} · {self.aba} · linha {self.linha}"


class OverrideAcompanhamento(models.Model):
    """Override manual de valor previsto/executado — financeiro por pilar, físico por KPI."""

    acompanhamento = models.ForeignKey(
        Acompanhamento, on_delete=models.CASCADE, related_name="overrides", verbose_name="Acompanhamento"
    )
    base = models.CharField("Base de análise", max_length=12, choices=BASES_OVERRIDE)
    pilar = models.ForeignKey(
        "pillars.Pilar", on_delete=models.CASCADE, null=True, blank=True,
        related_name="overrides_acompanhamento", verbose_name="Pilar",
    )  # base=financeiro
    kpi = models.ForeignKey(
        KpiAcompanhamento, on_delete=models.CASCADE, null=True, blank=True,
        related_name="overrides", verbose_name="KPI",
    )  # base=fisico
    ano = models.PositiveSmallIntegerField("Ano")
    campo = models.CharField("Campo", max_length=20)  # previsto|executado
    valor = models.DecimalField("Valor", max_digits=18, decimal_places=2)
    chave = models.CharField(
        "Chave", max_length=120
    )  # "fin|PDI|2026|executado" / "fis|PE-01|2025|previsto" — preenchida pelo chamador
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Usuário"
    )
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        ordering = ["acompanhamento", "chave"]
        verbose_name = "Override de acompanhamento"
        verbose_name_plural = "Overrides de acompanhamento"
        constraints = [
            models.UniqueConstraint(
                fields=["acompanhamento", "chave"],
                name="uniq_override_acomp_chave",
            ),
        ]

    def __str__(self):
        return f"{self.chave} · {self.valor}"

    def clean(self):
        """base=financeiro exige pilar e rejeita kpi; base=fisico exige o inverso (SDD §3)."""
        if self.base == "financeiro":
            if self.pilar_id is None or self.kpi_id is not None:
                raise ValidationError("Override financeiro exige pilar e não pode ter KPI.")
        elif self.base == "fisico":
            if self.kpi_id is None or self.pilar_id is not None:
                raise ValidationError("Override físico exige KPI e não pode ter pilar.")
