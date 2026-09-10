"""Dashboard consolidado e por pilar (RF-060 a RF-065, RF-070 a RF-073)."""
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render

from apps.entries.models import Lancamento
from apps.finance.models import FinanceiroConsolidado
from apps.highlights.models import DestaqueMensal
from apps.indicators.models import Indicador
from apps.pillars.models import Pilar

from .calculos import itens_do_periodo
from .dashboard import avisos_do_dashboard, graficos_dados, heatmap_por_pilar, kpi_por_pilar
from .permissions import eh_gestor, pilares_visiveis, sem_permissao, usuario_pode_pilar
from .utils import periodo_selecionado

MESES_ABREV = ["", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


@login_required
def dashboard(request):
    periodo, periodos = periodo_selecionado(request)
    contexto = {
        "periodo": periodo,
        "periodos": periodos,
        "linhas": [],
        "cards": {},
        "pendencias": [],
        "chart_financeiro": [],
        "chart_mensal": [],
        "status_counts": {},
        "eh_gestor": eh_gestor(request.user),
        "destaques": [],
        "kpis": [],
        "heatmap": [],
        "avisos": [],
        "destaque_pilar": "",
        "chart_mensal_json": "[]",
        "chart_financeiro_json": "[]",
    }
    if periodo is None:
        return render(request, "home.html", contexto)

    pilares = list(pilares_visiveis(request.user))
    ano = periodo.competencia.year
    fin_ytd = list(
        FinanceiroConsolidado.objects.filter(
            periodo__competencia__year=ano,
            periodo__competencia__lte=periodo.competencia,
            pilar__in=pilares,
        ).select_related("pilar", "periodo")
    )
    cards = {
        "execucao": sum((f.valor_executado or Decimal("0") for f in fin_ytd), Decimal("0")),
        "captacao_at": sum(
            (f.valor_captado or Decimal("0") for f in fin_ytd if f.tipo_recurso == "AT"), Decimal("0")
        ),
        "outras_fontes": sum(
            (f.valor_captado or Decimal("0") for f in fin_ytd if f.tipo_recurso == "OUTRAS_FONTES"),
            Decimal("0"),
        ),
    }
    codigos_cards = {
        "PDI-ARTIGOS": "artigos",
        "PDI-PI": "pi",
        "FORM-FORMADOS": "formados",
        "AT-CNPJ-NOVOS": "cnpjs",
        "STA-ATRAIDAS": "startups",
    }
    indicadores = list(
        Indicador.objects.filter(pilar__in=pilares, ativo=True)
        .select_related("pilar")
        .order_by("pilar__ordem", "codigo")
    )
    itens_todos = itens_do_periodo(indicadores, periodo)
    itens_por_pilar = {}
    for item in itens_todos:
        itens_por_pilar.setdefault(item["indicador"].pilar_id, []).append(item)
        chave = codigos_cards.get(item["indicador"].codigo)
        if chave:
            cards[chave] = {"nome": item["indicador"].nome, "dados": item}
    contexto["cards"] = cards

    linhas, pendencias = [], []
    for pilar in pilares:
        itens = itens_por_pilar.get(pilar.pk, [])
        linhas.append({"pilar": pilar, "itens": itens})
        faltantes = [i["indicador"] for i in itens if i["indicador"].tipo != "TXT" and i["realizado"] is None]
        pendencias.append({"pilar": pilar, "faltantes": faltantes})

    contexto.update(
        {
            "linhas": linhas,
            "pendencias": pendencias,
            "chart_financeiro": _chart_financeiro(fin_ytd),
            "chart_mensal": _chart_mensal(fin_ytd, ano),
            "status_counts": _status_counts(periodo, pilares),
        }
    )

    destaque_pilar = request.GET.get("destaque_pilar", "")
    destaques_qs = (
        DestaqueMensal.objects.filter(periodo=periodo)
        .filter(Q(pilar__isnull=True) | Q(pilar__in=pilares))
        .select_related("pilar")
        .order_by("-criado_em")
    )
    if destaque_pilar:
        destaques_qs = destaques_qs.filter(Q(pilar_id=destaque_pilar) | Q(pilar__isnull=True))
    contexto["destaques"] = destaques_qs[:6]
    contexto["destaque_pilar"] = destaque_pilar
    contexto["kpis"] = kpi_por_pilar(linhas)
    contexto["heatmap"] = heatmap_por_pilar(linhas)
    contexto["avisos"] = avisos_do_dashboard(
        periodo,
        pendencias,
        contexto["status_counts"],
        (contexto["status_counts"].get("ENVIADO") or {}).get("quantidade", 0),
    )
    contexto["chart_mensal_json"], contexto["chart_financeiro_json"] = graficos_dados(
        contexto["chart_mensal"], contexto["chart_financeiro"]
    )
    return render(request, "home.html", contexto)


@login_required
def pilar(request, pk):
    pilar_obj = get_object_or_404(Pilar, pk=pk)
    if not usuario_pode_pilar(request.user, pilar_obj):
        return sem_permissao(request)
    periodo, periodos = periodo_selecionado(request)
    itens = []
    destaques = []
    if periodo is not None:
        indicadores = Indicador.objects.filter(pilar=pilar_obj, ativo=True)
        itens = itens_do_periodo(indicadores, periodo)
        destaques = DestaqueMensal.objects.filter(periodo=periodo).filter(Q(pilar=pilar_obj) | Q(pilar__isnull=True)).select_related("pilar").order_by("-criado_em")
    return render(
        request,
        "dashboard/pilar.html",
        {"pilar": pilar_obj, "periodo": periodo, "periodos": periodos, "itens": itens, "destaques": destaques},
    )


@login_required
def pilar_drawer(request, pk):
    """Detalhe do pilar em drawer lateral (HTMX), respeitando o RBAC."""
    pilar_obj = get_object_or_404(Pilar, pk=pk)
    if not usuario_pode_pilar(request.user, pilar_obj):
        return HttpResponseForbidden("Sem permissão para este pilar.")
    periodo, _ = periodo_selecionado(request)
    itens = []
    if periodo is not None:
        indicadores = Indicador.objects.filter(pilar=pilar_obj, ativo=True)
        itens = itens_do_periodo(indicadores, periodo)
    return render(
        request,
        "partials/dashboard/drawer_pilar.html",
        {"pilar": pilar_obj, "periodo": periodo, "itens": itens},
    )


def _chart_financeiro(fin_ytd):
    """Captação × execução por pilar (barras horizontais)."""
    linhas = []
    por_pilar = {}
    for f in fin_ytd:
        dados = por_pilar.setdefault(f.pilar_id, {"nome": f.pilar.nome, "codigo": f.pilar.codigo, "captado": Decimal("0"), "executado": Decimal("0")})
        dados["captado"] += f.valor_captado or Decimal("0")
        dados["executado"] += f.valor_executado or Decimal("0")
    maior = max((max(d["captado"], d["executado"]) for d in por_pilar.values()), default=Decimal("0"))
    for d in por_pilar.values():
        d["pct_captado"] = _pct(d["captado"], maior)
        d["pct_executado"] = _pct(d["executado"], maior)
        linhas.append(d)
    return sorted(linhas, key=lambda x: x["codigo"])


def _chart_mensal(fin_ytd, ano):
    """Evolução mensal de captado × executado (agregado em memória)."""
    por_mes = {}
    for f in fin_ytd:
        chave = f.periodo.competencia
        dados = por_mes.setdefault(chave, {"captado": Decimal("0"), "executado": Decimal("0")})
        dados["captado"] += f.valor_captado or Decimal("0")
        dados["executado"] += f.valor_executado or Decimal("0")
    pontos = [
        {
            "rotulo": MESES_ABREV[competencia.month],
            "captado": dados["captado"],
            "executado": dados["executado"],
        }
        for competencia, dados in sorted(por_mes.items())
    ]
    maior = max((max(p["captado"], p["executado"]) for p in pontos), default=Decimal("0"))
    for p in pontos:
        p["pct_captado"] = _pct(p["captado"], maior)
        p["pct_executado"] = _pct(p["executado"], maior)
    return pontos


def _status_counts(periodo, pilares):
    """Distribuição de lançamentos por status no período (1 query agregada)."""
    agregado = Lancamento.objects.filter(periodo=periodo, indicador__pilar__in=pilares).aggregate(
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


def _pct(valor, maior):
    if not maior:
        return 0
    return round(float(valor / maior * 100), 1)
