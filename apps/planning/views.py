"""Edição auditada e exportações do plano anual (L7, RF-113/RF-114/RN-021)."""
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.audit.services import registrar_auditoria
from apps.core.permissions import pilares_editaveis_painel, pode_editar_painel, sem_permissao
from apps.core.templatetags.core_extras import numero_curto
from apps.pillars.models import Pilar

from .charts import geometria_consolidado, geometria_fonte
from .forms import BASE_FIN, PainelFiltroForm
from .models import PlanoAnual
from .services import ANOS, BASES, grade_edicao, painel as painel_anual

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
    filtros = _filtros_ou_padrao({"ano": request.POST.get("ano", "todos"), "base": request.POST.get("base", "fin")})
    ano_param, base_param = filtros or ("todos", "fin")
    permitidos = set(pilares_editaveis_painel(request.user).values_list("codigo", flat=True))
    try:
        itens = _parse_grade(request.POST, permitidos)
    except PermissionError:
        return sem_permissao(request)
    except ValueError as exc:
        messages.error(request, f"Edição rejeitada: {exc}")
        return redirect(f"/?ano={ano_param}&base={base_param}")
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
        return exportar_html(request, ano_param, base_param)
    messages.success(request, "Plano anual atualizado.")
    return redirect(f"/?ano={ano_param}&base={base_param}")


@login_required
def exportar_csv(request):
    """CSV da visão corrente (ano × base): `;`, BOM, UTF-8 (RF-114)."""
    filtros = _filtros_ou_padrao(request.GET)
    if filtros is None:
        return redirect("/?ano=todos&base=fin")
    ano_param, base_param = filtros
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


def _html_standalone(ano_param, base_param, usuario):
    import re

    from django.contrib.staticfiles.finders import find
    from django.template.loader import render_to_string

    contexto = contexto_painel(ano_param, base_param, usuario)
    caminho_css = find("css/tailwind.css")
    contexto["standalone_css"] = open(caminho_css, encoding="utf-8").read() if caminho_css else ""
    caminho_sprite = find("icons/sprite.svg")
    sprite = open(caminho_sprite, encoding="utf-8").read() if caminho_sprite else ""
    contexto["standalone_sprite"] = re.sub(r"<\?xml.*?\?>", "", sprite)
    contexto["standalone"] = True
    html = render_to_string("dashboard/standalone.html", contexto)
    html = re.sub(r"/static/icons/sprite[^\"'#]*\.svg", "", html)
    return html


def exportar_html(request, ano_param="todos", base_param="fin"):
    """HTML standalone da visão corrente (RF-114)."""
    filtros = _filtros_ou_padrao({"ano": ano_param, "base": base_param})
    ano_param, base_param = filtros or ("todos", "fin")
    html = _html_standalone(ano_param, base_param, request.user)
    hoje = date.today().isoformat()
    resposta = HttpResponse(html, content_type="text/html; charset=utf-8")
    resposta["Content-Disposition"] = (
        f"attachment; filename=dashboard_quiin_{base_param}_{ano_param}_{hoje}.html"
    )
    return resposta


@login_required
def download_html(request):
    filtros = _filtros_ou_padrao(request.GET)
    if filtros is None:
        return redirect("/?ano=todos&base=fin")
    return exportar_html(request, *filtros)
