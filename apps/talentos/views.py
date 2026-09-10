"""Organograma geral do Banco de Talentos."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from apps.audit.services import registrar_auditoria
from apps.core.permissions import pode_lancar, sem_permissao
from apps.pillars.models import Pilar

from .forms import AlocacaoForm, ColaboradorForm
from .models import Alocacao, Colaborador, Competencia


class OrganogramaView(LoginRequiredMixin, View):
    def get(self, request):
        pilar_selecionado = request.GET.get("pilar", "") or ""
        competencia_selecionada = request.GET.get("competencia", "") or ""
        hoje = timezone.localdate()
        vigentes = Alocacao.objects.filter(
            Q(data_fim__isnull=True) | Q(data_fim__gte=hoje)
        ).order_by("-data_inicio")
        qs = Colaborador.objects.select_related("pilar_principal").prefetch_related(
            "competencias",
            Prefetch("alocacoes", queryset=vigentes, to_attr="alocacoes_vigentes"),
        )
        if pilar_selecionado:
            if Pilar.objects.filter(codigo=pilar_selecionado).exists():
                qs = qs.filter(pilar_principal__codigo=pilar_selecionado)
            else:
                qs = qs.none()
        if competencia_selecionada:
            try:
                competencia_id = int(competencia_selecionada)
            except (TypeError, ValueError):
                competencia_id = None
            if competencia_id is not None and Competencia.objects.filter(pk=competencia_id).exists():
                qs = qs.filter(competencias__pk=competencia_id)
        return render(
            request,
            "talentos/organograma.html",
            {
                "colaboradores": qs,
                "pilares": Pilar.objects.filter(ativo=True),
                "competencias": Competencia.objects.all(),
                "pilar_selecionado": pilar_selecionado,
                "competencia_selecionada": competencia_selecionada,
                "pode_editar_talentos": pode_lancar(request.user),
            },
        )


@login_required
def colaborador_criar(request):
    if not pode_lancar(request.user):
        return sem_permissao(request)
    if request.method == "POST":
        form = ColaboradorForm(request.POST, request.FILES)
        if form.is_valid():
            colaborador = form.save()
            registrar_auditoria(
                request.user,
                "CRIAR_COLABORADOR",
                "Colaborador",
                registro_id=colaborador.pk,
                campo="nome",
                valor_novo=colaborador.nome,
            )
            messages.success(request, "Colaborador criado com sucesso.")
            return redirect("talentos:organograma")
    else:
        form = ColaboradorForm()
    return render(
        request,
        "talentos/colaborador_form.html",
        {"form": form, "titulo": "Novo colaborador"},
    )


@login_required
def colaborador_editar(request, pk):
    if not pode_lancar(request.user):
        return sem_permissao(request)
    colaborador = get_object_or_404(Colaborador, pk=pk)
    if request.method == "POST":
        nome_anterior = colaborador.nome
        form = ColaboradorForm(request.POST, request.FILES, instance=colaborador)
        if form.is_valid():
            colaborador = form.save()
            registrar_auditoria(
                request.user,
                "EDITAR_COLABORADOR",
                "Colaborador",
                registro_id=colaborador.pk,
                campo="nome",
                valor_anterior=nome_anterior,
                valor_novo=colaborador.nome,
            )
            messages.success(request, "Colaborador atualizado com sucesso.")
            return redirect("talentos:organograma")
    else:
        form = ColaboradorForm(instance=colaborador)
    return render(
        request,
        "talentos/colaborador_form.html",
        {"form": form, "titulo": "Editar colaborador", "colaborador": colaborador},
    )


@login_required
def alocacao_criar(request, colaborador_pk):
    if not pode_lancar(request.user):
        return sem_permissao(request)
    colaborador = get_object_or_404(Colaborador, pk=colaborador_pk)
    if request.method == "POST":
        form = AlocacaoForm(request.POST)
        if form.is_valid():
            alocacao = form.save(commit=False)
            alocacao.colaborador = colaborador
            alocacao.save()
            registrar_auditoria(
                request.user,
                "CRIAR_ALOCACAO",
                "Alocacao",
                registro_id=alocacao.pk,
                campo="projeto_ou_area",
                valor_novo=alocacao.projeto_ou_area,
            )
            messages.success(request, "Alocação criada com sucesso.")
            return redirect("talentos:organograma")
    else:
        form = AlocacaoForm()
    return render(
        request,
        "talentos/alocacao_form.html",
        {"form": form, "titulo": "Nova alocação", "colaborador": colaborador},
    )


@login_required
def alocacao_editar(request, pk):
    if not pode_lancar(request.user):
        return sem_permissao(request)
    alocacao = get_object_or_404(Alocacao, pk=pk)
    if request.method == "POST":
        projeto_anterior = alocacao.projeto_ou_area
        form = AlocacaoForm(request.POST, instance=alocacao)
        if form.is_valid():
            alocacao = form.save()
            registrar_auditoria(
                request.user,
                "EDITAR_ALOCACAO",
                "Alocacao",
                registro_id=alocacao.pk,
                campo="projeto_ou_area",
                valor_anterior=projeto_anterior,
                valor_novo=alocacao.projeto_ou_area,
            )
            messages.success(request, "Alocação atualizada com sucesso.")
            return redirect("talentos:organograma")
    else:
        form = AlocacaoForm(instance=alocacao)
    return render(
        request,
        "talentos/alocacao_form.html",
        {
            "form": form,
            "titulo": "Editar alocação",
            "colaborador": alocacao.colaborador,
            "alocacao": alocacao,
        },
    )
