import csv
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.accountability.models import Acompanhamento, CentroCompetencia
from apps.core.permissions import pilares_editaveis_painel, sem_permissao, usuario_pode_pilar
from apps.pillars.models import Pilar

from .at_forms import MaterialProdutoATForm, ProdutoATForm
from .at_services import carteira_at
from .at_services import resumo_produtos_at
from .navigation import aplicar_retorno
from .models import MaterialProdutoAT, ProdutoAT
from .services import auditar


def escopo_at(request, escrita=False):
    pilar = get_object_or_404(Pilar, codigo="AT", ativo=True)
    permitido = usuario_pode_pilar(request.user, pilar)
    if escrita:
        permitido = permitido and pilares_editaveis_painel(request.user).filter(pk=pilar.pk).exists()
    if not permitido:
        return None, sem_permissao(request)
    try:
        acomp_pk = int(request.GET.get("acompanhamento", ""))
    except (TypeError, ValueError):
        raise Http404("Acompanhamento inválido.")
    acomp = get_object_or_404(Acompanhamento.objects.select_related("centro"), pk=acomp_pk)
    params = {k: request.GET[k] for k in ("ano", "mes_inicial", "mes_final") if k in request.GET}
    params.update(acompanhamento=acomp.pk, base="fis", entregaveis_at="1")
    query = urlencode(params)
    return aplicar_retorno(request, {"pilar": pilar, "centro": acomp.centro, "acomp": acomp, "query": query,
            "voltar": reverse("core:pilar", args=[pilar.pk]) + "?" + query + "#entregaveis-at"}), None


@login_required
def produto_form(request, pk=None):
    s, erro = escopo_at(request, escrita=True)
    if erro is not None:
        return erro
    if pk:
        produto = get_object_or_404(ProdutoAT, pk=pk, centro=s["centro"])
    else:
        maior = ProdutoAT.objects.filter(centro=s["centro"]).aggregate(ordem=Max("ordem"))["ordem"]
        produto = ProdutoAT(centro=s["centro"], ordem=maior + 1 if maior is not None else 0)
    anterior = {"nome": produto.nome, "ordem": produto.ordem}
    form = ProdutoATForm(request.POST if request.method == "POST" else None, instance=produto)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                CentroCompetencia.objects.select_for_update().get(pk=s["centro"].pk)
                registro = form.save(commit=False)
                if not pk:
                    registro.criado_por = request.user
                registro.atualizado_por = request.user
                registro.save()
                auditar(request.user, "EDITAR_PRODUTO_AT" if pk else "CADASTRAR_PRODUTO_AT", registro, anterior)
            messages.success(request, "Produto salvo.")
            return redirect(s["voltar"])
        except IntegrityError:
            form.add_error("nome", "Já existe um produto com esse nome neste centro.")
    return render(request, "projects/form.html", {**s, "form": form, "titulo": "Editar produto da AT" if pk else "Novo produto da AT"})


@login_required
def material_form(request, produto_pk, pk=None):
    s, erro = escopo_at(request, escrita=True)
    if erro is not None:
        return erro
    produto = get_object_or_404(ProdutoAT, pk=produto_pk, centro=s["centro"])
    material = get_object_or_404(MaterialProdutoAT, pk=pk, produto=produto) if pk else MaterialProdutoAT(produto=produto)
    anterior = {k: str(getattr(material, k)) for k in ("titulo", "tipo", "url", "data_publicacao")}
    form = MaterialProdutoATForm(request.POST if request.method == "POST" else None, instance=material)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            registro = form.save(commit=False)
            if not pk:
                registro.criado_por = request.user
            registro.atualizado_por = request.user
            registro.save()
            auditar(request.user, "EDITAR_MATERIAL_AT" if pk else "CADASTRAR_MATERIAL_AT", registro, anterior)
        messages.success(request, "Material salvo.")
        return redirect(s["voltar"])
    titulo = ("Editar material · " if pk else "Novo material · ") + produto.nome
    return render(request, "projects/form.html", {**s, "form": form, "titulo": titulo})


@login_required
def gerenciar(request):
    s, erro = escopo_at(request, escrita=True)
    if erro is not None:
        return erro
    produtos = resumo_produtos_at(s["centro"], incluir_arquivados=True)
    return render(request, "projects/manage_at.html", {**s, "produtos": produtos})


@login_required
@require_POST
def situacao(request, recurso, pk):
    s, erro = escopo_at(request, escrita=True)
    if erro is not None:
        return erro
    if request.POST.get("acao") not in ("arquivar", "reativar"):
        return HttpResponseBadRequest("Ação inválida.")
    modelo = ProdutoAT if recurso == "produto" else MaterialProdutoAT
    filtros = {"centro": s["centro"]} if recurso == "produto" else {"produto__centro": s["centro"]}
    with transaction.atomic():
        registro = get_object_or_404(modelo.objects.select_for_update(), pk=pk, **filtros)
        ativo = request.POST["acao"] == "reativar"
        if registro.ativo != ativo:
            anterior = registro.ativo
            registro.ativo = ativo
            registro.atualizado_por = request.user
            registro.save()
            auditar(request.user, "REATIVAR_ENTREGAVEL_AT" if ativo else "ARQUIVAR_ENTREGAVEL_AT", registro, anterior)
    messages.success(request, "Situação atualizada.")
    return redirect(s.get("retorno_consulta") or reverse("deliverables_at:gerenciar") + "?" + s["query"])


@login_required
def exportar_csv(request):
    s, erro = escopo_at(request)
    if erro is not None:
        return erro
    resposta = HttpResponse(content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = 'attachment; filename="entregaveis_at.csv"'
    resposta.write("\ufeff")
    writer = csv.writer(resposta, delimiter=";")
    writer.writerow(["Produto", "Material", "Tipo", "Data", "URL"])
    for produto in carteira_at(s["centro"]):
        for material in list(produto.materiais.all()) or [None]:
            valores = [produto.nome, material.titulo if material else "", material.get_tipo_display() if material else "",
                material.data_publicacao.isoformat() if material and material.data_publicacao else "", material.url if material else ""]
            writer.writerow(["'" + v if v.lstrip().startswith(("=", "+", "-", "@")) else v for v in valores])
    return resposta
