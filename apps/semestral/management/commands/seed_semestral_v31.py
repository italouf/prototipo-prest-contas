"""Seed idempotente das listas oficiais EMBRAPII v3.1, pilares QuIIN e ciclos semestrais."""
from calendar import monthrange
from datetime import date, datetime, time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from openpyxl import load_workbook

from apps.accounts.models import User
from apps.pillars.models import Pilar
from apps.semestral.models import (
    CicloSemestral,
    CompetenciaMensalPilar,
    ConfiguracaoPilarSemestral,
    ListaDominioEmbrapii,
)

TEMPLATES_DIR = Path(settings.BASE_DIR) / "templates_embrapii" / "v3_1"

TEMPLATE_FILES = {
    "FIN": TEMPLATES_DIR / "fin_v3_1.xlsx",
    "FCRH": TEMPLATES_DIR / "fcrh_v3_1.xlsx",
    "ACS": TEMPLATES_DIR / "acs_v3_1.xlsx",
    "AFCCT": TEMPLATES_DIR / "afcct_v3_1.xlsx",
    "AT": TEMPLATES_DIR / "at_v3_1.xlsx",
}

# Listas declaradas inline nos DataValidations (stdDV) das planilhas v3.1
INLINE_VALIDATIONS = {
    "ACAO_OUTRAS_FONTES": (
        "FIN",
        "10. Conta Ação - Outras Fontes",
        "C11:C210",
        [
            "AFCCT",
            "FCRH",
            "ACS",
            "AT",
            "Ampliação de Infraestrutura",
            "Não vinculado a uma ação específica",
        ],
    ),
    "EQUIPE_TITULACAO": (
        "FIN",
        "11. Equipe",
        "E11:E1510",
        [
            "Nível médio",
            "Técnico(a)",
            "Graduado(a)",
            "Mestre",
            "Doutor(a)",
            "Pós-doutorado",
        ],
    ),
    "EVENTO_TIPO": (
        "FIN",
        "17. Eventos",
        "D10:D59",
        [
            "Seminário técnico",
            "Feiras e exposições",
            "Rodadas de negócios",
            "Fóruns Normativos",
            "Outros: especificar nas observações",
        ],
    ),
    "EVENTO_FORMATO": (
        "FIN",
        "17. Eventos",
        "E10:E854",
        ["Presencial", "Virtual", "Híbrido"],
    ),
    "EVENTO_PARTICIPACAO": (
        "FIN",
        "17. Eventos",
        "F10:F59",
        [
            "Expositor",
            "Organizador",
            "Palestrante",
            "Visitante",
            "Outros: especificar nas observações",
        ],
    ),
    "CONSELHO_NIVEL": (
        "FIN",
        "18. Conselho Consultivo",
        "G11:G60",
        ["Titular", "Suplente", "Presidente", "Vice-Presidente"],
    ),
    "STATUS_PROJETO_PADRAO": (
        "FCRH",
        "2. Info projetos FCRH",
        "J11:J210",
        ["Não iniciado", "Em andamento", "Concluído", "Atrasado", "Cancelado"],
    ),
    "TIPO_FORMACAO_FCRH": (
        "FCRH",
        "2. Info projetos FCRH",
        "P11:P210",
        [
            "Curso de curta duração",
            "Especialização Lato Sensu",
            "Mestrado",
            "Doutorado",
            "Pós-doutorado",
            "Outros",
        ],
    ),
    "TIPO_FORMACAO_AFCCT": (
        "AFCCT",
        "3. Info projetos Formação",
        "M11:M210",
        [
            "Curso de curta duração",
            "Especialização",
            "Mestrado",
            "Doutorado",
            "Pós-doutorado",
            "Outros",
        ],
    ),
    "ONDE_FORMACAO": (
        "FCRH",
        "2. Info projetos FCRH",
        "Q11:Q210",
        [
            "No próprio CC",
            "Em outra instituição nacional",
            "Em outra instituição internacional",
            "Em outra instituição nacional e internacional (Sanduíche)",
            "Outros",
        ],
    ),
    "VINCULO_FCRH": (
        "FCRH",
        "3. Profissionais Capacitados",
        "G10:G3233",
        [
            "Com uma empresa da AT",
            "Colaborador do CC",
            "Startup que participa das ações do CC",
            "Outros (especificar em observações)",
        ],
    ),
    "VINCULO_ACS": (
        "ACS",
        "4. Profissionais Capacitados",
        "G10:G2009",
        [
            "Profissional de startup vinculada ao Centro",
            "Profissional de startup não vinculada ao Centro",
            "Outros (detalhar em observações)",
        ],
    ),
    "VINCULO_AFCCT": (
        "AFCCT",
        "4. Profissionais Capacitados",
        "G10:G509",
        [
            "Quadro de pessoal",
            "Bolsista",
            "Aluno",
            "Outros (detalhar em observações)",
        ],
    ),
    "CERTIFICADO_EMITIDO": (
        "FCRH",
        "3. Profissionais Capacitados",
        "I10:I3233",
        ["Sim (reconhecido pelo MEC)", "Sim (não reconhecido pelo MEC)", "Não"],
    ),
    "STARTUP_ATRAIDA_CRIADA": (
        "ACS",
        "5. Empresas envolvidas",
        "H10:H2009",
        ["Atraída", "Criada", "Não se aplica"],
    ),
    "TRL_OPCOES": (
        "AFCCT",
        "2. Info Projetos PD&I AFCCT",
        "J11:K60",
        ["TRL 2", "TRL 3", "TRL 4", "TRL 5", "TRL 6"],
    ),
    "COOP_NAC_INT": (
        "AFCCT",
        "2. Info Projetos PD&I AFCCT",
        "T11:T60",
        [
            "Sim (Internacional)",
            "Sim (Nacional)",
            "Sim (Internacional e Nacional)",
            "Não",
        ],
    ),
    "ORIGEM_VALOR_AT": (
        "AT",
        "2. Info atividades AT",
        "J11:J60",
        ["Valor da AT", "Outra fonte", "Valor da AT + Outra fonte"],
    ),
    "INICIATIVA_PROSPECCAO": (
        "AT",
        "3. Prospecção",
        "C10:C109",
        ["EMBRAPII", "CC EMBRAPII", "Entidade / Cliente"],
    ),
    "TIPO_INTERACAO_AT": (
        "AT",
        "3. Prospecção",
        "D10:D109",
        [
            "CC EMBRAPII Day",
            "Visita à empresa",
            "Atendimento no CC EMBRAPII",
            "Fone ou teleconferência",
            "Reunião em evento de prospecção",
            "Outra: detalhar nas observações",
        ],
    ),
    "RESULTADO_PROPOSTA_AT": (
        "AT",
        "3. Prospecção",
        "M10:M109",
        ["Entidade realizou Associação", "Entidade não realizou Associação"],
    ),
}


def calcular_prazo_competencia(competencia: date, dia_limite: int) -> datetime:
    if competencia.month == 12:
        prox_ano, prox_mes = competencia.year + 1, 1
    else:
        prox_ano, prox_mes = competencia.year, competencia.month + 1
    ultimo_dia = monthrange(prox_ano, prox_mes)[1]
    dia = min(max(1, dia_limite), ultimo_dia)
    dt = datetime.combine(date(prox_ano, prox_mes, dia), time(18, 0))
    return timezone.make_aware(dt, timezone.get_current_timezone())


def _extrair_faixa(ws, min_col, max_col, min_row, max_row):
    rows = []
    for r in ws.iter_rows(
        min_row=min_row,
        max_row=max_row,
        min_col=min_col,
        max_col=max_col,
        values_only=True,
    ):
        rows.append(r)
    return rows


def seed_listas_oficiais():
    """Lê os templates gerenciados v3.1 e atualiza ListaDominioEmbrapii idempotentemente."""
    specs = []

    #FIN
    wb_fin = load_workbook(TEMPLATE_FILES["FIN"], read_only=True, data_only=True)
    ws_fin_listas = wb_fin["Listas"]
    specs.append(
        (
            "CONSELHO_REPRESENTACAO",
            "FIN",
            "Listas",
            "B10:B15",
            [(str(r[0]).strip(), "") for r in _extrair_faixa(ws_fin_listas, 2, 2, 10, 15) if r[0]],
        )
    )
    specs.append(
        (
            "OUTRAS_FONTES_ELEMENTO_AT",
            "FIN",
            "Listas",
            "B18:B32",
            [(str(r[0]).strip(), "") for r in _extrair_faixa(ws_fin_listas, 2, 2, 18, 32) if r[0]],
        )
    )
    specs.append(
        (
            "EQUIPE_FUNCAO",
            "FIN",
            "Listas",
            "C110:C117",
            [(str(r[0]).strip(), "") for r in _extrair_faixa(ws_fin_listas, 3, 3, 110, 117) if r[0]],
        )
    )
    specs.append(
        (
            "ASSOCIADA_CARGO",
            "FIN",
            "Listas",
            "B133:B185",
            [(str(r[0]).strip(), "") for r in _extrair_faixa(ws_fin_listas, 2, 2, 133, 185) if r[0]],
        )
    )
    specs.append(
        (
            "SIM_NAO",
            "FIN",
            "Listas",
            "J3:J4",
            [(str(r[0]).strip(), "") for r in _extrair_faixa(ws_fin_listas, 10, 10, 3, 4) if r[0]],
        )
    )
    wb_fin.close()

    # FCRH
    wb_fcrh = load_workbook(TEMPLATE_FILES["FCRH"], read_only=True, data_only=True)
    ws_fcrh_listas = wb_fcrh["Listas"]
    specs.append(
        (
            "CC_NOMES",
            "FCRH",
            "Listas",
            "B2:C9",
            [
                (str(r[0]).strip(), str(r[1] or "").strip())
                for r in _extrair_faixa(ws_fcrh_listas, 2, 3, 2, 9)
                if r[0]
            ],
        )
    )
    wb_fcrh.close()

    # AFCCT
    wb_afcct = load_workbook(TEMPLATE_FILES["AFCCT"], read_only=True, data_only=True)
    ws_afcct_listas = wb_afcct["Listas"]
    specs.append(
        (
            "AFCCT_STATUS_PROJETO",
            "AFCCT",
            "Listas",
            "D2:D5",
            [(str(r[0]).strip(), "") for r in _extrair_faixa(ws_afcct_listas, 4, 4, 2, 5) if r[0]],
        )
    )
    specs.append(
        (
            "PI_TIPO",
            "AFCCT",
            "Listas",
            "E2:E7",
            [(str(r[0]).strip(), "") for r in _extrair_faixa(ws_afcct_listas, 5, 5, 2, 7) if r[0]],
        )
    )
    specs.append(
        (
            "PUBLICACAO_CLASSIFICACAO",
            "AFCCT",
            "Listas",
            "F2:F4",
            [(str(r[0]).strip(), "") for r in _extrair_faixa(ws_afcct_listas, 6, 6, 2, 4) if r[0]],
        )
    )
    wb_afcct.close()

    # AT
    wb_at = load_workbook(TEMPLATE_FILES["AT"], read_only=True, data_only=True)
    ws_at_listas = wb_at["Listas"]
    specs.append(
        (
            "PROSPECCAO_CARGO",
            "AT",
            "Listas",
            "B12:B64",
            [(str(r[0]).strip(), "") for r in _extrair_faixa(ws_at_listas, 2, 2, 12, 64) if r[0]],
        )
    )
    wb_at.close()

    for categoria, (arquivo, aba, ref, valores) in INLINE_VALIDATIONS.items():
        specs.append((categoria, arquivo, aba, ref, [(v, "") for v in valores]))

    total = 0
    for categoria, arquivo, aba, ref, items in specs:
        for ordem, (valor, aux) in enumerate(items, start=1):
            ListaDominioEmbrapii.objects.update_or_create(
                categoria=categoria,
                valor=valor,
                defaults={
                    "arquivo_origem": arquivo,
                    "aba_origem": aba,
                    "referencia_celula": ref,
                    "codigo_auxiliar": aux,
                    "ordem": ordem,
                    "ativo": True,
                },
            )
            total += 1
    return total


def seed_pilares_e_ciclos(anos=(2026,)):
    """Cria/atualiza ConfiguracaoPilarSemestral QuIIN e ciclos semestrais padrão."""
    pilares_cfg = [
        (
            "FCRH",
            "FCRH — Formação e Capacitação de RH",
            "FCRH",
            "FORMACAO",
            "focal_formacao",
            "Focal FCRH (Formação)",
            "fcrh@quiin.local",
            1,
        ),
        (
            "ACS",
            "ACS — Atração e Criação de Startups",
            "ACS",
            "STARTUPS",
            "focal_startups",
            "Focal ACS (Startups)",
            "acs@quiin.local",
            2,
        ),
        (
            "AFCCT",
            "AFCCT — Ampliação e Fortalecimento de Competências",
            "AFCCT",
            "PDI",
            "focal_pdi",
            "Focal AFCCT (PD&I)",
            "afcct@quiin.local",
            3,
        ),
        (
            "AT",
            "AT — Associação Tecnológica",
            "AT",
            "AT",
            "focal_at",
            "Focal AT (Associação Tecnológica)",
            "at@quiin.local",
            4,
        ),
        (
            "FIN_QUIIN",
            "Financeiro QuIIN (Aba 10 + Abas Azuis 11–18)",
            "FIN",
            "OUTRASFONTES",
            "clarissa",
            "Clarissa (Gestão QuIIN / Apoio)",
            "financeiro.quiin@quiin.local",
            5,
        ),
    ]

    configs = []
    for codigo, nome, arquivo, pilar_cod, username, resp_nome, resp_email, ordem in pilares_cfg:
        pilar_obj = Pilar.objects.filter(codigo=pilar_cod).first()
        user_obj = User.objects.filter(username=username).first()
        nome_final = (user_obj.nome_exibicao if user_obj and user_obj.nome else resp_nome)
        email_final = (user_obj.email if user_obj and user_obj.email else resp_email)
        cfg, _ = ConfiguracaoPilarSemestral.objects.get_or_create(
            codigo=codigo,
            defaults={
                "nome": nome,
                "arquivo_embrapii": arquivo,
                "pilar": pilar_obj,
                "responsavel": user_obj,
                "responsavel_nome": nome_final,
                "responsavel_email": email_final,
                "dia_limite_mensal": 5,
                "ordem": ordem,
                "ativo": True,
            },
        )
        # Vincula pilar/responsável se ainda estiverem nulos
        changed = False
        if cfg.pilar is None and pilar_obj is not None:
            cfg.pilar = pilar_obj
            changed = True
        if cfg.responsavel is None and user_obj is not None:
            cfg.responsavel = user_obj
            changed = True
        if changed:
            cfg.save(update_fields=["pilar", "responsavel"])
        configs.append(cfg)

    ciclos = []
    for ano in anos:
        for semestre in (1, 2):
            ciclo, _ = CicloSemestral.objects.get_or_create(
                ano=ano,
                semestre=semestre,
                defaults={
                    "centro_competencia": "QuIIN (SENAI CIMATEC)",
                    "abreviacao_cc": "QIN",
                    "termo_cooperacao": "001/2023",
                    "periodo_referencia_label": f"{semestre}º semestre/{ano}",
                    "coordenacao_nome": "Mabel",
                    "coordenacao_email": "mabel.gestao@quiin.local",
                },
            )
            ciclos.append(ciclo)
            for cfg in configs:
                for comp_data in ciclo.competencias_datas:
                    CompetenciaMensalPilar.objects.get_or_create(
                        ciclo=ciclo,
                        configuracao_pilar=cfg,
                        competencia=comp_data,
                        defaults={
                            "prazo_limite": calcular_prazo_competencia(
                                comp_data, cfg.dia_limite_mensal
                            ),
                        },
                    )
    return configs, ciclos


class Command(BaseCommand):
    help = "Popula listas oficiais EMBRAPII v3.1, pilares QuIIN e ciclos semestrais."

    def add_arguments(self, parser):
        parser.add_argument("--ano", type=int, default=2026, help="Ano padrão a provisionar")

    @transaction.atomic
    def handle(self, *args, **options):
        total_listas = seed_listas_oficiais()
        configs, ciclos = seed_pilares_e_ciclos(anos=(options["ano"],))
        self.stdout.write(
            self.style.SUCCESS(
                f"Seed Semestral v3.1 concluído: {total_listas} itens de domínio, "
                f"{len(configs)} pilares QuIIN, {len(ciclos)} ciclos semestrais."
            )
        )
