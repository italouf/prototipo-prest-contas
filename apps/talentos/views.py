"""Organograma geral do Banco de Talentos."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch, Q
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_POST

from apps.audit.services import registrar_auditoria
from apps.core.permissions import eh_gestor, pilares_visiveis, pode_lancar, sem_permissao, usuario_pode_pilar
from apps.pillars.models import Pilar

from .forms import AlocacaoForm, ColaboradorForm
from .models import Alocacao, Colaborador, Competencia

def _valores_talento(c):
    return {"nome": c.nome, "cargo": c.cargo, "pilar_principal": str(c.pilar_principal or ""),
            "horas_semanais": str(c.horas_semanais), "formacoes": str(c.formacoes), "lattes_url": c.lattes_url,
            "competencias": ", ".join(c.competencias.values_list("nome", flat=True))}

def _auditar_talento(user, c, antes):
    for campo, novo in _valores_talento(c).items():
        if antes.get(campo, "") != novo:
            registrar_auditoria(user, "EDITAR_COLABORADOR", "Colaborador", c.pk, campo, antes.get(campo, ""), novo)


class OrganogramaView(LoginRequiredMixin, View):
    def get(self, request):
        pilar_selecionado = request.GET.get("pilar", "") or ""
        competencia_selecionada = request.GET.get("competencia", "") or ""
        hoje = timezone.localdate()
        vigentes = Alocacao.objects.filter(
            Q(data_fim__isnull=True) | Q(data_fim__gte=hoje), data_inicio__lte=hoje
        ).order_by("-data_inicio")
        qs = Colaborador.objects.filter(ativo=True).select_related("pilar_principal").prefetch_related(
            "competencias",
            Prefetch("alocacoes", queryset=vigentes, to_attr="alocacoes_vigentes"),
        )
        todos = list(qs)
        busca = request.GET.get("q", "").strip()
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
        colaboradores = list(qs)
        if busca:
            termo = busca.casefold()
            colaboradores = [c for c in colaboradores if termo in c.nome.casefold() or termo in c.cargo.casefold() or any(termo in v.nome.casefold() for v in c.competencias.all()) or any(termo in f[1].casefold() for f in c.formacoes)]
        for colaborador in colaboradores:
            vigentes_colab = getattr(colaborador, "alocacoes_vigentes", [])
            colaborador.horas_vigentes = sum(a.horas_semanais for a in vigentes_colab)
            colaborador.disponibilidade = max(0, colaborador.horas_semanais - colaborador.horas_vigentes)
            colaborador.percentual_alocado = min(100, colaborador.horas_vigentes / colaborador.horas_semanais * 100) if colaborador.horas_semanais else 0
            colaborador.pode_editar = pode_lancar(request.user) and (eh_gestor(request.user) or (colaborador.pilar_principal and usuario_pode_pilar(request.user, colaborador.pilar_principal)))
        alocadas = sum(sum(a.horas_semanais for a in c.alocacoes_vigentes) for c in todos)
        doutores = sum(any(f[0] in ("Doutorado", "Pós-doutorado") for f in c.formacoes) for c in todos)
        mestres = sum(any(f[0] == "Mestrado" for f in c.formacoes) and not any(f[0] in ("Doutorado", "Pós-doutorado") for f in c.formacoes) for c in todos)
        contexto = {
            "colaboradores": colaboradores,
            "pilares": Pilar.objects.filter(ativo=True),
            "competencias": Competencia.objects.all(),
            "pilar_selecionado": pilar_selecionado,
            "competencia_selecionada": competencia_selecionada,
            "pode_editar_talentos": pode_lancar(request.user),
            "q": busca, "total_colaboradores": len(todos), "doutores": doutores, "mestres": mestres,
            "horas_alocadas": alocadas, "horas_livres": sum(c.horas_semanais for c in todos) - alocadas,
        }
        if getattr(request, "htmx", False) and getattr(request.htmx, "target", "") == "talentos-lista":
            return render(request, "talentos/_lista.html", contexto)
        return render(request, "talentos/organograma.html", contexto)


@login_required
@transaction.atomic
def colaborador_criar(request):
    if not pode_lancar(request.user):
        return sem_permissao(request)
    if request.method == "POST":
        form = ColaboradorForm(request.POST, request.FILES, user=request.user)
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
        form = ColaboradorForm(user=request.user)
    return render(
        request,
        "features/form.html",
        {"form": form, "titulo": "Novo colaborador", "voltar": "talentos:organograma"},
    )


@login_required
@transaction.atomic
def colaborador_editar(request, pk):
    if not pode_lancar(request.user):
        return sem_permissao(request)
    colaborador = get_object_or_404(Colaborador, pk=pk)
    if request.method == "POST":
        colaborador = Colaborador.objects.select_for_update().get(pk=pk)
    if not eh_gestor(request.user):
        pilar_atual = colaborador.pilar_principal
        if pilar_atual is None or not usuario_pode_pilar(request.user, pilar_atual):
            return sem_permissao(request)
    if request.method == "POST":
        antes = _valores_talento(colaborador)
        form = ColaboradorForm(request.POST, request.FILES, instance=colaborador, user=request.user)
        if form.is_valid():
            colaborador = form.save()
            _auditar_talento(request.user, colaborador, antes)
            messages.success(request, "Colaborador atualizado com sucesso.")
            return redirect("talentos:organograma")
    else:
        form = ColaboradorForm(instance=colaborador, user=request.user)
    return render(
        request,
        "features/form.html",
        {"form": form, "titulo": "Editar colaborador", "colaborador": colaborador, "voltar": "talentos:organograma"},
    )


@login_required
@transaction.atomic
def alocacao_criar(request, colaborador_pk):
    if not pode_lancar(request.user):
        return sem_permissao(request)
    colaborador = get_object_or_404(Colaborador, pk=colaborador_pk)
    if request.method == "POST":
        colaborador = Colaborador.objects.select_for_update().get(pk=colaborador.pk)
    if not eh_gestor(request.user) and (not colaborador.pilar_principal or not usuario_pode_pilar(request.user, colaborador.pilar_principal)):
        return sem_permissao(request)
    if request.method == "POST":
        form = AlocacaoForm(request.POST, colaborador=colaborador)
        if form.is_valid():
            alocacao = form.save(commit=False)
            alocacao.colaborador = colaborador
            alocacao.save()
            registrar_auditoria(request.user, "CRIAR_ALOCACAO", "Alocacao", alocacao.pk, "horas_semanais", "", str(alocacao.horas_semanais))
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
        form = AlocacaoForm(colaborador=colaborador)
    return render(
        request,
        "features/form.html",
        {"form": form, "titulo": "Nova alocação", "descricao": colaborador.nome, "colaborador": colaborador, "voltar": "talentos:organograma"},
    )


@login_required
@transaction.atomic
def alocacao_editar(request, pk):
    if not pode_lancar(request.user):
        return sem_permissao(request)
    alocacao = get_object_or_404(Alocacao, pk=pk)
    if request.method == "POST":
        Colaborador.objects.select_for_update().get(pk=alocacao.colaborador_id)
        alocacao = Alocacao.objects.select_for_update().get(pk=pk)
    if not eh_gestor(request.user) and (not alocacao.colaborador.pilar_principal or not usuario_pode_pilar(request.user, alocacao.colaborador.pilar_principal)):
        return sem_permissao(request)
    if request.method == "POST":
        valores_antes = {campo: str(getattr(alocacao, campo) or "") for campo in AlocacaoForm.Meta.fields}
        form = AlocacaoForm(request.POST, instance=alocacao)
        if form.is_valid():
            alocacao = form.save()
            for campo in form.changed_data:
                registrar_auditoria(request.user, "EDITAR_ALOCACAO", "Alocacao", alocacao.pk, campo, valores_antes[campo], str(getattr(alocacao, campo) or ""))
            messages.success(request, "Alocação atualizada com sucesso.")
            return redirect("talentos:organograma")
    else:
        form = AlocacaoForm(instance=alocacao)
    return render(
        request,
        "features/form.html",
        {
            "form": form,
            "titulo": "Editar alocação",
            "colaborador": alocacao.colaborador,
            "alocacao": alocacao,
            "voltar": "talentos:organograma",
        },
    )

@login_required
@require_POST
def colaborador_arquivar(request, pk):
    c = get_object_or_404(Colaborador, pk=pk, ativo=True)
    if not pode_lancar(request.user) or (not eh_gestor(request.user) and (not c.pilar_principal or not usuario_pode_pilar(request.user, c.pilar_principal))):
        return sem_permissao(request)
    with transaction.atomic():
        c.ativo = False
        c.save(update_fields=["ativo"])
        registrar_auditoria(request.user, "ARQUIVAR_COLABORADOR", "Colaborador", c.pk, "ativo", "True", "False")
    messages.success(request, "Colaborador removido da lista de talentos. Histórico preservado.")
    return redirect("talentos:organograma")
