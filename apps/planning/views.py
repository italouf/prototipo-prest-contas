"""Edição auditada e exportações do plano anual (L7, RF-113/RF-114/RN-021)."""
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.audit.services import registrar_auditoria
from apps.core.permissions import (
    pilares_editaveis_painel,
    pode_editar_painel,
    sem_permissao,
    usuario_pode_pilar,
)
from apps.core.templatetags.core_extras import numero_curto
from apps.pillars.models import Pilar

from .charts import geometria_consolidado, geometria_fonte
from .forms import BASE_FIN, PainelFiltroForm
from .models import PlanoAnual
from .services import ANOS, BASES, grade_edicao, painel as painel_anual, painel_pilar

LIMITE_VALOR = Decimal(10) ** 10
ACAO_BAIXAR = "baixar"


def contexto_painel(ano_param, base_param, usuario):
    """Contexto completo do painel anual (usado pela view `/` e pelo export)."""
    ano = None if ano_param == "todos" else int(ano_param)
    painel = painel_anual(ano, base_param)
    destaque = None if ano is None else ANOS.index(ano)
    editaveis = (
        set(pilares_editaveis_painel(usuario).values_list("codigo", flat=True))
        if usuario and usuario.is_authenticated else set()
    )
    return {
        "painel": painel,
        "ano_param": ano_param,
        "base_param": base_param,
        "geo_fonte": {
            chave: geometria_fonte(
                [float(v) for v in bloco["serie_previsto"]],
                [float(v) for v in bloco["serie_executado"]],
                destaque,
            )
            for chave, bloco in painel["graficos"].items()
        },
        "geo_consolidado": geometria_consolidado(
            {s["nome"]: [float(v) for v in s["valores"]] for s in painel["consolidado"]["series"]},
            destaque,
        ),
        "grade_edicao": grade_edicao(base_param, editaveis or None),
        "base_plano": painel["base"],
        "pode_editar_painel": pode_editar_painel(usuario),
    }


def _filtros_ou_padrao(params):
    form = PainelFiltroForm(params or None)
    if params and not form.is_valid():
        return None
    ano = form.cleaned_data["ano"] if params else "todos"
    base = form.cleaned_data["base"] if params else BASE_FIN
    return ano, base


def _resolver_pilar_escopo(request, fonte):
    """Resolve `?pilar=<pk>` (ou campo POST): (pilar|None, resposta_erro|None).

    404 se o pk não existe; 403 se o usuário não enxerga o pilar.
    """
    pk = (fonte.get("pilar") or "").strip()
    if not pk:
        return None, None
    pilar = get_object_or_404(Pilar, pk=pk)
    if not usuario_pode_pilar(request.user, pilar):
        return None, sem_permissao(request)
    return pilar, None


def contexto_pilar(pilar, ano_param, base_param, usuario):
    """Contexto do painel anual do pilar (usado pela view e pelo export)."""
    ano = None if ano_param == "todos" else int(ano_param)
    pp = painel_pilar(pilar, ano, base_param)
    destaque = None if ano is None else ANOS.index(ano)
    editaveis = (
        set(pilares_editaveis_painel(usuario).values_list("codigo", flat=True))
        if usuario and usuario.is_authenticated else set()
    )
    return {
        "painel_pilar": pp,
        "ano_param": ano_param,
        "base_param": base_param,
        "geo_pilar": geometria_fonte(
            [float(v) for v in pp["serie_previsto"]],
            [float(v) for v in pp["serie_executado"]],
            destaque,
        ),
        "grade_edicao": grade_edicao(base_param, ({pilar.codigo} & editaveis) or {"__nenhum__"}),
        "base_plano": pp["base"],
        "pilar_pk": pilar.pk,
        "pode_editar_pilar": pilar.codigo in editaveis,
    }


def _parse_grade(post, codigos_permitidos):
    """Devolve [(ano, pilar, base, campo, valor)] ou levanta ValueError/PermissionError."""
    pilares = {p.codigo: p for p in Pilar.objects.filter(ativo=True)}
    itens = []
    for chave, bruto in post.items():
        if not chave.startswith("v__"):
            continue
        partes = chave.split("__")
        if len(partes) != 5:
            raise ValueError(f"campo inválido: {chave}")
        _, ano_s, base, codigo, campo = partes
        if not ano_s.isdigit() or int(ano_s) not in ANOS:
            raise ValueError(f"ano inválido: {chave}")
        if base not in BASES:
            raise ValueError(f"base inválida: {chave}")
        if codigo not in pilares:
            raise ValueError(f"pilar inválido: {chave}")
        if campo not in ("previsto", "executado"):
            raise ValueError(f"campo inválido: {chave}")
        if codigo not in codigos_permitidos:
            raise PermissionError(codigo)
        try:
            valor = Decimal(str(bruto).strip().replace(" ", "").replace(",", "."))
        except InvalidOperation:
            raise ValueError(f"valor inválido: {chave}")
        if valor < 0 or valor >= LIMITE_VALOR:
            raise ValueError(f"valor fora do intervalo: {chave}")
        if base == "fisico" and valor != valor.to_integral_value():
            raise ValueError(f"base física exige inteiro: {chave}")
        itens.append((int(ano_s), pilares[codigo], base, campo, valor))
    return itens


@login_required
@require_POST
def aplicar(request):
    """Aplica a grade de edição (atômico + auditado) ou aplica e baixa o HTML."""
    if not pode_editar_painel(request.user):
        return sem_permissao(request)
    pilar_escopo, erro = _resolver_pilar_escopo(request, request.POST)
    if erro is not None:
        return erro
    filtros = _filtros_ou_padrao({"ano": request.POST.get("ano", "todos"), "base": request.POST.get("base", "fin")})
    ano_param, base_param = filtros or ("todos", "fin")
    destino = (
        f"/pilar/{pilar_escopo.pk}/?ano={ano_param}&base={base_param}"
        if pilar_escopo is not None
        else f"/?ano={ano_param}&base={base_param}"
    )
    permitidos = set(pilares_editaveis_painel(request.user).values_list("codigo", flat=True))
    if pilar_escopo is not None:
        if pilar_escopo.codigo not in permitidos:
            return sem_permissao(request)
        permitidos &= {pilar_escopo.codigo}
    try:
        itens = _parse_grade(request.POST, permitidos)
    except PermissionError:
        return sem_permissao(request)
    except ValueError as exc:
        messages.error(request, f"Edição rejeitada: {exc}")
        return redirect(destino)
    with transaction.atomic():
        for ano, pilar, base, campo, valor in itens:
            obj, _ = PlanoAnual.objects.get_or_create(
                ano=ano, pilar=pilar, base=base, defaults={"previsto": 0, "executado": 0})
            anterior = getattr(obj, campo)
            if anterior == valor:
                continue
            setattr(obj, campo, valor)
            obj.atualizado_por = request.user
            obj.save(update_fields=[campo, "atualizado_em", "atualizado_por"])
            registrar_auditoria(
                request.user, "EDITAR_PLANO_ANUAL", "PlanoAnual", registro_id=str(obj.pk),
                campo=campo, valor_anterior=str(anterior), valor_novo=str(valor),
            )
    if request.POST.get("acao") == ACAO_BAIXAR:
        return exportar_html(request, ano_param, base_param,
                             pilar_pk=pilar_escopo.pk if pilar_escopo else None)
    messages.success(request, "Plano anual atualizado.")
    return redirect(destino)


@login_required
def exportar_csv(request):
    """CSV da visão corrente (ano × base), opcionalmente recortado por pilar."""
    filtros = _filtros_ou_padrao(request.GET)
    if filtros is None:
        return redirect("/?ano=todos&base=fin")
    ano_param, base_param = filtros
    pilar_escopo, erro = _resolver_pilar_escopo(request, request.GET)
    if erro is not None:
        return erro
    if pilar_escopo is not None:
        return _csv_pilar(request, pilar_escopo, ano_param, base_param)
    ano = None if ano_param == "todos" else int(ano_param)
    painel = painel_anual(ano, base_param)
    unidade = "R$ milhoes" if painel["base"] == "financeiro" else "metas"
    periodo = painel["rotulo_periodo"]
    linhas = ["Bloco;Item;Indicador;Unidade;Período;Valor"]
    for grupo in painel["tabela"]["grupos"]:
        bloco = grupo["bloco"]
        captacao = bloco != "4.1 PPI"
        for linha in grupo["linhas"]:
            if linha.get("total"):
                continue
            ref = "Captado" if captacao else "Projetado"
            linhas.append(f"{bloco};{linha['rotulo']};{ref};{unidade};{periodo};{numero_curto(linha['previsto'])}")
            linhas.append(f"{bloco};{linha['rotulo']};Executado;{unidade};{periodo};{numero_curto(linha['executado'])}")
    hoje = date.today().isoformat()
    resposta = HttpResponse("﻿" + "\n".join(linhas) + "\n", content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = f"attachment; filename=dados_quiin_{base_param}_{ano_param}_{hoje}.csv"
    return resposta


def _csv_pilar(request, pilar, ano_param, base_param):
    """CSV do pilar: `Pilar;Ano;Previsto;Executado;Saldo;% Executado` (RF-125)."""
    from .services import ROTULOS_PAINEL

    ano = None if ano_param == "todos" else int(ano_param)
    pp = painel_pilar(pilar, ano, base_param)
    rotulo = ROTULOS_PAINEL.get(pilar.codigo, pilar.nome)
    linhas = ["Pilar;Ano;Previsto;Executado;Saldo;% Executado"]
    for linha in pp["tabela"]:
        pct = f"{linha['pct']}%" if linha["pct"] is not None else "—"
        linhas.append(
            f"{rotulo};{linha['rotulo']};{numero_curto(linha['previsto'])};"
            f"{numero_curto(linha['executado'])};{numero_curto(linha['saldo'])};{pct}"
        )
    hoje = date.today().isoformat()
    resposta = HttpResponse("﻿" + "\n".join(linhas) + "\n", content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = (
        f"attachment; filename=dados_quiin_{base_param}_{ano_param}_{pilar.codigo}_{hoje}.csv"
    )
    return resposta


def _html_standalone(ano_param, base_param, usuario, pilar=None):
    import re

    from django.contrib.staticfiles.finders import find
    from django.template.loader import render_to_string

    if pilar is None:
        contexto = contexto_painel(ano_param, base_param, usuario)
        template = "dashboard/standalone.html"
    else:
        contexto = contexto_pilar(pilar, ano_param, base_param, usuario)
        template = "dashboard/standalone_pilar.html"
    caminho_css = find("css/tailwind.css")
    contexto["standalone_css"] = open(caminho_css, encoding="utf-8").read() if caminho_css else ""
    caminho_sprite = find("icons/sprite.svg")
    sprite = open(caminho_sprite, encoding="utf-8").read() if caminho_sprite else ""
    contexto["standalone_sprite"] = re.sub(r"<\?xml.*?\?>", "", sprite)
    contexto["standalone"] = True
    html = render_to_string(template, contexto)
    html = re.sub(r"/static/icons/sprite[^\"'#]*\.svg", "", html)
    return html


def exportar_html(request, ano_param="todos", base_param="fin", pilar_pk=None):
    """HTML standalone da visão corrente (RF-114/RF-126)."""
    filtros = _filtros_ou_padrao({"ano": ano_param, "base": base_param})
    ano_param, base_param = filtros or ("todos", "fin")
    pilar = None
    if pilar_pk is not None:
        pilar, erro = _resolver_pilar_escopo(request, {"pilar": str(pilar_pk)})
        if erro is not None:
            return erro
    html = _html_standalone(ano_param, base_param, request.user, pilar)
    hoje = date.today().isoformat()
    sufixo = f"_{pilar.codigo}" if pilar is not None else ""
    resposta = HttpResponse(html, content_type="text/html; charset=utf-8")
    resposta["Content-Disposition"] = (
        f"attachment; filename=dashboard_quiin_{base_param}_{ano_param}{sufixo}_{hoje}.html"
    )
    return resposta


@login_required
def download_html(request):
    filtros = _filtros_ou_padrao(request.GET)
    if filtros is None:
        return redirect("/?ano=todos&base=fin")
    pilar_pk = (request.GET.get("pilar") or "").strip() or None
    return exportar_html(request, *filtros, pilar_pk=pilar_pk)
