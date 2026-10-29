import csv
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from apps.accountability.models import Acompanhamento
from apps.core.permissions import pilares_editaveis_painel, pilares_visiveis

from .material_search import ConsultaMateriaisForm, PILARES, combinar, filtrar, fontes
from .models import BookPrograma, Projeto, ProdutoAT, TIPOS_MATERIAL
from .at_catalog import TIPOS_MATERIAL_AT
from .navigation import aplicar_retorno, token_retorno


def url_com_query(nome, args, query):
    return reverse(nome, args=args) + "?" + query


def preparar_linha(row, acomp, editaveis, retorno, pilares_ids):
    at = row["fonte"] == "AT"
    pilar = row["pilar_codigo"]
    args = [row["dono_id"]] if at else [pilares_ids[pilar], row["dono_id"]]
    namespace = "deliverables_at" if at else "projects"
    edicao = urlencode({"acompanhamento": acomp.pk, "retorno": retorno})
    row.update(tipo_rotulo=dict(TIPOS_MATERIAL_AT if at else TIPOS_MATERIAL).get(row["tipo"], row["tipo"]),
        pilar_rotulo=PILARES[pilar], editar=pilar in editaveis,
        detalhe_url=url_com_query(namespace + ":detalhe", args, edicao),
        editar_url=url_com_query(namespace + ":material_editar", [*args, row["id"]], edicao),
        situacao_url=url_com_query(namespace + ":material_situacao", [row["id"]] if at else [pilares_ids[pilar], row["id"]], edicao))
    return row


def consulta(request, dono=None, pilar_pk=None, modo="lista", dono_pk=None):
    from apps.pillars.models import Pilar
    visiveis = set(pilares_visiveis(request.user).filter(codigo__in=PILARES).values_list("codigo", flat=True))
    editaveis = set(pilares_editaveis_painel(request.user).filter(codigo__in=PILARES).values_list("codigo", flat=True))
    if not visiveis:
        raise PermissionDenied
    try:
        acomp_pk = int(request.GET.get("acompanhamento", ""))
    except (TypeError, ValueError):
        raise Http404("Acompanhamento inválido.")
    acomp = get_object_or_404(Acompanhamento.objects.select_related("centro"), pk=acomp_pk)
    pilares_ids = dict(Pilar.objects.filter(codigo__in=PILARES).values_list("codigo", "pk"))
    at = dono == "AT"
    proprietario = None
    codigo = None
    if dono is not None:
        if at:
            codigo = "AT"
            if codigo not in visiveis:
                raise PermissionDenied
            proprietario = get_object_or_404(ProdutoAT, pk=dono_pk, centro=acomp.centro)
        else:
            pilar = get_object_or_404(Pilar, pk=pilar_pk, codigo__in=set(PILARES)-{"AT"})
            codigo = pilar.codigo
            if codigo not in visiveis:
                raise PermissionDenied
            proprietario = get_object_or_404(Projeto, pk=dono_pk, centro=acomp.centro, pilar=pilar)
        if not proprietario.ativo and codigo not in editaveis:
            raise Http404
    if request.GET.get("pilar") and request.GET["pilar"] not in visiveis:
        raise PermissionDenied
    base = fontes(acomp.centro, {codigo} if proprietario else visiveis)
    origens = []
    projetos = Projeto.objects.filter(centro=acomp.centro, pilar__codigo__in=visiveis).filter(Q(ativo=True) | Q(pilar__codigo__in=editaveis)).select_related("pilar")
    origens.extend(("PROJETO:" + str(p.pk), PILARES[p.pilar.codigo] + " · " + p.nome) for p in projetos)
    if "AT" in visiveis:
        produtos = ProdutoAT.objects.filter(centro=acomp.centro)
        if "AT" not in editaveis:
            produtos = produtos.filter(ativo=True)
        origens.extend(("AT:" + str(p.pk), "AT · " + p.nome) for p in produtos)
    anos = set()
    for origem, fk, qs in base:
        permitido = Q(ativo=True, **{fk + "__ativo": True})
        if origem == "AT" and "AT" in editaveis:
            permitido = Q()
        elif origem == "PROJETO":
            permitido |= Q(projeto__pilar__codigo__in=editaveis)
        if proprietario:
            qs = qs.filter(**{fk + "_id": proprietario.pk}) if at == (origem == "AT") else qs.none()
        anos.update(d.year for d in qs.filter(permitido).dates("data_publicacao", "year"))
    dados = request.GET.copy()
    if not dados.get("tamanho"):
        dados["tamanho"] = "25"
    if proprietario and not proprietario.ativo and "situacao" not in dados:
        dados["situacao"] = "arquivados"
    form = ConsultaMateriaisForm(dados, pilares={codigo} if proprietario else visiveis,
        origens=origens, anos=sorted(anos, reverse=True), editavel=bool(editaveis & ({codigo} if proprietario else visiveis)))
    if proprietario:
        tipos = dict(TIPOS_MATERIAL_AT if at else TIPOS_MATERIAL)
        tipos["OUTROS"] = tipos.pop("OUTRO") if "OUTRO" in tipos else tipos["OUTROS"]
        form.fields["tipo"].choices = [("", "Todos os tipos"), *sorted(tipos.items(), key=lambda t: t[1])]
    valido = form.is_valid()
    if not valido and modo == "csv":
        return HttpResponseBadRequest("Filtros inválidos. Revise os campos na consulta de materiais.")
    filtros = form.cleaned_data if valido else {}
    filtradas = filtrar(base, filtros, editaveis, proprietario)
    registros = combinar(filtradas, filtros.get("ordem", ""))
    if not valido:
        registros = combinar([(origem, fk, qs.none()) for origem, fk, qs in base])
    paginador = Paginator(registros, filtros.get("tamanho") or 25)
    pagina = paginador.get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    params["acompanhamento"] = str(acomp.pk)
    query = params.urlencode()
    token = token_retorno(request, acomp.centro)
    linhas = registros if modo != "lista" else pagina.object_list
    linhas = [preparar_linha(dict(row), acomp, editaveis, token, pilares_ids) for row in linhas]
    if modo == "csv":
        resposta = HttpResponse(content_type="text/csv; charset=utf-8")
        resposta["Content-Disposition"] = 'attachment; filename="materiais.csv"'
        resposta.write("\ufeff")
        writer = csv.writer(resposta, delimiter=";")
        writer.writerow(["Pilar", "Produto/projeto", "Título", "Tipo", "Data", "URL", "Situação"])
        for row in linhas:
            valores = [row["pilar_rotulo"], row["dono_nome"], row["titulo"], row["tipo_rotulo"],
                row["data_publicacao"].isoformat() if row["data_publicacao"] else "", row["url"],
                "Origem arquivada" if not row["dono_ativo"] else "Arquivado" if not row["ativo"] else "Ativo"]
            writer.writerow(["'" + v if v.lstrip().startswith(("=", "+", "-", "@")) else v for v in valores])
        return resposta
    args = [] if not proprietario else [proprietario.pk] if at else [pilar_pk, proprietario.pk]
    namespace = "materials" if not proprietario else "deliverables_at" if at else "projects"
    titulo = proprietario.nome if proprietario else "Biblioteca de materiais"
    novo_url = None
    if proprietario and codigo in editaveis:
        novo_url = url_com_query(namespace + ":material_novo", args, urlencode({"acompanhamento": acomp.pk, "retorno": token}))
    back_params = {k: request.GET[k] for k in ("ano", "mes_inicial", "mes_final") if k in request.GET}
    back_params.update(acompanhamento=acomp.pk, base="fis", **{"entregaveis_at" if at else "entregaveis": "1"})
    back = reverse("core:pilar", args=[pilares_ids[codigo]]) + "?" + urlencode(back_params) if proprietario else None
    contexto = {"titulo": titulo, "centro": acomp.centro, "proprietario": proprietario, "form": form,
        "linhas": linhas, "page_obj": pagina, "query": query, "total": paginador.count,
        "global": proprietario is None, "produto_at": at, "voltar": back, "novo_url": novo_url,
        "biblioteca_url": reverse("materials:biblioteca") + "?" + urlencode({"acompanhamento": acomp.pk}),
        "relatorio_url": url_com_query(namespace + ":relatorio", args, query),
        "csv_url": url_com_query(namespace + ":csv_consulta" if proprietario else "materials:csv", args, query),
        "book": BookPrograma.objects.filter(centro=acomp.centro, ativo=True).first() if proprietario and not at else None}
    contexto["contexto_oculto"] = [(k, request.GET[k]) for k in ("ano", "mes_inicial", "mes_final", "retorno") if k in request.GET]
    contexto["limpar_url"] = "?" + urlencode({"acompanhamento": acomp.pk, **dict(contexto["contexto_oculto"])})
    contexto["filtros_rotulos"] = []
    for nome in ("q", "pilar", "origem", "tipo", "ano_material", "situacao"):
        valor = filtros.get(nome)
        if valor:
            campo = form.fields[nome]
            rotulos = dict(getattr(campo, "choices", []))
            contexto["filtros_rotulos"].append((campo.label, rotulos.get(str(valor), valor)))
    aplicar_retorno(request, contexto)
    return render(request, "projects/material_report.html" if modo == "relatorio" else "projects/material_list.html", contexto, status=200 if valido else 400)


@login_required
def biblioteca(request, modo="lista"):
    return consulta(request, modo=modo)


@login_required
def produto(request, pk, modo="lista"):
    return consulta(request, dono="AT", dono_pk=pk, modo=modo)


@login_required
def projeto(request, pilar_pk, pk, modo="lista"):
    return consulta(request, dono="PROJETO", dono_pk=pk, pilar_pk=pilar_pk, modo=modo)
