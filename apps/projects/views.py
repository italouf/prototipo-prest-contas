import csv
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.accountability.models import Acompanhamento
from apps.core.permissions import eh_gestor, pilares_editaveis_painel, sem_permissao, usuario_pode_pilar
from apps.pillars.models import Pilar

from .forms import AssociacaoForm, BookForm, MaterialForm, ProjetoForm
from .identity import PILARES
from .models import BookPrograma, MaterialProjeto, Projeto, ReferenciaImportacaoProjeto
from .presentation import carteira
from .presentation import resumo_projetos
from .navigation import aplicar_retorno
from .services import associar_referencia, auditar, salvar_book


def escopo(request, pilar_pk, *, escrita=False, book=False):
    pilar = get_object_or_404(Pilar, pk=pilar_pk, codigo__in=PILARES, ativo=True)
    permitido = usuario_pode_pilar(request.user, pilar)
    if escrita:
        permitido = permitido and pilares_editaveis_painel(request.user).filter(pk=pilar.pk).exists()
    if book:
        permitido = permitido and eh_gestor(request.user)
    if not permitido:
        return None, sem_permissao(request)
    try:
        acomp_pk = int(request.GET.get("acompanhamento", ""))
    except (ValueError, TypeError):
        raise Http404("Acompanhamento inválido.")
    acomp = get_object_or_404(Acompanhamento.objects.select_related("centro"), pk=acomp_pk)
    params = {k: request.GET[k] for k in ("ano", "mes_inicial", "mes_final") if k in request.GET}
    params.update(acompanhamento=acomp.pk, base="fis", entregaveis="1")
    query = urlencode(params)
    return aplicar_retorno(request, {"pilar": pilar, "acomp": acomp, "centro": acomp.centro, "query": query,
            "voltar": reverse("core:pilar", args=[pilar.pk]) + "?" + query + "#entregaveis"}), None


def tela_form(request, s, form, titulo):
    return render(request, "projects/form.html", {**s, "form": form, "titulo": titulo})


@login_required
def projeto_form(request, pilar_pk, pk=None):
    s, erro = escopo(request, pilar_pk, escrita=True)
    if erro is not None:
        return erro
    projeto = get_object_or_404(Projeto, pk=pk, centro=s["centro"], pilar=s["pilar"]) if pk else Projeto(centro=s["centro"], pilar=s["pilar"])
    anterior = {"nome": projeto.nome, "codigo": projeto.codigo_embrapii}
    form = ProjetoForm(request.POST if request.method == "POST" else None, instance=projeto)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                registro = form.save(commit=False)
                if not pk:
                    registro.criado_por = request.user
                registro.atualizado_por = request.user
                registro.save()
                auditar(request.user, "EDITAR_PROJETO" if pk else "CADASTRAR_PROJETO", registro, anterior)
            messages.success(request, "Projeto salvo.")
            return redirect(s["voltar"])
        except IntegrityError:
            form.add_error("nome", "Já existe um projeto com esse nome neste centro e pilar.")
    return tela_form(request, s, form, "Editar projeto" if pk else "Novo projeto")


@login_required
def material_form(request, pilar_pk, projeto_pk, pk=None):
    s, erro = escopo(request, pilar_pk, escrita=True)
    if erro is not None:
        return erro
    projeto = get_object_or_404(Projeto, pk=projeto_pk, centro=s["centro"], pilar=s["pilar"])
    material = get_object_or_404(MaterialProjeto, pk=pk, projeto=projeto) if pk else MaterialProjeto(projeto=projeto)
    anterior = {k: str(getattr(material, k)) for k in ("titulo", "tipo", "url", "data_publicacao")}
    form = MaterialForm(request.POST if request.method == "POST" else None, instance=material)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            registro = form.save(commit=False)
            if not pk:
                registro.criado_por = request.user
            registro.atualizado_por = request.user
            registro.save()
            auditar(request.user, "EDITAR_MATERIAL" if pk else "CADASTRAR_MATERIAL", registro, anterior)
        messages.success(request, "Material salvo.")
        return redirect(s["voltar"])
    return tela_form(request, s, form, ("Editar material · " if pk else "Novo material · ") + projeto.nome)


@login_required
def book_form(request, pilar_pk):
    s, erro = escopo(request, pilar_pk, escrita=True, book=True)
    if erro is not None:
        return erro
    vigente = BookPrograma.objects.filter(centro=s["centro"], ativo=True).first()
    inicial = {c: getattr(vigente, c) for c in ("titulo", "url", "data_publicacao")} if vigente else {}
    # Cada publicação gera uma versão e mantém a anterior no histórico.
    form = BookForm(request.POST if request.method == "POST" else None,
                    instance=BookPrograma(centro=s["centro"], ativo=False), initial=inicial)
    if request.method == "POST" and form.is_valid():
        salvar_book(form.save(commit=False), request.user)
        messages.success(request, "Book geral publicado para todos os projetos de PDI, FCRH e ACS deste centro.")
        return redirect(s["voltar"])
    return tela_form(request, s, form, "Publicar Book geral · " + s["centro"].nome)


@login_required
def gerenciar(request, pilar_pk):
    s, erro = escopo(request, pilar_pk, escrita=True)
    if erro is not None:
        return erro
    projetos = resumo_projetos(s["centro"], s["pilar"], incluir_arquivados=True).prefetch_related("referencias_importacao")
    return render(request, "projects/manage.html", {**s, "projetos": projetos,
        "books": BookPrograma.objects.filter(centro=s["centro"]) if eh_gestor(request.user) else [], "gestor": eh_gestor(request.user)})


@login_required
@require_POST
def situacao(request, pilar_pk, recurso, pk):
    s, erro = escopo(request, pilar_pk, escrita=True, book=recurso == "book")
    if erro is not None:
        return erro
    if request.POST.get("acao") not in ("arquivar", "reativar"):
        return HttpResponseBadRequest("Ação inválida.")
    modelos = {"projeto": Projeto, "material": MaterialProjeto, "book": BookPrograma}
    filtros = {"centro": s["centro"], "pilar": s["pilar"]} if recurso == "projeto" else {"projeto__centro": s["centro"], "projeto__pilar": s["pilar"]} if recurso == "material" else {"centro": s["centro"]}
    with transaction.atomic():
        if recurso == "book":
            from apps.accountability.models import CentroCompetencia
            CentroCompetencia.objects.select_for_update().get(pk=s["centro"].pk)
        registro = get_object_or_404(modelos[recurso].objects.select_for_update(), pk=pk, **filtros)
        ativo = request.POST.get("acao") == "reativar"
        if ativo and recurso == "book":
            salvar_book(registro, request.user)
        elif registro.ativo != ativo:
            anterior = registro.ativo
            registro.ativo = ativo
            registro.atualizado_por = request.user
            registro.save()
            auditar(request.user, "REATIVAR_ENTREGAVEL" if ativo else "ARQUIVAR_ENTREGAVEL", registro, anterior)
    messages.success(request, "Situação atualizada.")
    return redirect(s.get("retorno_consulta") or reverse("projects:gerenciar", args=[s["pilar"].pk]) + "?" + s["query"])


@login_required
def referencia_form(request, pilar_pk, pk):
    s, erro = escopo(request, pilar_pk, escrita=True)
    if erro is not None:
        return erro
    referencia = get_object_or_404(ReferenciaImportacaoProjeto, pk=pk, centro=s["centro"], pilar=s["pilar"])
    form = AssociacaoForm(request.POST if request.method == "POST" else None, referencia=referencia)
    if request.method == "POST" and form.is_valid():
        try:
            associar_referencia(referencia, form.cleaned_data["projeto"], request.user)
            messages.success(request, "Referência associada. Materiais existentes continuam no projeto ao qual pertencem.")
            return redirect(s["voltar"])
        except ValidationError as exc:
            form.add_error(None, exc)
    return tela_form(request, s, form, "Associar referência importada · " + referencia.nome_origem)


@login_required
def exportar_csv(request, pilar_pk):
    s, erro = escopo(request, pilar_pk)
    if erro is not None:
        return erro
    resposta = HttpResponse(content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = 'attachment; filename="entregaveis_' + s["pilar"].codigo + '.csv"'
    resposta.write("\ufeff")
    writer = csv.writer(resposta, delimiter=";")
    writer.writerow(["Projeto", "Código EMBRAPII", "Material", "Tipo", "Data", "URL", "Book geral", "URL do Book"])
    book = BookPrograma.objects.filter(centro=s["centro"], ativo=True).first()
    for projeto in carteira(s["centro"], s["pilar"]):
        for material in list(projeto.materiais.all()) or [None]:
            valores = [projeto.nome, projeto.codigo_embrapii,
                material.titulo if material else "", material.get_tipo_display() if material else "",
                material.data_publicacao.isoformat() if material and material.data_publicacao else "", material.url if material else "",
                book.titulo if book else "", book.url if book else ""]
            writer.writerow(["'" + v if v.lstrip().startswith(("=", "+", "-", "@")) else v for v in valores])
    return resposta
