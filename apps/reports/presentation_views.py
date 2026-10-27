"""Apresentação Reveal.js e edição restrita a Admin/Master."""
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.core.permissions import eh_gestor, pilares_visiveis, sem_permissao

from .editorial import excluir_editorial, salvar_editorial
from .forms import ApresentacaoMensalForm, ConteudoApresentacaoForm
from .models import ApresentacaoMensal, ConteudoApresentacao
from .presentation import compor_apresentacao


def _competencia(bruto):
    valor = date.fromisoformat(bruto)
    if valor.day != 1 or valor.isoformat() != bruto:
        raise ValueError
    return valor


def _url(apresentacao, nome="core:mensal"):
    return f"{reverse(nome)}?periodo={apresentacao.competencia.isoformat()}"


@login_required
@require_GET
def apresentacao_mensal(request):
    apresentacoes = list(ApresentacaoMensal.objects.select_related("acompanhamento__centro"))
    bruto = request.GET.get("periodo", "")
    competencia = None
    if bruto:
        try:
            competencia = _competencia(bruto)
        except ValueError:
            return redirect(_url(apresentacoes[0]) if apresentacoes else reverse("core:mensal"))
    elif apresentacoes:
        competencia = apresentacoes[0].competencia
    apresentacao = next((a for a in apresentacoes if a.competencia == competencia), None)
    contexto = {
        "apresentacoes": apresentacoes, "apresentacao": apresentacao,
        "competencia_apresentacao": competencia, "pode_editar_apresentacao": eh_gestor(request.user),
        "modo_impressao": "print-pdf" in request.GET,
    }
    if apresentacao:
        contexto.update(compor_apresentacao(apresentacao, request.user))
    template = "reports/presentation_print.html" if contexto["modo_impressao"] else "reports/presentation.html"
    return render(request, template, contexto)


@login_required
@require_http_methods(["GET", "POST"])
def editar_apresentacao(request):
    if not eh_gestor(request.user):
        return sem_permissao(request)
    bruto = request.GET.get("periodo", "")
    try:
        competencia = _competencia(bruto) if bruto else timezone.localdate().replace(day=1)
    except ValueError:
        raise Http404("Mês inválido.")
    apresentacao = ApresentacaoMensal.objects.filter(competencia=competencia).first() if bruto else None
    form = ApresentacaoMensalForm(
        request.POST if request.method == "POST" else None,
        instance=apresentacao, initial={"competencia": competencia},
    )
    if request.method == "POST" and form.is_valid():
        # A competência da edição é a da URL; criação pode escolher outro mês.
        obj = salvar_editorial(form.save(commit=False), request.user)
        messages.success(request, "Apresentação salva. Os dados usam o acompanhamento vinculado.")
        return redirect(_url(obj, "core:mensal_editar"))
    conteudos = apresentacao.conteudos.select_related("pilar").defer("imagem") if apresentacao else []
    return render(request, "reports/presentation_editor.html", {
        "form": form, "apresentacao": apresentacao, "conteudos": conteudos,
        "competencia_apresentacao": competencia,
    })


@login_required
@require_http_methods(["GET", "POST"])
def editar_conteudo(request, apresentacao_pk, pk=None):
    if not eh_gestor(request.user):
        return sem_permissao(request)
    apresentacao = get_object_or_404(ApresentacaoMensal, pk=apresentacao_pk)
    conteudo = get_object_or_404(ConteudoApresentacao, pk=pk, apresentacao=apresentacao) if pk else None
    form = ConteudoApresentacaoForm(
        request.POST if request.method == "POST" else None, request.FILES or None,
        instance=conteudo,
    )
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.apresentacao = apresentacao
        salvar_editorial(obj, request.user)
        messages.success(request, "Conteúdo salvo na apresentação.")
        return redirect(_url(apresentacao, "core:mensal_editar"))
    return render(request, "reports/presentation_content_form.html", {
        "form": form, "apresentacao": apresentacao, "conteudo": conteudo,
    })


@login_required
@require_POST
def excluir_conteudo(request, apresentacao_pk, pk):
    if not eh_gestor(request.user):
        return sem_permissao(request)
    conteudo = get_object_or_404(ConteudoApresentacao.objects.select_related("apresentacao"), pk=pk, apresentacao_id=apresentacao_pk)
    apresentacao = conteudo.apresentacao
    excluir_editorial(conteudo, request.user)
    messages.success(request, "Conteúdo excluído.")
    return redirect(_url(apresentacao, "core:mensal_editar"))


@login_required
@require_GET
def imagem_conteudo(request, pk):
    conteudo = get_object_or_404(
        ConteudoApresentacao.objects.filter(
            Q(pilar__isnull=True) | Q(pilar__in=pilares_visiveis(request.user))
        ), pk=pk,
    )
    if not conteudo.imagem_mime or not conteudo.imagem:
        raise Http404("Imagem indisponível.")
    resposta = HttpResponse(bytes(conteudo.imagem), content_type=conteudo.imagem_mime)
    resposta["Cache-Control"] = "private, no-store"
    resposta["X-Content-Type-Options"] = "nosniff"
    return resposta
