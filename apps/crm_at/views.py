"""Funil de oportunidades da Associação Tecnológica."""
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from apps.audit.services import registrar_auditoria
from apps.core.calculos import meta_realizado_percentual
from apps.core.permissions import pode_lancar, sem_permissao, usuario_pode_pilar
from apps.core.utils import periodo_selecionado
from apps.indicators.models import Indicador
from apps.pillars.models import Pilar

from .forms import EmpresaForm, OportunidadeForm
from .models import Empresa, Oportunidade

_FASES_FECHADAS = ("FECHAMENTO", "PERDIDO")


def _pode_editar_crm(usuario):
    """Cadastro no site: pode_lancar E vínculo com o pilar AT."""
    pilar_at = Pilar.objects.filter(codigo="AT").first()
    if pilar_at is None:
        return False
    return pode_lancar(usuario) and usuario_pode_pilar(usuario, pilar_at)


class FunilATView(LoginRequiredMixin, View):
    def get(self, request):
        pilar_at = Pilar.objects.filter(codigo="AT").first()
        if pilar_at is None or not usuario_pode_pilar(request.user, pilar_at):
            return sem_permissao(request)
        qs = Oportunidade.objects.select_related("empresa").all()
        grupos = []
        for valor, rotulo in Oportunidade.FASES:
            itens = [o for o in qs if o.fase == valor]
            total = sum((o.valor_previsto for o in itens), Decimal("0"))
            grupos.append({"fase": valor, "rotulo": rotulo, "oportunidades": itens, "total": total})
        pipeline_open = qs.exclude(fase__in=_FASES_FECHADAS).aggregate(t=Sum("valor_previsto"))["t"] or Decimal("0")
        renovacoes = qs.filter(tipo="RENOVACAO").exclude(fase__in=_FASES_FECHADAS)
        renovacoes_qtd = renovacoes.count()
        renovacoes_total = renovacoes.aggregate(t=Sum("valor_previsto"))["t"] or Decimal("0")

        fases_funil = [fase for fase in Oportunidade.FASES if fase[0] not in ("RENOVACAO", "PERDIDO")]
        funil = [
            {"fase": valor, "rotulo": rotulo, "oportunidades": [o for o in qs if o.fase == valor]}
            for valor, rotulo in fases_funil
        ]
        periodo, _ = periodo_selecionado(request)
        meta_cnpjs = None
        if periodo is not None:
            indicador_cnpjs = Indicador.objects.filter(codigo="AT-CNPJ-NOVOS").first()
            if indicador_cnpjs is not None:
                meta_cnpjs = {
                    "indicador": indicador_cnpjs,
                    "dados": meta_realizado_percentual(indicador_cnpjs, periodo),
                    "periodo": periodo,
                }
        return render(
            request,
            "crm_at/funil.html",
            {
                "grupos": grupos,
                "pipeline_open": pipeline_open,
                "renovacoes_qtd": renovacoes_qtd,
                "renovacoes_total": renovacoes_total,
                "pode_editar_crm": pode_lancar(request.user)
                and usuario_pode_pilar(request.user, pilar_at),
                "funil": funil,
                "renovacoes": list(renovacoes.select_related("empresa")),
                "perdidos": list(qs.filter(fase="PERDIDO")),
                "meta_cnpjs": meta_cnpjs,
                "empresas_associadas": Empresa.objects.filter(status="ASSOCIADA").count(),
                "prospects": Empresa.objects.filter(status="PROSPECT").count(),
            },
        )


def _destino_seguro(request, padrao):
    """Devolve o ?next= apenas se for URL interna do site."""
    proximo = request.GET.get("next") or request.POST.get("next") or ""
    if proximo and url_has_allowed_host_and_scheme(
        proximo, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return proximo
    return padrao


@login_required
def oportunidade_criar(request):
    if not _pode_editar_crm(request.user):
        return sem_permissao(request)
    if request.method == "POST":
        form = OportunidadeForm(request.POST)
        if form.is_valid():
            oportunidade = form.save()
            registrar_auditoria(
                request.user,
                "CRIAR_OPORTUNIDADE",
                "Oportunidade",
                registro_id=oportunidade.pk,
                campo="fase",
                valor_novo=oportunidade.fase,
            )
            messages.success(request, "Oportunidade criada com sucesso.")
            return redirect("crm_at:funil")
    else:
        form = OportunidadeForm()
    return render(
        request,
        "crm_at/oportunidade_form.html",
        {"form": form, "titulo": "Nova oportunidade"},
    )


@login_required
def oportunidade_editar(request, pk):
    if not _pode_editar_crm(request.user):
        return sem_permissao(request)
    oportunidade = get_object_or_404(Oportunidade, pk=pk)
    if request.method == "POST":
        fase_anterior = oportunidade.fase
        form = OportunidadeForm(request.POST, instance=oportunidade)
        if form.is_valid():
            oportunidade = form.save()
            registrar_auditoria(
                request.user,
                "EDITAR_OPORTUNIDADE",
                "Oportunidade",
                registro_id=oportunidade.pk,
                campo="fase",
                valor_anterior=fase_anterior,
                valor_novo=oportunidade.fase,
            )
            messages.success(request, "Oportunidade atualizada com sucesso.")
            return redirect("crm_at:funil")
    else:
        form = OportunidadeForm(instance=oportunidade)
    return render(
        request,
        "crm_at/oportunidade_form.html",
        {"form": form, "titulo": "Editar oportunidade", "oportunidade": oportunidade},
    )


@login_required
def empresa_criar(request):
    if not _pode_editar_crm(request.user):
        return sem_permissao(request)
    padrao = reverse("crm_at:funil")
    proximo = request.GET.get("next") or request.POST.get("next") or ""
    if request.method == "POST":
        form = EmpresaForm(request.POST)
        if form.is_valid():
            empresa = form.save()
            registrar_auditoria(
                request.user,
                "CRIAR_EMPRESA",
                "Empresa",
                registro_id=empresa.pk,
                campo="nome",
                valor_novo=empresa.nome,
            )
            messages.success(request, "Empresa criada com sucesso.")
            return redirect(_destino_seguro(request, padrao))
    else:
        form = EmpresaForm()
    return render(
        request,
        "crm_at/empresa_form.html",
        {"form": form, "titulo": "Nova empresa", "next": proximo},
    )
