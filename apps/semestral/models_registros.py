"""Registros tipados das 24 abas no escopo QuIIN (EMBRAPII v3.1).

Cada registro vincula-se a uma CompetenciaMensalPilar (`mm/aaaa`), permitindo coleta
mensal incremental e consolidação cronológica semestral na exportação .xlsx.
"""
from django.conf import settings
from django.db import models

from .models import CompetenciaMensalPilar


class RegistroSemestralBase(models.Model):
    competencia_mensal = models.ForeignKey(
        CompetenciaMensalPilar,
        on_delete=models.CASCADE,
        related_name="%(class)s_registros",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        abstract = True
        ordering = ["competencia_mensal__competencia", "id"]


# ---------------------------------------------------------------------------
# PLANILHA 1 — FINANCEIRO (Escopo QuIIN: Aba 10 + Abas Azuis 11 a 18)
# ---------------------------------------------------------------------------


class RegFinOutrasFontes(RegistroSemestralBase):
    """Aba 10. Conta Ação - Outras Fontes (FIN)."""

    acao_relacionada = models.CharField("Ação relacionada", max_length=80)
    codigo_projeto_atividade = models.CharField(
        "Código do projeto/atividade", max_length=120, blank=True
    )
    tipo_despesa = models.CharField("Tipo de despesa", max_length=140, blank=True)
    mes_ano_competencia = models.DateField("Mês/ano da competência")
    entidade_aporte = models.CharField(
        "Entidade que realizou o aporte", max_length=180, blank=True
    )
    descricao = models.TextField("Descrição")
    data_movimentacao = models.DateField("Data")
    valor = models.DecimalField("Valor (R$)", max_digits=14, decimal_places=2)

    class Meta(RegistroSemestralBase.Meta):
        verbose_name = "10. Conta Ação - Outras Fontes"


class RegFinEquipe(RegistroSemestralBase):
    """Aba 11. Equipe (FIN)."""

    nome_completo = models.CharField("Nome Completo", max_length=180)
    cpf_passaporte = models.CharField("CPF / Passaporte", max_length=40)
    titulacao = models.CharField("Titulação", max_length=60)
    formacao_academica = models.CharField(
        "Formação Acadêmica (da Graduação)", max_length=180
    )
    atividade_funcao = models.CharField("Atividade / Função", max_length=120)
    disponibilidade_horas_mes = models.PositiveIntegerField(
        "Disponibilidade (horas/mês)"
    )
    link_lattes = models.URLField("Link do Currículo Lattes", max_length=400, blank=True)
    data_admissao = models.DateField("Data de Admissão no CC")
    data_saida = models.DateField("Data de Saída do CC", null=True, blank=True)
    observacoes = models.TextField("Observações", blank=True)

    class Meta(RegistroSemestralBase.Meta):
        verbose_name = "11. Equipe"


class RegFinLicenciamentoPI(RegistroSemestralBase):
    """Aba 12. Licenciamento de PIs (FIN)."""

    titulo_pi = models.CharField("Título da PI", max_length=255)
    codigo_projeto = models.CharField("Código do projeto que originou a PI", max_length=120)
    tipo_pi = models.CharField("Tipo de PI", max_length=80)
    numero_pedido_inpi = models.CharField("Número do Pedido no INPI", max_length=80)
    empresa_estrangeira = models.CharField("Empresa que licenciou é estrangeira?", max_length=10)
    razao_social = models.CharField("Razão social da empresa", max_length=200)
    cnpj = models.CharField("CNPJ", max_length=30, blank=True)
    pais_sede = models.CharField("País sede da empresa que licenciou", max_length=100)
    participacao_resultados = models.TextField(
        "Participação nos resultados da exploração do licenciamento", blank=True
    )
    observacoes = models.TextField("Observações", blank=True)

    class Meta(RegistroSemestralBase.Meta):
        verbose_name = "12. Licenciamento de PIs"


class RegFinAssociadas(RegistroSemestralBase):
    """Aba 13. Acompanhamento Associadas (FIN)."""

    razao_social = models.CharField("Razão social da entidade", max_length=200)
    nome_fantasia = models.CharField("Nome fantasia da entidade", max_length=200)
    cnpj = models.CharField("CNPJ", max_length=30)
    eh_startup = models.CharField("A empresa é uma startup?", max_length=10)
    data_inicio_associacao = models.DateField("Data de início da associação")
    categoria_at = models.CharField("Categoria da AT que a empresa se associou", max_length=80)
    associacao_vigente = models.CharField("Associação da entidade ainda está vigente?", max_length=10)
    data_encerramento = models.DateField(
        "Data de encerramento da associação", null=True, blank=True
    )
    contrib_ano1 = models.DecimalField("Contribuição Ano 1 (R$)", max_digits=14, decimal_places=2, default=0)
    contrib_ano2 = models.DecimalField("Contribuição Ano 2 (R$)", max_digits=14, decimal_places=2, default=0)
    contrib_ano3 = models.DecimalField("Contribuição Ano 3 (R$)", max_digits=14, decimal_places=2, default=0)
    contrib_ano4 = models.DecimalField("Contribuição Ano 4 (R$)", max_digits=14, decimal_places=2, default=0)
    nome_contato = models.CharField("Nome do contato da entidade associada", max_length=160)
    cargo_contato = models.CharField("Cargo", max_length=140)
    email_contato = models.EmailField("Email do contato da entidade associada")
    part_pdi = models.CharField("Participação em projeto PD&I?", max_length=10)
    part_fcrh = models.CharField("Participação na ação FCRH?", max_length=10)
    part_acs = models.CharField("Participação nas ações ACS?", max_length=10)
    part_lic_pi = models.CharField("Licenciamento de PI?", max_length=10)
    doacao_infra = models.CharField("Doação de infraestrutura?", max_length=10)
    observacoes = models.TextField("Observações", blank=True)

    @property
    def contrib_total(self):
        return (self.contrib_ano1 or 0) + (self.contrib_ano2 or 0) + (self.contrib_ano3 or 0) + (self.contrib_ano4 or 0)

    class Meta(RegistroSemestralBase.Meta):
        verbose_name = "13. Acompanhamento Associadas"


class RegFinCoopNacional(RegistroSemestralBase):
    """Aba 14. Cooperação Nacional (FIN)."""

    nome_instituicao = models.CharField("Nome da Instituição", max_length=200)
    cidade_instituicao = models.CharField("Cidade da Instituição", max_length=120)
    data_inicio = models.DateField("Data de início da cooperação")
    vigente = models.CharField("Cooperação ainda vigente?", max_length=10)
    data_encerramento = models.DateField("Data de encerramento da cooperação", null=True, blank=True)
    codigos_projetos = models.CharField("Código(s) do(s) projeto(s)", max_length=255, blank=True)
    instrumento_formalizacao = models.CharField("Instrumento que formaliza a cooperação", max_length=180)
    nome_contato = models.CharField("Nome do contato na Instituição", max_length=160)
    cargo_contato = models.CharField("Cargo do contato na Instituição", max_length=140)
    email_contato = models.EmailField("Email do contato na Instituição")
    objetivo = models.TextField("Objetivo da cooperação")
    resultados_atividades = models.TextField("Resultados e atividades até o momento")
    observacoes = models.TextField("Observações", blank=True)

    class Meta(RegistroSemestralBase.Meta):
        verbose_name = "14. Cooperação Nacional"


class RegFinCoopInternacional(RegistroSemestralBase):
    """Aba 15. Cooperação Internacional (FIN)."""

    nome_instituicao = models.CharField("Nome da Instituição", max_length=200)
    pais = models.CharField("País", max_length=100)
    cidade = models.CharField("Cidade", max_length=120)
    data_inicio = models.DateField("Data de início da cooperação")
    vigente = models.CharField("Cooperação ainda vigente?", max_length=10)
    data_encerramento = models.DateField("Data de encerramento da cooperação", null=True, blank=True)
    codigos_projetos = models.CharField("Código(s) do(s) projeto(s)", max_length=255, blank=True)
    instrumento_formalizacao = models.CharField("Instrumento que formaliza a cooperação", max_length=180)
    nome_contato = models.CharField("Nome do contato na Instituição", max_length=160)
    cargo_contato = models.CharField("Cargo do contato na Instituição", max_length=140)
    email_contato = models.EmailField("Email do contato na Instituição")
    objetivo = models.TextField("Objetivo da cooperação")
    resultados_atividades = models.TextField("Resultados e atividades até o momento")
    observacoes = models.TextField("Observações", blank=True)

    class Meta(RegistroSemestralBase.Meta):
        verbose_name = "15. Cooperação Internacional"


class RegFinMidia(RegistroSemestralBase):
    """Aba 16. Mídia (FIN)."""

    titulo_publicacao = models.CharField("Título da publicação", max_length=255)
    veiculo_divulgacao = models.CharField("Nome do veículo de divulgação", max_length=180)
    porta_voz_fonte = models.CharField("Porta-voz/Fonte", max_length=160)
    link_publicacao = models.URLField("Link da publicação", max_length=500)
    data_publicacao = models.DateField("Data da publicação")
    observacoes = models.TextField("Observações", blank=True)

    class Meta(RegistroSemestralBase.Meta):
        verbose_name = "16. Mídia"


class RegFinEventos(RegistroSemestralBase):
    """Aba 17. Eventos (FIN)."""

    titulo_evento = models.CharField("Título do evento", max_length=255)
    tipo_evento = models.CharField("Tipo de evento", max_length=120)
    formato_evento = models.CharField("Formato do evento", max_length=40)
    tipo_participacao = models.CharField("Tipo de participação do CC", max_length=120)
    local_realizacao = models.CharField("Local de realização (Cidade/Estado/País)", max_length=180)
    data_realizacao = models.DateField("Data de realização")
    participantes_cc = models.TextField("Nome dos Participantes do CC")
    resultado_alcancado = models.TextField("Resultado alcançado com a participação")
    entidades_contatadas = models.TextField("Entidades às quais foram feitos contatos", blank=True)
    observacoes = models.TextField("Observações", blank=True)

    class Meta(RegistroSemestralBase.Meta):
        verbose_name = "17. Eventos"


class RegFinConselho(RegistroSemestralBase):
    """Aba 18. Conselho Consultivo (FIN)."""

    nome_membro = models.CharField("Nome do membro", max_length=180)
    cpf = models.CharField("CPF", max_length=20)
    instituicao_vinculada = models.CharField("Nome da instituição vinculada", max_length=200)
    categoria_representante = models.CharField("Categoria (representante)", max_length=140)
    nivel_representacao = models.CharField("Nível de representação", max_length=60)
    duracao_mandato_anos = models.DecimalField("Duração do mandato (em anos)", max_digits=5, decimal_places=1)
    data_entrada = models.DateField("Data de entrada do Conselho")
    membro_ativo = models.CharField("Membro ativo?", max_length=10)
    data_saida = models.DateField("Data de saída do Conselho", null=True, blank=True)
    observacoes = models.TextField("Observações", blank=True)

    class Meta(RegistroSemestralBase.Meta):
        verbose_name = "18. Conselho Consultivo"


# ---------------------------------------------------------------------------
# PLANILHA 2 — PILAR FCRH
# ---------------------------------------------------------------------------


class RegFcrhProjeto(RegistroSemestralBase):
    """Aba 2. Info projetos FCRH (FCRH)."""

    titulo = models.CharField("Título do Projeto de Formação e Capacitação de RH", max_length=255)
    objetivo = models.TextField("Objetivo")
    descricao_publica = models.TextField("Descrição Pública")
    ementa_detalhada = models.TextField("Ementa detalhada")
    carga_horaria_total = models.DecimalField("Carga horária total", max_digits=8, decimal_places=1)
    publico_alvo = models.CharField("Público alvo do curso", max_length=255)
    status_atual = models.CharField("Status atual do projeto", max_length=60)
    valor_total_planejado = models.DecimalField(
        "Valor total planejado do projeto (todas as fontes)", max_digits=14, decimal_places=2
    )
    data_inicio = models.DateField("Data real de início")
    data_termino = models.DateField("Data real de término", null=True, blank=True)
    qtd_iniciaram = models.PositiveIntegerField("Profissionais que iniciaram", default=0)
    qtd_concluiram = models.PositiveIntegerField("Profissionais que concluíram", default=0)
    tipo_formacao = models.CharField("Qual tipo de formação será realizada?", max_length=100)
    onde_realizada = models.CharField("Onde a formação será realizada?", max_length=160)
    vinculo_linhas_tematicas = models.CharField("Vínculo às linhas temáticas do CC", max_length=255)
    qtd_empresas_at = models.PositiveIntegerField("Qtd. empresas associadas à AT", default=0)
    observacoes = models.TextField("Observações", blank=True)

    def codigo_preview(self, seq=1, abrev="QIN"):
        if not self.data_inicio:
            return ""
        return f"{abrev}-FCRH-{self.data_inicio.year}-{self.data_inicio.month}-{self.data_inicio.day}-{seq}"

    class Meta(RegistroSemestralBase.Meta):
        verbose_name = "FCRH · 2. Info projetos FCRH"


class RegFcrhProfissional(RegistroSemestralBase):
    """Aba 3. Profissionais Capacitados (FCRH)."""

    nome_completo = models.CharField("Nome Completo", max_length=180)
    cpf = models.CharField("CPF", max_length=20)
    email = models.EmailField("Email")
    codigo_projeto = models.CharField("Código do projeto FCRH", max_length=120)
    vinculo_profissional = models.CharField("Vínculo deste profissional", max_length=120)
    data_conclusao = models.DateField("Data de conclusão da formação", null=True, blank=True)
    certificado_emitido = models.CharField("Certificado emitido?", max_length=80)
    link_certificados = models.URLField("Link para acesso aos certificados", max_length=500, blank=True)
    observacao = models.TextField("Observação", blank=True)

    class Meta(RegistroSemestralBase.Meta):
        verbose_name = "FCRH · 3. Profissionais Capacitados"


# ---------------------------------------------------------------------------
# PLANILHA 3 — PILAR ACS
# ---------------------------------------------------------------------------


class RegAcsProjetoPdi(RegistroSemestralBase):
    """Aba 2. Info projetos PD&I ACS (ACS)."""

    titulo = models.CharField("Título do Projeto PD&I ACS", max_length=255)
    ambiente_inovacao_aberta = models.CharField("Ambiente de inovação aberta?", max_length=10)
    forma_cooperada = models.CharField("Desenvolvido de forma cooperada?", max_length=10)
    objetivo = models.TextField("Objetivo")
    descricao_publica = models.TextField("Descrição Pública")
    trl_inicial = models.CharField("TRL Inicial", max_length=20)
    trl_final = models.CharField("TRL Final", max_length=20)
    status_atual = models.CharField("Status atual do projeto", max_length=60)
    valor_total_planejado = models.DecimalField("Valor total planejado", max_digits=14, decimal_places=2)
    qtd_pis_geradas = models.PositiveIntegerField("Quantidade de PIs geradas", default=0)
    qtd_publicacoes_geradas = models.PositiveIntegerField("Quantidade de publicações geradas", default=0)
    data_inicio = models.DateField("Data real de início")
    data_termino = models.DateField("Data real de término", null=True, blank=True)
    qtd_empresas_base_tec = models.PositiveIntegerField("Qtd. empresas de base tecnológica envolvidas", default=0)
    observacoes = models.TextField("Observações", blank=True)

    def codigo_preview(self, seq=1, abrev="QIN"):
        if not self.data_inicio:
            return ""
        return f"{abrev}-PJACS-{self.data_inicio.year}-{self.data_inicio.month}-{self.data_inicio.day}-{seq}"

    class Meta(RegistroSemestralBase.Meta):
        verbose_name = "ACS · 2. Info projetos PD&I ACS"


class RegAcsPedidoPi(RegistroSemestralBase):
    """Aba 2.1. Pedidos de PI (ACS)."""

    titulo_pi = models.CharField("Título da PI", max_length=255)
    codigo_projeto = models.CharField("Código do projeto PD&I ACS", max_length=120)
    tipo_pi = models.CharField("Tipo de pedido de proteção de PI no INPI", max_length=80)
    data_pedido = models.DateField("Data do pedido")
    numero_pedido_inpi = models.CharField("Número do Pedido no INPI", max_length=80)
    link = models.URLField("Link", max_length=500, blank=True)
    observacoes = models.TextField("Observações", blank=True)

    class Meta(RegistroSemestralBase.Meta):
        verbose_name = "ACS · 2.1. Pedidos de PI"


class RegAcsPublicacao(RegistroSemestralBase):
    """Aba 2.2. Publicações (ACS)."""

    titulo_publicacao = models.CharField("Título da publicação", max_length=255)
    codigo_projeto = models.CharField("Código do projeto PD&I ACS", max_length=120)
    data_publicacao_aceite = models.DateField("Data da publicação ou aceite")
    titulo_periodico = models.CharField("Título do periódico", max_length=255)
    classificacao_periodico = models.CharField("Classificação do periódico", max_length=80)
    autores = models.TextField("Nome(s) do(s) autor(es)")
    outras_informacoes = models.CharField("DOI, volume, página etc.", max_length=255, blank=True)
    link = models.URLField("Link", max_length=500, blank=True)
    observacoes = models.TextField("Observações", blank=True)

    class Meta(RegistroSemestralBase.Meta):
        verbose_name = "ACS · 2.2. Publicações"


class RegAcsProjetoFormacao(RegistroSemestralBase):
    """Aba 3. Info projetos Formação (ACS)."""

    titulo = models.CharField("Título do Projeto de Formação (ACS)", max_length=255)
    objetivo = models.TextField("Objetivo")
    descricao_publica = models.TextField("Descrição Pública")
    ementa_detalhada = models.TextField("Ementa detalhada")
    carga_horaria_total = models.DecimalField("Carga horária total", max_digits=8, decimal_places=1)
    publico_alvo = models.CharField("Público alvo do curso", max_length=255)
    status_atual = models.CharField("Status atual do projeto", max_length=60)
    valor_total_planejado = models.DecimalField("Valor total planejado", max_digits=14, decimal_places=2)
    data_inicio = models.DateField("Data real de início")
    data_termino = models.DateField("Data real de término", null=True, blank=True)
    qtd_iniciaram = models.PositiveIntegerField("Profissionais que iniciaram", default=0)
    qtd_concluiram = models.PositiveIntegerField("Profissionais que concluíram", default=0)
    tipo_formacao = models.CharField("Tipo de formação", max_length=100)
    onde_realizada = models.CharField("Onde realizada", max_length=160)
    vinculo_linhas_tematicas = models.CharField("Vínculo às linhas temáticas", max_length=255)
    observacoes = models.TextField("Observações", blank=True)

    def codigo_preview(self, seq=1, abrev="QIN"):
        if not self.data_inicio:
            return ""
        return f"{abrev}-FCRH-ACS-{self.data_inicio.year}-{self.data_inicio.month}-{self.data_inicio.day}-{seq}"

    class Meta(RegistroSemestralBase.Meta):
        verbose_name = "ACS · 3. Info projetos Formação"


class RegAcsProfissional(RegistroSemestralBase):
    """Aba 4. Profissionais Capacitados (ACS)."""

    nome_completo = models.CharField("Nome Completo", max_length=180)
    cpf = models.CharField("CPF", max_length=20)
    email = models.EmailField("Email")
    codigo_projeto = models.CharField("Código do projeto Formação (ACS)", max_length=120)
    vinculo_profissional = models.CharField("Vínculo deste profissional", max_length=120)
    data_conclusao = models.DateField("Data de conclusão da formação", null=True, blank=True)
    certificado_emitido = models.CharField("Certificado emitido?", max_length=80)
    link_certificados = models.URLField("Link para acesso aos certificados", max_length=500, blank=True)
    observacao = models.TextField("Observação", blank=True)

    class Meta(RegistroSemestralBase.Meta):
        verbose_name = "ACS · 4. Profissionais Capacitados"


class RegAcsEmpresa(RegistroSemestralBase):
    """Aba 5. Empresas envolvidas (ACS)."""

    razao_social = models.CharField("Razão social da empresa", max_length=200)
    nome_fantasia = models.CharField("Nome fantasia da empresa", max_length=200)
    codigo_projeto = models.CharField("Código do projeto ACS", max_length=120)
    cnpj = models.CharField("CNPJ", max_length=30)
    eh_ebt_ou_startup = models.CharField("É EBT ou Startup?", max_length=10)
    startup_atraida_criada = models.CharField("Startup atraída ou criada?", max_length=40)
    nome_contato = models.CharField("Nome do contato da empresa", max_length=160)
    cargo = models.CharField("Cargo", max_length=140)
    telefone = models.CharField("Telefone do contato", max_length=40)
    email = models.EmailField("Email do contato")
    houve_alavancagem = models.CharField("Houve alavancagem?", max_length=10)
    valor_alavancagem = models.DecimalField(
        "Valor da alavancagem (R$)", max_digits=14, decimal_places=2, null=True, blank=True
    )
    quem_realizou_alavancagem = models.CharField(
        "Quem realizou a alavancagem?", max_length=180, blank=True
    )
    modelo_alavancagem = models.CharField("Modelo de alavancagem", max_length=180, blank=True)
    observacao = models.TextField("Observação", blank=True)

    class Meta(RegistroSemestralBase.Meta):
        verbose_name = "ACS · 5. Empresas envolvidas"


# ---------------------------------------------------------------------------
# PLANILHA 4 — PILAR AFCCT
# ---------------------------------------------------------------------------


class RegAfcctProjetoPdi(RegistroSemestralBase):
    """Aba 2. Info Projetos PD&I AFCCT (AFCCT)."""

    titulo = models.CharField("Título do Projeto PD&I AFCCT", max_length=255)
    resumo_projeto = models.TextField("Resumo do projeto")
    descricao_publica = models.TextField("Descrição Pública")
    envolvimento_empresas_at = models.CharField(
        "Envolvimento de pesquisadores das empresas da AT?", max_length=10
    )
    nomes_profissionais_at = models.TextField("Nome(s) do(s) profissional(is) da AT", blank=True)
    empresas_at_vinculadas = models.TextField("Nome(s) da(s) empresa(s) da AT vinculada(s)", blank=True)
    trl_inicial = models.CharField("TRL Inicial", max_length=20)
    trl_final = models.CharField("TRL Final", max_length=20)
    status_atual = models.CharField("Status atual do projeto", max_length=60)
    resultados_executados = models.TextField("Resultados executados (até o momento)")
    valor_total_planejado = models.DecimalField("Valor total planejado", max_digits=14, decimal_places=2)
    qtd_pis_geradas = models.PositiveIntegerField("Quantidade de PIs geradas no período", default=0)
    qtd_publicacoes_geradas = models.PositiveIntegerField("Quantidade de publicações geradas no período", default=0)
    data_inicio = models.DateField("Data real de início")
    data_prevista_termino = models.DateField("Data prevista de término")
    data_real_termino = models.DateField("Data real de término", null=True, blank=True)
    cooperacao_nacional_internacional = models.CharField(
        "Cooperação nacional ou internacional?", max_length=60
    )
    observacoes = models.TextField("Observações", blank=True)

    def codigo_preview(self, seq=1, abrev="QIN"):
        if not self.data_inicio:
            return ""
        return f"{abrev}-AFCCT-{self.data_inicio.year}-{self.data_inicio.month}-{self.data_inicio.day}-{seq}"

    class Meta(RegistroSemestralBase.Meta):
        verbose_name = "AFCCT · 2. Info Projetos PD&I AFCCT"


class RegAfcctPedidoPi(RegistroSemestralBase):
    """Aba 2.1. Pedidos de PI (AFCCT)."""

    titulo_pi = models.CharField("Título da PI", max_length=255)
    codigo_projeto = models.CharField("Código do projeto PD&I AFCCT", max_length=120)
    tipo_pi = models.CharField("Tipo de PI", max_length=80)
    data_pedido = models.DateField("Data do pedido")
    numero_pedido_inpi = models.CharField("Número do Pedido no INPI", max_length=80)
    link = models.URLField("Link", max_length=500, blank=True)
    observacoes = models.TextField("Observações", blank=True)

    class Meta(RegistroSemestralBase.Meta):
        verbose_name = "AFCCT · 2.1. Pedidos de PI"


class RegAfcctPublicacao(RegistroSemestralBase):
    """Aba 2.2. Publicações (AFCCT)."""

    titulo_publicacao = models.CharField("Título da publicação em periódico", max_length=255)
    codigo_projeto = models.CharField("Código do projeto PD&I AFCCT", max_length=120)
    data_publicacao_aceite = models.DateField("Data da publicação ou aceite")
    titulo_periodico = models.CharField("Título do periódico", max_length=255)
    classificacao_periodico = models.CharField("Classificação do periódico", max_length=80)
    autores = models.TextField("Nome(s) do(s) autor(es)")
    outras_informacoes = models.CharField("DOI, volume, página etc.", max_length=255, blank=True)
    link = models.URLField("Link", max_length=500, blank=True)
    observacoes = models.TextField("Observações", blank=True)

    class Meta(RegistroSemestralBase.Meta):
        verbose_name = "AFCCT · 2.2. Publicações"


class RegAfcctProjetoFormacao(RegistroSemestralBase):
    """Aba 3. Info projetos Formação (AFCCT)."""

    titulo = models.CharField("Título do Projeto de Formação (colaboradores CC)", max_length=255)
    objetivo = models.TextField("Objetivo")
    descricao_publica = models.TextField("Descrição Pública")
    status_atual = models.CharField("Status atual do projeto", max_length=60)
    valor_total_planejado = models.DecimalField("Valor total planejado", max_digits=14, decimal_places=2)
    data_inicio = models.DateField("Data real de início")
    data_termino = models.DateField("Data real de término", null=True, blank=True)
    qtd_iniciaram = models.PositiveIntegerField("Profissionais que iniciaram", default=0)
    qtd_concluiram = models.PositiveIntegerField("Profissionais que concluíram", default=0)
    tipo_formacao = models.CharField("Qual tipo de formação será realizada?", max_length=100)
    onde_realizada = models.CharField("Onde a formação será realizada?", max_length=160)
    vinculo_linhas_tematicas = models.CharField("Vínculo às linhas temáticas do CC", max_length=255)
    observacoes = models.TextField("Observações", blank=True)

    def codigo_preview(self, seq=1, abrev="QIN"):
        if not self.data_inicio:
            return ""
        return f"{abrev}-AFCCT-FC-CC-{self.data_inicio.year}-{self.data_inicio.month}-{self.data_inicio.day}-{seq}"

    class Meta(RegistroSemestralBase.Meta):
        verbose_name = "AFCCT · 3. Info projetos Formação"


class RegAfcctProfissional(RegistroSemestralBase):
    """Aba 4. Profissionais Capacitados (AFCCT)."""

    nome_completo = models.CharField("Nome Completo", max_length=180)
    cpf = models.CharField("CPF", max_length=20)
    email = models.EmailField("Email")
    codigo_projeto = models.CharField("Código do projeto Formação (AFCCT)", max_length=120)
    vinculo_profissional = models.CharField("Vínculo deste profissional", max_length=120)
    data_conclusao = models.DateField("Data de conclusão da formação", null=True, blank=True)
    certificado_emitido = models.CharField("Certificado emitido?", max_length=80)
    link_certificados = models.URLField("Link para acesso aos certificados", max_length=500, blank=True)
    observacao = models.TextField("Observação", blank=True)

    class Meta(RegistroSemestralBase.Meta):
        verbose_name = "AFCCT · 4. Profissionais Capacitados"


# ---------------------------------------------------------------------------
# PLANILHA 5 — PILAR AT
# ---------------------------------------------------------------------------


class RegAtAtividade(RegistroSemestralBase):
    """Aba 2. Info atividades AT (AT)."""

    titulo = models.CharField("Título da atividade executada na AT", max_length=255)
    associadas_participantes = models.TextField("Quais associadas participaram?")
    objetivo = models.TextField("Objetivo")
    descricao_publica = models.TextField("Descrição Pública")
    status_atual = models.CharField("Status atual da atividade", max_length=60)
    valor_executado = models.DecimalField("Valor executado (se houver)", max_digits=14, decimal_places=2, default=0)
    origem_valor = models.CharField("Valor da AT ou outra fonte?", max_length=60)
    data_inicio = models.DateField("Data real de início")
    data_termino = models.DateField("Data real de término", null=True, blank=True)
    observacoes = models.TextField("Observações", blank=True)

    def codigo_preview(self, seq=1, abrev="QIN"):
        if not self.data_inicio:
            return ""
        return f"{abrev}-AT-{self.data_inicio.year}-{self.data_inicio.month}-{self.data_inicio.day}-{seq}"

    class Meta(RegistroSemestralBase.Meta):
        verbose_name = "AT · 2. Info atividades AT"


class RegAtProspeccao(RegistroSemestralBase):
    """Aba 3. Prospecção (AT)."""

    iniciativa = models.CharField("Iniciativa da prospecção", max_length=80)
    tipo_interacao = models.CharField("Tipo de interação com a Entidade", max_length=120)
    razao_social = models.CharField("Razão social da entidade", max_length=200)
    nome_fantasia = models.CharField("Nome fantasia da entidade", max_length=200)
    cnpj = models.CharField("CNPJ", max_length=30)
    data_prospeccao = models.DateField("Data da prospecção")
    nomes_contatos = models.CharField("Nome(s) do(s) contato(s)", max_length=200)
    cargo = models.CharField("Cargo", max_length=140)
    descricao_resultado = models.TextField("Breve descrição do resultado da prospecção")
    proposta_emitida = models.CharField("Foi emitida proposta para se associar?", max_length=10)
    resultado_proposta = models.CharField("Resultado da proposta", max_length=80, blank=True)
    observacoes = models.TextField("Observações", blank=True)

    class Meta(RegistroSemestralBase.Meta):
        verbose_name = "AT · 3. Prospecção"


# ---------------------------------------------------------------------------
# COMPARTILHADO — OUTROS COMENTÁRIOS (4 planilhas técnicas, célula mesclada B10:E14)
# ---------------------------------------------------------------------------


class RegOutrosComentarios(RegistroSemestralBase):
    """Abas `*. Outros comentários` (FCRH=4, ACS=6, AFCCT=5, AT=4)."""

    arquivo = models.CharField("Arquivo EMBRAPII", max_length=16)
    aba = models.CharField("Aba de origem", max_length=60)
    comentario = models.TextField("Outros comentários")

    class Meta(RegistroSemestralBase.Meta):
        verbose_name = "Outros comentários"
        verbose_name_plural = "Outros comentários"
