"""seed_demo — base demonstrativa local do Portal QuIIN (idempotente).

Uso:
    python manage.py seed_demo
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.audit.services import registrar_auditoria
from apps.core.permissions import garantir_grupos
from apps.crm_at.models import Empresa, Oportunidade
from apps.entries.models import Lancamento
from apps.entries.services import aprovar, salvar_ou_enviar
from apps.finance.models import FinanceiroConsolidado, ImportacaoFinanceira
from apps.highlights.models import DestaqueMensal
from apps.indicators.models import Indicador, Meta
from apps.periods.models import Periodo
from apps.periods.services import abrir_periodo, fechar_periodo
from apps.pillars.models import Pilar, UsuarioPilar
from apps.talentos.models import Alocacao, Colaborador, Competencia

USUARIOS = [
    ("erica", "erica123", "Érica (coordenação)", "Master"),
    ("clarissa", "clarissa123", "Clarissa (apoio operacional)", "Admin"),
    ("focal_pdi", "focal123", "Focal PDI", "PontoFocal"),
    ("focal_formacao", "focal123", "Focal Formação", "PontoFocal"),
    ("focal_startups", "focal123", "Focal Startups", "PontoFocal"),
    ("focal_at", "focal123", "Focal AT", "PontoFocal"),
    ("lideranca", "lider123", "Liderança", "Lideranca"),
    ("auditor", "auditor123", "Auditoria", "Auditor"),
]

PILARES = [
    ("PDI", "PDI / FCCT", 1),
    ("FORMACAO", "Formação e Capacitação de RH", 2),
    ("STARTUPS", "Atração e Criação de Startups", 3),
    ("AT", "Associação Tecnológica", 4),
    ("INFRA", "Infraestrutura", 5),
    ("OUTRASFONTES", "Financeiro e Outras Fontes", 6),
]

INDICADORES = [
    ("PDI", "PDI-PROJ-INI", "Projetos iniciados", "projetos", "QTD", False),
    ("PDI", "PDI-PROJ-AND", "Projetos em andamento", "projetos", "QTD", False),
    ("PDI", "PDI-PROJ-CONC", "Projetos concluídos", "projetos", "QTD", False),
    ("PDI", "PDI-ARTIGOS", "Artigos publicados", "artigos", "QTD", True),
    ("PDI", "PDI-PI", "Pedidos de propriedade intelectual", "pedidos", "QTD", True),
    ("FORMACAO", "FORM-CURSOS", "Cursos lançados", "cursos", "QTD", True),
    ("FORMACAO", "FORM-MATRICULAS", "Matrículas", "matrículas", "QTD", True),
    ("FORMACAO", "FORM-FORMADOS", "Pessoas formadas", "pessoas", "QTD", True),
    ("STARTUPS", "STA-ATRAIDAS", "Startups atraídas", "startups", "QTD", True),
    ("STARTUPS", "STA-CNPJ-CRIADOS", "CNPJs criados", "CNPJs", "QTD", True),
    ("STARTUPS", "STA-CAPACITADOS", "Profissionais capacitados", "pessoas", "QTD", True),
    ("AT", "AT-CNPJ-NOVOS", "CNPJs novos", "CNPJs", "QTD", True),
    ("AT", "AT-RENOVACOES", "Renovações assinadas", "renovações", "QTD", True),
    ("AT", "AT-CAPTACAO", "Captação AT", "R$", "MON", False),
    ("AT", "AT-PIPELINE", "Pipeline ativo", "empresas", "QTD", False),
    ("INFRA", "INFRA-EXECUCAO", "Execução de infraestrutura", "R$", "MON", False),
    ("OUTRASFONTES", "FIN-EXEC-PDI", "Execução PDI", "R$", "MON", True),
    ("OUTRASFONTES", "FIN-EXEC-FORM", "Execução Formação", "R$", "MON", True),
    ("OUTRASFONTES", "FIN-EXEC-STA", "Execução Startups", "R$", "MON", True),
    ("OUTRASFONTES", "FIN-EXEC-INFRA", "Execução Infraestrutura", "R$", "MON", True),
    ("OUTRASFONTES", "FIN-CAPT-AT", "Captação AT", "R$", "MON", True),
    ("OUTRASFONTES", "FIN-OUTRAS-FONTES", "Outras fontes", "R$", "MON", True),
]

# (codigo_indicador, periodicidade, valor, acumulado_ytd)
METAS = [
    ("PDI-PROJ-INI", "MENSAL", 2),
    ("PDI-PROJ-AND", "MENSAL", 12),
    ("PDI-PROJ-CONC", "MENSAL", 1),
    ("PDI-ARTIGOS", "ANUAL", 20),
    ("PDI-PI", "ANUAL", 8),
    ("FORM-CURSOS", "MENSAL", 1),
    ("FORM-MATRICULAS", "MENSAL", 60),
    ("FORM-FORMADOS", "MENSAL", 45),
    ("STA-ATRAIDAS", "MENSAL", 1),
    ("STA-CNPJ-CRIADOS", "MENSAL", 2),
    ("STA-CAPACITADOS", "MENSAL", 20),
    ("AT-CNPJ-NOVOS", "ANUAL", 129),
    ("AT-RENOVACOES", "ANUAL", 40),
    ("AT-CAPTACAO", "ANUAL", 7_750_000),
    ("AT-PIPELINE", "MENSAL", 10),
    ("INFRA-EXECUCAO", "ANUAL", 10_000_000),
    ("FIN-EXEC-PDI", "ANUAL", 29_000_000),
    ("FIN-EXEC-FORM", "ANUAL", 14_000_000),
    ("FIN-EXEC-STA", "ANUAL", 7_000_000),
    ("FIN-EXEC-INFRA", "ANUAL", 10_000_000),
    ("FIN-CAPT-AT", "ANUAL", 7_750_000),
    ("FIN-OUTRAS-FONTES", "ANUAL", 6_300_000),
]

# Valores mensais de demonstração por indicador (2026-05 e 2026-06)
VALORES = {
    "PDI-PROJ-INI": "1",
    "PDI-PROJ-AND": "8",
    "PDI-PROJ-CONC": "0",
    "PDI-ARTIGOS": "2",
    "PDI-PI": "1",
    "FORM-CURSOS": "1",
    "FORM-MATRICULAS": "55",
    "FORM-FORMADOS": "40",
    "STA-ATRAIDAS": "1",
    "STA-CNPJ-CRIADOS": "2",
    "STA-CAPACITADOS": "15",
    "AT-CNPJ-NOVOS": "5",
    "AT-RENOVACOES": "3",
    "AT-CAPTACAO": "500000",
    "AT-PIPELINE": "9",
    "INFRA-EXECUCAO": "250000",
    "FIN-EXEC-PDI": "400000",
    "FIN-EXEC-FORM": "250000",
    "FIN-EXEC-STA": "120000",
    "FIN-EXEC-INFRA": "180000",
    "FIN-CAPT-AT": "600000",
    "FIN-OUTRAS-FONTES": "800000",
}

# Status especiais no período aberto (2026-06) para demonstração
RASCUNHO_JUNHO = {"PDI-PROJ-CONC"}
ENVIADO_JUNHO = {"FORM-CURSOS"}
DEVOLVIDO_JUNHO = {"AT-PIPELINE"}

FINANCEIRO_MENSAL = {
    "PDI": ("EMBRAPII", 0, 400_000),
    "FORMACAO": ("EMBRAPII", 0, 250_000),
    "STARTUPS": ("EMBRAPII", 0, 120_000),
    "INFRA": ("EMBRAPII", 0, 180_000),
    "AT": ("AT", 600_000, 150_000),
    "OUTRASFONTES": ("OUTRAS_FONTES", 800_000, 100_000),
}

# Task B — CRM AT demo (100% fictício): (nome, cnpj, status)
CRM_EMPRESAS = [
    ("Metalúrgica Exemplo S.A.", "11.111.111/0001-11", "ASSOCIADA"),
    ("Banco Fictício do Sul S.A.", "22.222.222/0001-22", "ASSOCIADA"),
    ("Startup Demo Quântica LTDA", "33.333.333/0001-33", "PROSPECT"),
    ("Consultoria Encerada LTDA", "44.444.444/0001-44", "EX_ASSOCIADA"),
]

# Task B — (empresa_nome, fase, tipo, valor_previsto); pipeline em aberto = 934597
CRM_OPORTUNIDADES = [
    ("Startup Demo Quântica LTDA", "PROSPECCAO", "NOVO_CNPJ", "150000"),
    ("Banco Fictício do Sul S.A.", "NEGOCIACAO", "NOVO_CNPJ", "564000"),
    ("Metalúrgica Exemplo S.A.", "RENOVACAO", "RENOVACAO", "220597"),
    ("Consultoria Encerada LTDA", "PERDIDO", "NOVO_CNPJ", "50000"),
]

# Task B — talentos demo (100% fictício)
TALENTOS_COMPETENCIAS = ["Gestão de Eventos", "Python", "Óptica Quântica"]

# (nome, cargo, pilar_codigo, competencias, lattes_url)
TALENTOS_COLABORADORES = [
    (
        "Ana Demonstração",
        "Analista de Projetos",
        "AT",
        ("Gestão de Eventos", "Python"),
        "https://lattes.cnpq.br/0000000000000000",
    ),
    ("Bruno Exemplo", "Pesquisador Sênior", "PDI", ("Óptica Quântica",), ""),
    ("Carla Modelo", "Designer de Eventos", "STARTUPS", ("Gestão de Eventos",), ""),
]

# (colaborador_nome, projeto_ou_area, horas_semanais, data_inicio, data_fim)
TALENTOS_ALOCACOES = [
    ("Ana Demonstração", "Apoio AT — Arena QuIIN", 10, date(2026, 6, 1), None),
    ("Bruno Exemplo", "Projeto PDI-07", 30, date(2026, 1, 5), date(2026, 3, 31)),
]


class Command(BaseCommand):
    help = "Cria a base de demonstração local do Portal QuIIN (idempotente)."

    def handle(self, *args, **options):
        garantir_grupos()
        usuarios = self._usuarios()
        pilares = self._pilares()
        self._vinculos(usuarios, pilares)
        indicadores = self._indicadores(pilares)
        self._metas(indicadores)

        erica = usuarios["erica"]
        periodo_maio = self._periodo(date(2026, 5, 1))
        periodo_junho = self._periodo(date(2026, 6, 1))
        self._periodo(date(2026, 7, 1))

        abrir_periodo(periodo_maio, erica)
        self._lancamentos_mes(periodo_maio, indicadores, usuarios, aprovado=True)
        fechar_periodo(periodo_maio, erica)

        abrir_periodo(periodo_junho, erica)
        self._lancamentos_junho(periodo_junho, indicadores, usuarios, erica)
        self._financeiro_ytd(periodo_junho, pilares)
        self._crm()
        self._talentos(pilares)
        self._highlights(periodo_junho, pilares, erica)
        self._auditoria_demo(erica, usuarios)

        self.stdout.write(self.style.SUCCESS(
            "Base demo pronta: 8 usuários, 6 pilares, 22 indicadores, períodos 2026-05/06/07, "
            "CRM com 4 empresas e 4 oportunidades (pipeline em aberto R$ 934.597,00), "
            "talentos com 3 colaboradores e 2 alocações, highlights com 2 destaques em junho/2026."
        ))

    # ---------- helpers ----------

    def _usuarios(self):
        grupos = {g.name: g for g in Group.objects.all()}
        resultado = {}
        for username, senha, nome, grupo in USUARIOS:
            superuser = username == "erica"
            usuario, _ = User.objects.update_or_create(
                username=username,
                defaults={
                    "nome": nome,
                    "email": f"{username}@quiin.demo",
                    "is_active": True,
                    "is_staff": superuser,
                    "is_superuser": superuser,
                },
            )
            usuario.set_password(senha)
            usuario.groups.set([grupos[grupo]])
            usuario.save()
            resultado[username] = usuario
        return resultado

    def _pilares(self):
        resultado = {}
        for codigo, nome, ordem in PILARES:
            pilar, _ = Pilar.objects.update_or_create(
                codigo=codigo,
                defaults={"nome": nome, "ordem": ordem, "ativo": True, "descricao": f"Pilar {nome}."},
            )
            resultado[codigo] = pilar
        return resultado

    def _vinculos(self, usuarios, pilares):
        vinculos = {
            "focal_pdi": "PDI",
            "focal_formacao": "FORMACAO",
            "focal_startups": "STARTUPS",
            "focal_at": "AT",
        }
        for username, pilar_cod in vinculos.items():
            UsuarioPilar.objects.get_or_create(usuario=usuarios[username], pilar=pilares[pilar_cod])

    def _indicadores(self, pilares):
        resultado = {}
        for pilar_cod, codigo, nome, unidade, tipo, acumulado in INDICADORES:
            ind, _ = Indicador.objects.update_or_create(
                pilar=pilares[pilar_cod],
                codigo=codigo,
                defaults={
                    "nome": nome,
                    "unidade": unidade,
                    "tipo": tipo,
                    "acumulado": acumulado,
                    "ativo": True,
                    "descricao": f"Indicador {nome}.",
                },
            )
            resultado[codigo] = ind
        return resultado

    def _metas(self, indicadores):
        inicio, fim = date(2026, 1, 1), date(2026, 12, 31)
        for codigo, periodicidade, valor in METAS:
            Meta.objects.update_or_create(
                indicador=indicadores[codigo],
                versao=1,
                defaults={
                    "competencia_inicio": inicio,
                    "competencia_fim": fim,
                    "periodicidade": periodicidade,
                    "valor": Decimal(str(valor)),
                    "ativo": True,
                },
            )

    def _periodo(self, competencia):
        periodo, _ = Periodo.objects.update_or_create(
            competencia=competencia,
            defaults={"status": "PLANEJADO"},
        )
        return periodo

    def _dados_mes(self):
        return {
            codigo: {"valor": valor, "comentario": "Valor de demonstração."}
            for codigo, valor in VALORES.items()
        }

    def _lancamentos_mes(self, periodo, indicadores, usuarios, aprovado=True):
        por_pilar = {ind.pilar_id: [] for ind in indicadores.values()}
        dados = {ind.pk: {"valor": VALORES[ind.codigo], "comentario": "Valor de demonstração."} for ind in indicadores.values()}
        for ind in indicadores.values():
            por_pilar[ind.pilar_id].append(ind)

        for pilar_id, lista in por_pilar.items():
            pilar = lista[0].pilar
            criador = self._criador_do_pilar(pilar, usuarios)
            sub = {str(ind.pk): dados[ind.pk] for ind in lista}
            salvar_ou_enviar(periodo, pilar, criador, sub, enviar=True)
        if aprovado:
            for lc in Lancamento.objects.filter(periodo=periodo, status="ENVIADO"):
                aprovar(lc, usuarios["erica"])

    def _lancamentos_junho(self, periodo, indicadores, usuarios, erica):
        self._lancamentos_mes(periodo, indicadores, usuarios, aprovado=False)
        for codigo in RASCUNHO_JUNHO:
            lc = Lancamento.objects.get(periodo=periodo, indicador=indicadores[codigo])
            lc.status = "RASCUNHO"
            lc.save()
        for codigo in DEVOLVIDO_JUNHO:
            lc = Lancamento.objects.get(periodo=periodo, indicador=indicadores[codigo])
            lc.status = "DEVOLVIDO"
            lc.comentario_revisao = "Faltam evidências. Envie o comprovante do pipeline."
            lc.usuario_aprovacao = erica
            lc.save()

    def _criador_do_pilar(self, pilar, usuarios):
        vinculo = UsuarioPilar.objects.filter(pilar=pilar).select_related("usuario").first()
        if vinculo:
            return vinculo.usuario
        return usuarios["clarissa"]

    def _financeiro_ytd(self, periodo_junho, pilares):
        for mes in range(1, 6):
            competencia = date(2026, mes, 1)
            periodo, _ = Periodo.objects.update_or_create(competencia=competencia, defaults={"status": "FECHADO"})
            for pilar_cod, (tipo, captado, executado) in FINANCEIRO_MENSAL.items():
                FinanceiroConsolidado.objects.update_or_create(
                    periodo=periodo,
                    pilar=pilares[pilar_cod],
                    tipo_recurso=tipo,
                    defaults={
                        "valor_captado": Decimal(captado),
                        "valor_executado": Decimal(executado),
                        "observacao": "Consolidado de demonstração.",
                    },
                )
        qs = ImportacaoFinanceira.objects.filter(periodo=periodo_junho, arquivo_nome="financeiro_demo.csv")
        if qs.count() > 1:
            qs.exclude(pk=qs.order_by("pk").first().pk).delete()
        ImportacaoFinanceira.objects.update_or_create(
            periodo=periodo_junho,
            arquivo_nome="financeiro_demo.csv",
            defaults={"status": "SUCESSO", "usuario": None, "log": "Arquivo de exemplo presente em data/seed/financeiro_demo.csv."},
        )

    def _crm(self):
        empresas = {}
        for nome, cnpj, status in CRM_EMPRESAS:
            empresa, _ = Empresa.objects.update_or_create(
                nome=nome,
                defaults={"cnpj": cnpj, "status": status},
            )
            empresas[nome] = empresa
        for nome, fase, tipo, valor in CRM_OPORTUNIDADES:
            Oportunidade.objects.update_or_create(
                empresa=empresas[nome],
                fase=fase,
                tipo=tipo,
                defaults={
                    "valor_previsto": Decimal(valor),
                    "observacao": "Oportunidade de demonstração.",
                },
            )
        return empresas

    def _talentos(self, pilares):
        competencias = {}
        for nome in TALENTOS_COMPETENCIAS:
            competencia, _ = Competencia.objects.get_or_create(nome=nome)
            competencias[nome] = competencia
        colaboradores = {}
        for nome, cargo, pilar_cod, nomes_comp, lattes in TALENTOS_COLABORADORES:
            colaborador, _ = Colaborador.objects.update_or_create(
                nome=nome,
                defaults={
                    "cargo": cargo,
                    "pilar_principal": pilares[pilar_cod],
                    "lattes_url": lattes,
                },
            )
            colaborador.competencias.set([competencias[n] for n in nomes_comp])
            colaboradores[nome] = colaborador
        for nome_col, projeto, horas, inicio, fim in TALENTOS_ALOCACOES:
            Alocacao.objects.update_or_create(
                colaborador=colaboradores[nome_col],
                projeto_ou_area=projeto,
                data_inicio=inicio,
                defaults={"horas_semanais": horas, "data_fim": fim},
            )
        return colaboradores

    def _highlights(self, periodo_junho, pilares, erica):
        # periodo_junho já vem do helper _periodo (período ABERTO junho/2026);
        # não chamar _periodo aqui de novo para não regredir o status a PLANEJADO.
        DestaqueMensal.objects.update_or_create(
            periodo=periodo_junho,
            pilar=None,
            titulo="Arena QuIIN reúne 113 empreendedores",
            defaults={
                "descricao": "Demonstração: arena de negócios reuniu 113 empreendedores no período.",
                "tipo": "DESTAQUE",
                "criado_por": erica,
            },
        )
        DestaqueMensal.objects.update_or_create(
            periodo=periodo_junho,
            pilar=pilares["AT"],
            titulo="Fechar 2 renovações em negociação",
            defaults={
                "descricao": "Demonstração: priorizar o fechamento de 2 renovações em negociação nos próximos 30 dias.",
                "tipo": "FOCO_30_DIAS",
                "criado_por": erica,
            },
        )

    def _auditoria_demo(self, erica, usuarios):
        registrar_auditoria(erica, "LOGIN", "Sessao", campo="login", valor_novo="sucesso")
        registrar_auditoria(
            usuarios["focal_pdi"], "ENVIAR_LANCAMENTO", "Lancamento",
            campo="status", valor_novo="ENVIADO", justificativa="Demonstração",
        )
