"""Dashboard anual, mensal e por pilar (RF-060 a RF-065, RF-070 a RF-073, RF-107 a RF-119)."""
from datetime import date

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from apps.highlights.models import DestaqueMensal
from apps.indicators.models import Indicador
from apps.pillars.models import Pilar
from apps.periods.models import Periodo
from apps.planning.forms import ALIASES_BASE, BASE_FIN, PainelFiltroForm
from apps.planning.services import ANOS
from apps.planning.views import contexto_painel, contexto_pilar

from .calculos import itens_do_periodo
from .permissions import (
    sem_permissao,
    usuario_pode_pilar,
)
from .prestacao import (
    anos_com_periodos,
    contexto_mensal,
    linhas_csv_semestre,
    painel_semestral,
    resolver_destaque,
    resolver_periodo,
    resolver_semestre,
)
from .utils import periodo_selecionado

URL_PADRAO_PAINEL = "/?ano=todos&base=fin"


def _hx_parcial(request):
    """Fragmento htmx só para swaps de filtro — nunca para navegação com boost.

    O sidebar usa hx-boost com hx-select="#main": se a view devolvesse o
    fragmento, o OOB atualizaria header/URL mas o #main jamais trocaria.
    """
    return bool(request.headers.get("HX-Request")) and not request.headers.get("HX-Boosted")


@login_required
def dashboard(request):
    """Painel anual (RF-107/RF-108/RF-118): `?ano=todos|2024..2027&base=fin|fis`."""
    params = request.GET
    if "periodo" in params and "ano" not in params and "base" not in params:
        try:
            ano_legado = date.fromisoformat(params.get("periodo", "")).year
        except ValueError:
            ano_legado = None
        destino = f"/?ano={ano_legado}&base=fin" if ano_legado in ANOS else URL_PADRAO_PAINEL
        return redirect(destino, permanent=True)
    if params:
        base_crua = (params.get("base") or "").strip().lower()
        if base_crua in ALIASES_BASE:
            form_previa = PainelFiltroForm({"ano": params.get("ano") or "todos"})
            ano_previo = form_previa["ano"].value() if form_previa.is_valid() else "todos"
            return redirect(f"/?ano={ano_previo}&base={ALIASES_BASE[base_crua]}")
    form = PainelFiltroForm(params or None)
    if params and not form.is_valid():
        return redirect(URL_PADRAO_PAINEL)
    ano_param = form.cleaned_data["ano"] if params else "todos"
    base_param = form.cleaned_data["base"] if params else BASE_FIN
    contexto = contexto_painel(ano_param, base_param, request.user)
    if _hx_parcial(request):
        return render(request, "dashboard/_fragmento.html", contexto)
    return render(request, "dashboard/anual.html", contexto)


@login_required
def mensal(request):
    """Prestação mensal no padrão do painel anual (L20): `?periodo=YYYY-MM-DD`."""
    params = request.GET
    estado, periodo = resolver_periodo(params)
    if estado == "invalido":
        if periodo is None:
            contexto = contexto_mensal(None, request.user)
            if _hx_parcial(request):
                return render(request, "dashboard/_fragmento_mensal.html", contexto)
            return render(request, "dashboard/mensal.html", contexto)
        return redirect(
            f"/prestacao/mensal/?periodo={periodo.competencia.isoformat()}")
    destaque = resolver_destaque(params, request.user)
    contexto = contexto_mensal(periodo, request.user, destaque)
    if _hx_parcial(request):
        return render(request, "dashboard/_fragmento_mensal.html", contexto)
    return render(request, "dashboard/mensal.html", contexto)


@login_required
def semestral(request):
    """Visão geral semestral no padrão do painel anual (L21): `?ano=&semestre=`."""
    params = request.GET
    estado, ano, semestre = resolver_semestre(params)
    if estado == "vazio":
        return render(request, "dashboard/semestral.html", {
            "anos": [], "ano": None, "semestre": None, "painel_semestral": None,
        })
    if estado == "canonico" and params:
        return redirect(f"/prestacao/semestral/?ano={ano}&semestre={semestre}")
    contexto = {"anos": anos_com_periodos(), "ano": ano, "semestre": semestre}
    contexto.update(painel_semestral(ano, semestre, request.user))
    if _hx_parcial(request):
        return render(request, "dashboard/_fragmento_semestral.html", contexto)
    return render(request, "dashboard/semestral.html", contexto)


@login_required
def semestral_csv(request):
    """CSV do semestre: `Mês;Pilar;Indicador;Meta;Realizado;% Executado`."""
    from django.http import HttpResponse

    estado, ano, semestre = resolver_semestre(request.GET)
    if estado == "vazio":
        return redirect("core:semestral")
    if estado == "canonico" and request.GET:
        return redirect(
            f"/prestacao/semestral/dados.csv?ano={ano}&semestre={semestre}")
    linhas = linhas_csv_semestre(ano, semestre, request.user)
    hoje = date.today().isoformat()
    resposta = HttpResponse(
        "﻿" + "\n".join(linhas) + "\n", content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = (
        f"attachment; filename=dados_quiin_semestre_{ano}_s{semestre}_{hoje}.csv"
    )
    return resposta


@login_required
def pilar(request, pk):
    """Painel anual do pilar + seção mensal (RF-120/RF-122)."""
    pilar_obj = get_object_or_404(Pilar, pk=pk)
    if not usuario_pode_pilar(request.user, pilar_obj):
        return sem_permissao(request)
    params = request.GET
    base_url = f"/pilar/{pilar_obj.pk}/"

    def _preservar_periodo(destino):
        periodo_param = params.get("periodo", "")
        try:
            date.fromisoformat(periodo_param)
        except ValueError:
            return destino
        return f"{destino}&periodo={periodo_param}"

    if params:
        base_crua = (params.get("base") or "").strip().lower()
        if base_crua in ALIASES_BASE:
            form_previa = PainelFiltroForm({"ano": params.get("ano") or "todos"})
            ano_previo = form_previa["ano"].value() if form_previa.is_valid() else "todos"
            return redirect(_preservar_periodo(
                f"{base_url}?ano={ano_previo}&base={ALIASES_BASE[base_crua]}"))
    form = PainelFiltroForm(params or None)
    if params and not form.is_valid():
        return redirect(_preservar_periodo(f"{base_url}?ano=todos&base=fin"))
    ano_param = form.cleaned_data["ano"] if params else "todos"
    base_param = form.cleaned_data["base"] if params else BASE_FIN
    contexto = contexto_pilar(pilar_obj, ano_param, base_param, request.user)
    periodo, periodos = periodo_selecionado(request)
    itens = []
    destaques = []
    if periodo is not None:
        indicadores = Indicador.objects.filter(pilar=pilar_obj, ativo=True)
        itens = itens_do_periodo(indicadores, periodo)
        destaques = DestaqueMensal.objects.filter(periodo=periodo).filter(Q(pilar=pilar_obj) | Q(pilar__isnull=True)).select_related("pilar").order_by("-criado_em")
    contexto = {
        "pilar": pilar_obj, "periodo": periodo, "periodos": periodos,
        "itens": itens, "destaques": destaques,
    }
    contexto.update(contexto_pilar(pilar_obj, ano_param, base_param, request.user))
    if _hx_parcial(request):
        return render(request, "dashboard/_fragmento_pilar.html", contexto)
    return render(request, "dashboard/pilar.html", contexto)


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


