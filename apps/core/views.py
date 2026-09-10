"""Dashboard consolidado e por pilar (RF-060 a RF-065, RF-070 a RF-073)."""
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render

from apps.entries.models import Lancamento
from apps.finance.models import FinanceiroConsolidado
from apps.highlights.models import DestaqueMensal
from apps.indicators.models import Indicador
from apps.pillars.models import Pilar

from .calculos import meta_realizado_percentual
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

    pilares = pilares_visiveis(request.user)
    ano = periodo.competencia.year
    fin_ytd = FinanceiroConsolidado.objects.filter(
        periodo__competencia__year=ano,
        periodo__competencia__lte=periodo.competencia,
        pilar__in=pilares,
    )
    pilares_ids = set(pilares.values_list("pk", flat=True))
    cards = {
        "execucao": fin_ytd.aggregate(t=Sum("valor_executado"))["t"] or Decimal("0"),
        "captacao_at": fin_ytd.filter(tipo_recurso="AT").aggregate(t=Sum("valor_captado"))["t"] or Decimal("0"),
        "outras_fontes": fin_ytd.filter(tipo_recurso="OUTRAS_FONTES").aggregate(t=Sum("valor_captado"))["t"] or Decimal("0"),
    }
    for chave, codigo in (
        ("artigos", "PDI-ARTIGOS"),
        ("pi", "PDI-PI"),
        ("formados", "FORM-FORMADOS"),
        ("cnpjs", "AT-CNPJ-NOVOS"),
        ("startups", "STA-ATRAIDAS"),
    ):
        card = _card_pilar(codigo, periodo, pilares_ids)
        if card is not None:
            cards[chave] = card
    contexto["cards"] = cards

    linhas, pendencias = [], []
    for pilar in pilares:
        indicadores = Indicador.objects.filter(pilar=pilar, ativo=True)
        itens = [{"indicador": ind, **meta_realizado_percentual(ind, periodo)} for ind in indicadores]
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
        itens = [{"indicador": ind, **meta_realizado_percentual(ind, periodo)} for ind in indicadores]
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
        itens = [{"indicador": ind, **meta_realizado_percentual(ind, periodo)} for ind in indicadores]
    return render(
        request,
        "partials/dashboard/drawer_pilar.html",
        {"pilar": pilar_obj, "periodo": periodo, "itens": itens},
    )


def _card(codigo, periodo):
    ind = Indicador.objects.filter(codigo=codigo).first()
    if not ind:
        return None
    return {"nome": ind.nome, "dados": meta_realizado_percentual(ind, periodo)}


def _card_pilar(codigo, periodo, pilares_ids):
    """Card de indicador só se o pilar for visível ao usuário."""
    ind = Indicador.objects.filter(codigo=codigo).first()
    if not ind:
        return None
    if ind.pilar_id not in pilares_ids:
        return None
    return {"nome": ind.nome, "dados": meta_realizado_percentual(ind, periodo)}


def _chart_financeiro(fin_ytd):
    """Captação × execução por pilar (barras horizontais)."""
    linhas = []
    por_pilar = {}
    for f in fin_ytd.select_related("pilar"):
        dados = por_pilar.setdefault(f.pilar_id, {"nome": f.pilar.nome, "codigo": f.pilar.codigo, "captado": Decimal("0"), "executado": Decimal("0")})
        dados["captado"] += f.valor_captado
        dados["executado"] += f.valor_executado
    maior = max((max(d["captado"], d["executado"]) for d in por_pilar.values()), default=Decimal("0"))
    for d in por_pilar.values():
        d["pct_captado"] = _pct(d["captado"], maior)
        d["pct_executado"] = _pct(d["executado"], maior)
        linhas.append(d)
    return sorted(linhas, key=lambda x: x["codigo"])


def _chart_mensal(fin_ytd, ano):
    """Evolução mensal de captado × executado (colunas)."""
    agregado = (
        fin_ytd.values("periodo__competencia")
        .annotate(captado=Sum("valor_captado"), executado=Sum("valor_executado"))
        .order_by("periodo__competencia")
    )
    pontos = []
    for item in agregado:
        competencia = item["periodo__competencia"]
        pontos.append(
            {
                "rotulo": MESES_ABREV[competencia.month],
                "captado": item["captado"] or Decimal("0"),
                "executado": item["executado"] or Decimal("0"),
            }
        )
    maior = max((max(p["captado"], p["executado"]) for p in pontos), default=Decimal("0"))
    for p in pontos:
        p["pct_captado"] = _pct(p["captado"], maior)
        p["pct_executado"] = _pct(p["executado"], maior)
    return pontos


def _status_counts(periodo, pilares):
    """Distribuição de lançamentos por status no período (pilares visíveis)."""
    qs = Lancamento.objects.filter(periodo=periodo, indicador__pilar__in=pilares)
    total = qs.count()
    counts = {}
    for status in ("APROVADO", "ENVIADO", "RASCUNHO", "DEVOLVIDO"):
        n = qs.filter(status=status).count()
        counts[status] = {
            "quantidade": n,
            "pct": round((n / total * 100), 1) if total else 0,
        }
    counts["total"] = total
    return counts


def _pct(valor, maior):
    if not maior:
        return 0
    return round(float(valor / maior * 100), 1)
