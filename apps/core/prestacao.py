"""Agregações da prestação mensal no padrão do painel anual (L20).

Funções puras sobre os modelos operacionais (períodos, lançamentos,
financeiro, destaques); a view `core:mensal` é casca fina. Reusa
`itens_do_periodo` (batch, sem N+1), o farol de `planning.services` e a
geometria de `core.charts`. Séries monetárias saem em R$ mi.
"""
from datetime import date
from decimal import Decimal

from django.db.models import Count, Q

from apps.core.calculos import itens_do_periodo
from apps.core.charts import geometria_barras
from apps.core.dashboard import avisos_do_dashboard, heatmap_por_pilar, kpi_por_pilar
from apps.core.permissions import pilares_visiveis
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
