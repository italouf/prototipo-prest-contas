"""Operação sobre indicadores dos dashboards; nenhuma escrita no catálogo legado."""
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.http import Http404, HttpResponseBadRequest, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.accountability.models import Acompanhamento
from apps.audit.models import AuditLog
from apps.core.permissions import eh_gestor, pilares_visiveis, pode_aprovar, pode_lancar, usuario_pode_pilar
from apps.core.templatetags.core_extras import numero_curto, numero_ptbr
from apps.periods.models import Periodo
from apps.pillars.models import Pilar
from .models import BaseOperacional, IndicadorOperacional, LancamentoOperacional
from . import operational as services


def formatar(item, valor):
    if valor is None:
        return "—"
    if item.tipo == "PER":
        return numero_curto(valor * 100) + "%"
    return ("R$ " + numero_ptbr(valor)) if item.tipo == "MON" else str(int(valor))


def query_url(request, **changes):
    params = request.GET.copy()
    for k, v in changes.items():
        if v is None:
            params.pop(k, None)
        else:
            params[k] = str(v)
    return request.path + ("?" + params.urlencode() if params else "")


def contexto(request, periodo=None, pilar=None):
    fontes = Acompanhamento.objects.select_related("centro").order_by("-criado_em", "-pk")
    acomp = get_object_or_404(fontes, pk=request.GET["acompanhamento"]) if request.GET.get("acompanhamento") else fontes.first()
    base = BaseOperacional.objects.filter(acompanhamento=acomp).first() if acomp else None
    visiveis = pilares_visiveis(request.user)
    filtro = request.GET.get("pilar", str(pilar.pk) if pilar else "")
    if filtro and not visiveis.filter(pk=filtro).exists():
        raise PermissionDenied
    tipo = request.GET.get("base", "")
    if tipo not in ("", "financeiro", "fisico"):
        raise Http404("Base inválida.")
    return dict(acompanhamento=acomp, acompanhamentos=fontes, base_operacional=base,
                periodo=periodo, periodos=Periodo.objects.all(), pilar=pilar,
                pilares_operacao=visiveis, filtro_pilar=filtro, filtro_base=tipo,
                busca=request.GET.get("q", "").strip()[:150], gestor=eh_gestor(request.user),
                voltar=request.get_full_path())


@login_required
def iniciar(request):
    if not pode_lancar(request.user):
        raise PermissionDenied
    c = contexto(request)
    periodo = Periodo.objects.filter(status__in=["ABERTO", "REABERTO"]).first()
    pilar = c["pilares_operacao"].filter(pk=c["filtro_pilar"]).first() if c["filtro_pilar"] else c["pilares_operacao"].first()
    if periodo and pilar and c["base_operacional"]:
        return redirect(reverse("entries:formulario", args=[periodo.pk, pilar.pk]) + ("?" + request.GET.urlencode() if request.GET else ""))
    return render(request, "entries/operational_setup.html", c)


@login_required
def configurar(request):
    if not eh_gestor(request.user):
        raise PermissionDenied
    c = contexto(request)
    if request.method == "POST":
        try:
            competencia = date.fromisoformat(request.POST.get("competencia", "") + "-01")
            initial = date.fromisoformat(request.POST.get("competencia_inicial", "") + "-01")
            if initial < competencia or initial.year > 2027:
                raise ValidationError("A competência inicial deve pertencer ao ciclo e ser posterior ou igual ao corte.")
            if not c["acompanhamento"]:
                raise ValidationError("Importe e selecione um acompanhamento antes de configurar a operação.")
            with transaction.atomic():
                services.confirmar_base(c["acompanhamento"], competencia, request.user,
                    request.POST.get("justificativa", ""), reconciliar=bool(c["base_operacional"]))
                periodo, novo = Periodo.objects.get_or_create(competencia=initial, defaults={"status": "PLANEJADO"})
                if novo:
                    from apps.periods.services import abrir_periodo
                    abrir_periodo(periodo, request.user)
            messages.success(request, "Base confirmada. Os dados importados foram preservados.")
            return redirect(reverse("entries:iniciar") + f"?acompanhamento={c['acompanhamento'].pk}")
        except (ValueError, ValidationError) as exc:
            messages.error(request, "; ".join(exc.messages) if isinstance(exc, ValidationError) else "Informe competências válidas em MM/AAAA.")
    return render(request, "entries/operational_setup.html", c)


@login_required
def formulario(request, periodo_pk, pilar_pk):
    periodo = get_object_or_404(Periodo, pk=periodo_pk)
    pilar = get_object_or_404(Pilar, pk=pilar_pk)
    if not pode_lancar(request.user) or not usuario_pode_pilar(request.user, pilar):
        raise PermissionDenied
    if request.method != "GET":
        return HttpResponseBadRequest("O lançamento legado foi desativado. Abra um indicador do catálogo atual.")
    c = contexto(request, periodo, pilar)
    if not c["base_operacional"]:
        return render(request, "entries/operational_setup.html", c)
    itens = IndicadorOperacional.objects.filter(acompanhamento=c["acompanhamento"], ativo=True, pilar_id=c["filtro_pilar"])
    if c["filtro_base"]:
        itens = itens.filter(base=c["filtro_base"])
    if c["busca"]:
        itens = itens.filter(nome__icontains=c["busca"])
    pagina = Paginator(itens.select_related("pilar"), 25).get_page(request.GET.get("page"))
    existentes = {r.indicador_id: r for r in LancamentoOperacional.objects.filter(
        indicador__in=pagina.object_list, periodo=periodo).order_by("indicador_id", "versao")}
    linhas = []
    from .effective import estado
    oficial = estado(c["acompanhamento"])
    for item in pagina:
        proposta = existentes.get(item.pk)
        atual = oficial.valor(item.chave, periodo.competencia)
        linhas.append(dict(indicador=item, proposta=proposta, vigente=formatar(item, atual),
            proposto=formatar(item, proposta.valor) if proposta else "—",
            url=reverse("entries:propor", args=[periodo.pk, item.pk])))
    c.update(linhas=linhas, pagina=pagina,
             anterior=query_url(request, page=pagina.previous_page_number()) if pagina.has_previous() else None,
             proxima=query_url(request, page=pagina.next_page_number()) if pagina.has_next() else None)
    return render(request, "entries/operational_form.html", c)


@login_required
def propor(request, periodo_pk, indicador_pk):
    item = get_object_or_404(IndicadorOperacional.objects.select_related("pilar", "acompanhamento"), pk=indicador_pk)
    periodo = get_object_or_404(Periodo, pk=periodo_pk)
    if not pode_lancar(request.user) or not usuario_pode_pilar(request.user, item.pilar):
        raise PermissionDenied
    atual = services.valor_atual(item, periodo.competencia)
    proposta = item.revisoes.filter(periodo=periodo).order_by("-versao").first()
    c = dict(indicador=item, periodo=periodo, vigente=formatar(item, atual), gestor=eh_gestor(request.user),
             acompanhamento=item.acompanhamento,
             valor=request.POST.get("valor", str((proposta.valor if proposta else atual) * (100 if item.tipo == "PER" else 1)) if (proposta or atual is not None) else ""),
             comentario=request.POST.get("comentario", proposta.comentario if proposta else ""),
             bloqueado=not periodo.permite_edicao or proposta and proposta.status == "ENVIADO")
    if request.method == "POST":
        try:
            services.salvar(item, periodo, request.user, request.POST.get("valor", ""), request.POST.get("comentario", ""),
                            enviar=request.POST.get("acao") == "enviar", direto=request.POST.get("acao") == "direto")
            messages.success(request, "Resultado publicado nos dashboards." if request.POST.get("acao") == "direto" else
                             "Proposta enviada para análise. Os dashboards ainda não foram alterados." if request.POST.get("acao") == "enviar" else "Rascunho salvo.")
            return redirect(reverse("entries:formulario", args=[periodo.pk, item.pilar_id]) + f"?acompanhamento={item.acompanhamento_id}&base={item.base}")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    return render(request, "entries/operational_proposal.html", c)


@login_required
def aprovacao(request, periodo_pk):
    if not pode_aprovar(request.user):
        raise PermissionDenied
    periodo = get_object_or_404(Periodo, pk=periodo_pk)
    c = contexto(request, periodo)
    if request.method == "POST":
        item = get_object_or_404(LancamentoOperacional.objects.select_related("indicador"), pk=request.POST.get("lancamento_id"),
                                  periodo=periodo, indicador__acompanhamento=c["acompanhamento"])
        try:
            if request.POST.get("acao") == "aprovar":
                services.aprovar(item, request.user)
                messages.success(request, "Resultado aprovado e publicado nos dashboards.")
            elif request.POST.get("acao") == "devolver":
                services.devolver(item, request.user, request.POST.get("justificativa", ""))
                messages.success(request, "Proposta devolvida para correção.")
            else:
                raise ValidationError("Ação inválida.")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        return redirect(request.get_full_path())
    q = LancamentoOperacional.objects.filter(periodo=periodo, indicador__acompanhamento=c["acompanhamento"],
                                              indicador__pilar__in=c["pilares_operacao"])
    if c["filtro_pilar"]:
        q = q.filter(indicador__pilar_id=c["filtro_pilar"])
    if c["filtro_base"]:
        q = q.filter(indicador__base=c["filtro_base"])
    if c["busca"]:
        q = q.filter(indicador__nome__icontains=c["busca"])
    contagens = dict(q.values("status").annotate(n=Count("pk")).values_list("status", "n"))
    aberto = request.GET.get("aprovados_abertos") == "1"
    colunas = []
    for status, titulo, ordem in (("ENVIADO", "Em análise", "enviado_em"), ("DEVOLVIDO", "Devolvidos", "-atualizado_em"),
                                  ("RASCUNHO", "Rascunhos", "-atualizado_em"), ("APROVADO", "Aprovados", "-aprovado_em")):
        pagina = None
        if status != "APROVADO" or aberto:
            pagina = Paginator(q.filter(status=status).select_related("indicador__pilar", "criado_por", "periodo").order_by(ordem, "pk"), 10).get_page(request.GET.get("page_" + status))
            for item in pagina:
                item.valor_formatado = formatar(item.indicador, item.valor)
                item.detalhe_url = reverse("entries:lancamento_drawer", args=[item.pk]) + ("?" + request.GET.urlencode() if request.GET else "")
        colunas.append(dict(status=status, titulo=titulo, total=contagens.get(status, 0), pagina=pagina,
            anterior=query_url(request, **{"page_" + status: pagina.previous_page_number()}) if pagina and pagina.has_previous() else None,
            proxima=query_url(request, **{"page_" + status: pagina.next_page_number()}) if pagina and pagina.has_next() else None))
    c.update(colunas=colunas, aprovados_abertos=aberto,
             toggle_url=query_url(request, aprovados_abertos="0" if aberto else "1"),
             mobile_status=request.GET.get("mobile_status", "ENVIADO"))
    return render(request, "entries/operational_board.html", c)


@login_required
def detalhe(request, pk):
    if not pode_aprovar(request.user):
        raise PermissionDenied
    item = get_object_or_404(LancamentoOperacional.objects.select_related("indicador__pilar", "indicador__acompanhamento", "periodo", "criado_por", "revisado_por"), pk=pk)
    atual = services.valor_atual(item.indicador, item.periodo.competencia)
    base = BaseOperacional.objects.get(acompanhamento_id=item.indicador.acompanhamento_id)
    eventos = Paginator(AuditLog.objects.filter(entidade="LancamentoOperacional", registro_id=str(item.pk)).select_related("usuario"), 20).get_page(request.GET.get("history_page"))
    params = request.GET.copy()
    params.pop("history_page", None)
    params["acompanhamento"] = str(item.indicador.acompanhamento_id)
    origem = reverse("entries:aprovacao", args=[item.periodo_id]) + "?" + params.urlencode()
    c = dict(item=item, vigente=formatar(item.indicador, atual), proposto=formatar(item.indicador, item.valor),
        variacao=formatar(item.indicador, item.valor - atual if atual is not None else None),
        conflito=item.status == "ENVIADO" and (item.valor_base != atual or item.base_versao != base.versao),
        eventos=eventos, origem=origem,
        historico_anterior=query_url(request, history_page=eventos.previous_page_number()) if eventos.has_previous() else None,
        historico_proximo=query_url(request, history_page=eventos.next_page_number()) if eventos.has_next() else None)
    template = "entries/_operational_detail.html" if request.headers.get("HX-Request") else "entries/operational_detail.html"
    return render(request, template, c)


@login_required
def projeto_fonte(request):
    if not eh_gestor(request.user):
        raise PermissionDenied
    c = contexto(request)
    if not c["base_operacional"]:
        return render(request, "entries/operational_setup.html", c)
    if request.method == "POST":
        try:
            pilar = get_object_or_404(Pilar, pk=request.POST.get("pilar"), codigo__in=["AT", "OUTRASFONTES"])
            services.criar_projeto_fonte(c["base_operacional"], pilar, request.POST.get("nome", ""),
                request.POST.get("captado", ""), request.POST.get("realizado", ""), request.user)
            messages.success(request, "Projeto cadastrado. A distribuição do saldo histórico preservou os totais da fonte.")
            return redirect(reverse("entries:iniciar") + f"?acompanhamento={c['acompanhamento'].pk}&pilar={pilar.pk}&base=financeiro")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    return render(request, "entries/operational_source_project.html", c)


@login_required
def importar_legado(request, **kwargs):
    if request.method != "GET":
        return HttpResponseBadRequest("O importador de indicadores legados foi desativado.")
    messages.info(request, "Use o catálogo atual para lançar resultados. Planilhas oficiais permanecem na importação de acompanhamentos.")
    return redirect("entries:iniciar")


@login_required
def mover_legado(request, **kwargs):
    return HttpResponseNotAllowed(["GET"], "Aprovações exigem revisão e ação explícita no novo painel.")
