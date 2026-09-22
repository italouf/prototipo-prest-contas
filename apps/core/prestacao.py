"""Agregações da prestação mensal no padrão do painel anual (L20).

Funções puras sobre os modelos operacionais (períodos, lançamentos,
financeiro, destaques); a view `core:mensal` é casca fina. Reusa
`itens_do_periodo` (batch), o farol de `planning.services` e a geometria
de `core.charts`. Séries monetárias saem em R$ mi.
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Count, Q

from apps.core.calculos import itens_do_periodo, itens_por_periodo
from apps.core.charts import geometria_barras
from apps.core.dashboard import avisos_do_dashboard, heatmap_por_pilar, kpi_por_pilar
from apps.core.permissions import pilares_visiveis
from apps.core.templatetags.core_extras import numero_curto
from apps.entries.models import Lancamento
from apps.finance.models import FinanceiroConsolidado
from apps.highlights.models import DestaqueMensal
from apps.indicators.models import Indicador
from apps.periods.models import Periodo
from apps.planning.services import faixa, pct_inteiro

MESES_ABREV = ["", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
               "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

DIMENSOES_BARRA = {
    "largura": 1100, "altura": 280,
    "pad": {"esq": 52, "dir": 20, "topo": 26, "base": 50},
    "larg_barra_max": 44, "espaco": 10,
}

ZERO = Decimal("0")
MI = Decimal("1000000")

CODIGOS_CARDS = {
    "PDI-ARTIGOS": "artigos",
    "PDI-PI": "pi",
    "FORM-FORMADOS": "formados",
    "AT-CNPJ-NOVOS": "cnpjs",
    "STA-ATRAIDAS": "startups",
}

URL_CANONICA = "/prestacao/mensal/"


def periodo_padrao():
    """Período aberto/reaberto mais recente; senão o mais recente; senão None."""
    return (
        Periodo.objects.filter(status__in=["ABERTO", "REABERTO"])
        .order_by("-competencia").first()
        or Periodo.objects.order_by("-competencia").first()
    )


def resolver_periodo(params):
    """(estado, periodo): "ok" | "padrao" (sem filtro) | "invalido" (302)."""
    bruto = (params.get("periodo") or "").strip()
    if not bruto:
        return "padrao", periodo_padrao()
    try:
        competencia = date.fromisoformat(bruto)
    except ValueError:
        return "invalido", periodo_padrao()
    periodo = Periodo.objects.filter(competencia=competencia).first()
    if periodo is None:
        return "invalido", periodo_padrao()
    return "ok", periodo


def resolver_destaque(params, usuario):
    """Pk do pilar do filtro de destaques; inválido ou invisível ⇒ ""."""
    bruto = (params.get("destaque_pilar") or "").strip()
    if not bruto.isdigit():
        return ""
    visiveis = {str(p.pk) for p in pilares_visiveis(usuario)}
    return bruto if bruto in visiveis else ""


def _status_counts(periodo, pilares):
    """Distribuição de lançamentos por status no período (1 query agregada)."""
    agregado = Lancamento.objects.filter(
        periodo=periodo, indicador__pilar__in=pilares).aggregate(
        total=Count("pk"),
        aprovado=Count("pk", filter=Q(status="APROVADO")),
        enviado=Count("pk", filter=Q(status="ENVIADO")),
        rascunho=Count("pk", filter=Q(status="RASCUNHO")),
        devolvido=Count("pk", filter=Q(status="DEVOLVIDO")),
    )
    total = agregado["total"] or 0
    counts = {}
    for status, chave in (
        ("APROVADO", "aprovado"),
        ("ENVIADO", "enviado"),
        ("RASCUNHO", "rascunho"),
        ("DEVOLVIDO", "devolvido"),
    ):
        n = agregado[chave] or 0
        counts[status] = {"quantidade": n, "pct": round((n / total * 100), 1) if total else 0}
    counts["total"] = total
    return counts


def _serie_mensal(fin_ano):
    """Captado × executado por mês do ano (12 grupos; valores em R$)."""
    por_mes = {
        mes: {"rotulo": MESES_ABREV[mes], "captado": ZERO, "executado": ZERO}
        for mes in range(1, 13)
    }
    for f in fin_ano:
        dados = por_mes[f.periodo.competencia.month]
        dados["captado"] += f.valor_captado or ZERO
        dados["executado"] += f.valor_executado or ZERO
    return [por_mes[mes] for mes in range(1, 13)]


def _serie_pilares(fin_ytd):
    """Captado × executado por pilar no acumulado (ordenado por código)."""
    por_pilar = {}
    for f in fin_ytd:
        dados = por_pilar.setdefault(f.pilar_id, {
            "nome": f.pilar.nome, "codigo": f.pilar.codigo,
            "captado": ZERO, "executado": ZERO})
        dados["captado"] += f.valor_captado or ZERO
        dados["executado"] += f.valor_executado or ZERO
    return sorted(por_pilar.values(), key=lambda d: d["codigo"])


def _em_milhoes(valor):
    return float((valor or ZERO) / MI)


def contexto_mensal(periodo, usuario, destaque_pilar=""):
    """Contexto completo da prestação mensal (usado pela view e pelos testes)."""
    periodos = Periodo.objects.order_by("-competencia")
    if periodo is None:
        return {
            "periodo": None, "periodos": periodos, "painel_mensal": None,
            "linhas": [], "cards": {}, "pendencias": [], "kpis": [],
            "heatmap": [], "avisos": [], "status_counts": {},
            "chart_mensal": [], "chart_financeiro": [],
            "geo_mensal": None, "geo_pilares": None,
            "bloco_mensal": None, "bloco_pilares": None,
            "destaques": [], "destaque_pilar": "",
        }
    pilares = list(pilares_visiveis(usuario))
    ano = periodo.competencia.year
    indicadores = list(
        Indicador.objects.filter(pilar__in=pilares, ativo=True)
        .select_related("pilar")
        .order_by("pilar__ordem", "codigo")
    )
    itens_todos = itens_do_periodo(indicadores, periodo)
    itens_por_pilar = {}
    for item in itens_todos:
        item["faixa"] = faixa(item["percentual"])
        itens_por_pilar.setdefault(item["indicador"].pilar_id, []).append(item)

    cards = {
        "execucao": ZERO, "captacao_at": ZERO, "outras_fontes": ZERO,
    }
    for item in itens_todos:
        chave = CODIGOS_CARDS.get(item["indicador"].codigo)
        if chave:
            cards[chave] = {"nome": item["indicador"].nome, "dados": item}

    linhas, pendencias = [], []
    for pilar in pilares:
        itens = itens_por_pilar.get(pilar.pk, [])
        linhas.append({"pilar": pilar, "itens": itens})
        faltantes = [i["indicador"] for i in itens
                     if i["indicador"].tipo != "TXT" and i["realizado"] is None]
        pendencias.append({"pilar": pilar, "faltantes": faltantes})

    fin_ano = list(
        FinanceiroConsolidado.objects.filter(
            periodo__competencia__year=ano, pilar__in=pilares)
        .select_related("pilar", "periodo")
    )
    fin_ytd = [f for f in fin_ano if f.periodo.competencia <= periodo.competencia]
    for f in fin_ytd:
        cards["execucao"] += f.valor_executado or ZERO
        if f.tipo_recurso == "AT":
            cards["captacao_at"] += f.valor_captado or ZERO
        elif f.tipo_recurso == "OUTRAS_FONTES":
            cards["outras_fontes"] += f.valor_captado or ZERO

    serie_mensal = _serie_mensal(fin_ano)
    serie_pilares = _serie_pilares(fin_ytd)
    eixos_meses = [(MESES_ABREV[mes], str(ano)) for mes in range(1, 13)]
    geo_mensal = geometria_barras(
        eixos_meses,
        [_em_milhoes(p["captado"]) for p in serie_mensal],
        [_em_milhoes(p["executado"]) for p in serie_mensal],
        periodo.competencia.month - 1, **DIMENSOES_BARRA)
    geo_pilares = geometria_barras(
        [(p["codigo"], "") for p in serie_pilares],
        [_em_milhoes(p["captado"]) for p in serie_pilares],
        [_em_milhoes(p["executado"]) for p in serie_pilares],
        None, **DIMENSOES_BARRA) if serie_pilares else None

    mes = serie_mensal[periodo.competencia.month - 1]
    pct_mes = pct_inteiro(mes["executado"], mes["captado"])
    bloco_mensal = {"nome_previsto": "Captado", "nome_executado": "Executado",
                    "rodape_pct": pct_mes, "rodape_faixa": faixa(pct_mes)}
    tot_cap = sum((p["captado"] for p in serie_pilares), ZERO)
    tot_exec = sum((p["executado"] for p in serie_pilares), ZERO)
    pct_ano = pct_inteiro(tot_exec, tot_cap)
    bloco_pilares = {"nome_previsto": "Captado", "nome_executado": "Executado",
                     "rodape_pct": pct_ano, "rodape_faixa": faixa(pct_ano)}

    status_counts = _status_counts(periodo, pilares)
    destaques_qs = (
        DestaqueMensal.objects.filter(periodo=periodo)
        .filter(Q(pilar__isnull=True) | Q(pilar__in=pilares))
        .select_related("pilar")
        .order_by("-criado_em")
    )
    if destaque_pilar:
        destaques_qs = destaques_qs.filter(
            Q(pilar_id=int(destaque_pilar)) | Q(pilar__isnull=True))
    return {
        "periodo": periodo, "periodos": periodos,
        "painel_mensal": {
            "rotulo_periodo": periodo.rotulo, "status": periodo.status,
            "status_display": periodo.get_status_display(),
            "n_pilares": len(pilares), "n_indicadores": len(indicadores),
        },
        "linhas": linhas, "cards": cards, "pendencias": pendencias,
        "kpis": kpi_por_pilar(linhas), "heatmap": heatmap_por_pilar(linhas),
        "avisos": avisos_do_dashboard(
            periodo, pendencias, status_counts,
            (status_counts.get("ENVIADO") or {}).get("quantidade", 0)),
        "status_counts": status_counts,
        "chart_mensal": serie_mensal, "chart_financeiro": serie_pilares,
        "geo_mensal": geo_mensal, "geo_pilares": geo_pilares,
        "bloco_mensal": bloco_mensal, "bloco_pilares": bloco_pilares,
        "destaques": destaques_qs[:6], "destaque_pilar": destaque_pilar,
    }


# ---------------------------------------------------------------------------
# Prestação semestral (L21): visão geral do semestre no padrão do anual.
# ---------------------------------------------------------------------------

def anos_com_periodos():
    """Anos com períodos, do mais recente ao mais antigo."""
    return sorted(
        {p.competencia.year for p in Periodo.objects.all()}, reverse=True)


def meses_do_semestre(ano, semestre):
    """Períodos do semestre em ordem cronológica."""
    ini, fim = (1, 6) if semestre == 1 else (7, 12)
    return list(
        Periodo.objects.filter(
            competencia__year=ano,
            competencia__month__gte=ini,
            competencia__month__lte=fim,
        ).order_by("competencia")
    )


def resolver_semestre(params):
    """(estado, ano, semestre): "ok" | "canonico" (302) | "vazio" (sem dados)."""
    anos = anos_com_periodos()
    padrao = periodo_padrao()
    if not anos or padrao is None:
        return "vazio", None, None
    ano_bruto = (params.get("ano") or "").strip()
    sem_bruto = (params.get("semestre") or "").strip()
    ano = int(ano_bruto) if ano_bruto.isdigit() and int(ano_bruto) in anos else None
    sem = int(sem_bruto) if sem_bruto in ("1", "2") else None
    if ano is not None and sem is not None:
        return "ok", ano, sem
    if ano is None:
        ano = padrao.competencia.year
    if sem is None:
        ult = Periodo.objects.filter(competencia__year=ano).order_by("-competencia").first()
        sem = 1 if ult.competencia.month <= 6 else 2
    return "canonico", ano, sem


def _pct_csv(p):
    if p is None:
        return "—"
    texto = format(
        Decimal(p).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP).normalize(), "f")
    return texto.replace(".", ",") + "%"


def painel_semestral(ano, semestre, usuario):
    """Visão geral do semestre: KPIs, financeiro, status, destaques e meses."""
    pilares = list(pilares_visiveis(usuario))
    periodos = meses_do_semestre(ano, semestre)
    indicadores = list(
        Indicador.objects.filter(pilar__in=pilares, ativo=True)
        .select_related("pilar")
        .order_by("pilar__ordem", "codigo")
    )
    por_periodo = itens_por_periodo(indicadores, periodos) if periodos else {}
    for itens in por_periodo.values():
        for item in itens:
            item["faixa"] = faixa(item["percentual"])

    tabela = []
    lc_por_periodo = {
        p.pk: {it["indicador"].pilar_id for it in por_periodo.get(p.pk, [])
               if it["lc"] is not None}
        for p in periodos
    }
    meses_com_dados = sum(1 for p in periodos if lc_por_periodo[p.pk])
    for pilar in pilares:
        pcts = [it["percentual"] for p in periodos
                for it in por_periodo.get(p.pk, [])
                if it["indicador"].pilar_id == pilar.pk
                and it["percentual"] is not None]
        atingidos = sum(1 for p in pcts if p >= 100)
        pendentes = sum(
            1 for p in periodos for it in por_periodo.get(p.pk, [])
            if it["indicador"].pilar_id == pilar.pk
            and it["indicador"].tipo != "TXT" and it["realizado"] is None)
        meses = sum(1 for p in periodos if pilar.pk in lc_por_periodo[p.pk])
        pct = sum(pcts, ZERO) / len(pcts) if pcts else None
        tabela.append({"pilar": pilar, "pct": pct, "faixa": faixa(pct),
                       "atingidos": atingidos, "pendentes": pendentes,
                       "meses": meses, "n_meses": len(periodos)})

    ini, fim = (1, 6) if semestre == 1 else (7, 12)
    fin = list(
        FinanceiroConsolidado.objects.filter(
            periodo__competencia__year=ano,
            periodo__competencia__month__gte=ini,
            periodo__competencia__month__lte=fim,
            pilar__in=pilares)
        .select_related("pilar", "periodo")
    )
    por_mes = {m: {"captado": ZERO, "executado": ZERO} for m in range(ini, fim + 1)}
    for f in fin:
        dados = por_mes[f.periodo.competencia.month]
        dados["captado"] += f.valor_captado or ZERO
        dados["executado"] += f.valor_executado or ZERO
    meses_serie = [(m, por_mes[m]) for m in range(ini, fim + 1)]
    eixos_meses = [(MESES_ABREV[m], str(ano)) for m in range(ini, fim + 1)]
    meses_idx = list(range(ini, fim + 1))
    pk_por_mes = {p.competencia.month: p.pk for p in periodos}
    com_dados = [i for i, m in enumerate(meses_idx)
                 if por_mes[m]["captado"] or por_mes[m]["executado"]
                 or any(it["realizado"] is not None
                        for it in por_periodo.get(pk_por_mes.get(m), []))]
    geo_meses = geometria_barras(
        eixos_meses,
        [_em_milhoes(d["captado"]) for _, d in meses_serie],
        [_em_milhoes(d["executado"]) for _, d in meses_serie],
        com_dados[-1] if com_dados else None, **DIMENSOES_BARRA)
    por_pilar = {}
    for f in fin:
        dados = por_pilar.setdefault(f.pilar_id, {
            "nome": f.pilar.nome, "codigo": f.pilar.codigo,
            "captado": ZERO, "executado": ZERO})
        dados["captado"] += f.valor_captado or ZERO
        dados["executado"] += f.valor_executado or ZERO
    serie_pilares = sorted(por_pilar.values(), key=lambda d: d["codigo"])
    geo_pilares = geometria_barras(
        [(p["codigo"], "") for p in serie_pilares],
        [_em_milhoes(p["captado"]) for p in serie_pilares],
        [_em_milhoes(p["executado"]) for p in serie_pilares],
        None, **DIMENSOES_BARRA) if serie_pilares else None

    tot_cap = sum((p["captado"] for p in serie_pilares), ZERO)
    tot_exec = sum((p["executado"] for p in serie_pilares), ZERO)
    pct_sem = pct_inteiro(tot_exec, tot_cap)
    cards = {"captado": tot_cap, "executado": tot_exec,
             "outras_fontes": sum(
                 (f.valor_captado or ZERO for f in fin
                  if f.tipo_recurso == "OUTRAS_FONTES"), ZERO)}

    agregado = Lancamento.objects.filter(
        periodo__in=periodos, indicador__pilar__in=pilares).aggregate(
        total=Count("pk"),
        aprovado=Count("pk", filter=Q(status="APROVADO")),
        enviado=Count("pk", filter=Q(status="ENVIADO")),
        rascunho=Count("pk", filter=Q(status="RASCUNHO")),
        devolvido=Count("pk", filter=Q(status="DEVOLVIDO")),
    )
    total = agregado["total"] or 0
    status_counts = {
        status: {"quantidade": agregado[chave] or 0,
                 "pct": round(((agregado[chave] or 0) / total * 100), 1) if total else 0}
        for status, chave in (("APROVADO", "aprovado"), ("ENVIADO", "enviado"),
                              ("RASCUNHO", "rascunho"), ("DEVOLVIDO", "devolvido"))
    }
    status_counts["total"] = total
    destaques = list(
        DestaqueMensal.objects.filter(periodo__in=periodos)
        .filter(Q(pilar__isnull=True) | Q(pilar__in=pilares))
        .select_related("pilar")
        .order_by("-criado_em")[:6]
    )
    ult = periodos[-1] if periodos else None
    linhas = []
    if ult is not None:
        por_pilar_ult = {}
        for item in por_periodo.get(ult.pk, []):
            por_pilar_ult.setdefault(item["indicador"].pilar_id, []).append(item)
        linhas = [{"pilar": pilar, "itens": por_pilar_ult.get(pilar.pk, [])}
                 for pilar in pilares]
    return {
        "ano": ano, "semestre": semestre,
        "painel_semestral": {
            "rotulo_periodo": f"{semestre}º semestre de {ano}",
            "n_meses": len(periodos), "n_pilares": len(pilares),
            "meses_dados": meses_com_dados,
        },
        "periodos": periodos, "meses": periodos, "por_periodo": por_periodo,
        "tabela": tabela, "linhas": linhas,
        "cards": cards, "status_counts": status_counts,
        "geo_meses": geo_meses, "geo_pilares": geo_pilares,
        "bloco_meses": {"nome_previsto": "Captado", "nome_executado": "Executado",
                        "rodape_pct": pct_sem, "rodape_faixa": faixa(pct_sem)},
        "bloco_pilares": {"nome_previsto": "Captado", "nome_executado": "Executado",
                          "rodape_pct": pct_sem, "rodape_faixa": faixa(pct_sem)},
        "destaques": destaques,
    }


def linhas_csv_semestre(ano, semestre, usuario):
    """Linhas `Mês;Pilar;Indicador;Meta;Realizado;% Executado` do semestre."""
    ctx = painel_semestral(ano, semestre, usuario)
    linhas = ["Mês;Pilar;Indicador;Meta;Realizado;% Executado"]
    for periodo in ctx["meses"]:
        for item in ctx["por_periodo"].get(periodo.pk, []):
            ind = item["indicador"]
            linhas.append(
                f"{periodo.rotulo};{ind.pilar.codigo};{ind.codigo};"
                f"{numero_curto(item['meta'])};{numero_curto(item['realizado'])};"
                f"{_pct_csv(item['percentual'])}")
    return linhas
