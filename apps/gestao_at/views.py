from collections import Counter
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from apps.audit.services import registrar_auditoria
from apps.core.permissions import pode_lancar, sem_permissao
from apps.pillars.models import Pilar
from .forms import AssociadoEmailForm, AssociadoForm, SolicitacaoForm
from .models import Associado, HistoricoSolicitacao, Plano, Solicitacao
from .services import RESPONSAVEIS, atualizar_usos, pode_gerir_associados, pode_ver_associados, registrar_andamento, resumo_beneficios, solicitacoes_visiveis

@login_required
def acompanhamento(request):
    if not pode_ver_associados(request.user):
        return sem_permissao(request)
    associados = list(Associado.objects.select_related("plano").prefetch_related("usos", "solicitacoes"))
    for a in associados:
        a.resumo = resumo_beneficios(a)
        a.abertas = sum(s.respondida_em is None for s in a.solicitacoes.all())
    contagens = Counter(a.plano_id for a in associados)
    planos = list(Plano.objects.order_by("-valor_anual"))
    maximo = max(contagens.values(), default=1)
    for p in planos:
        p.total = contagens[p.pk]
        p.percentual = p.total / maximo * 100
    vencimentos = sorted([a for a in associados if a.dias_vigencia <= 90], key=lambda a: a.fim_vigencia)
    contexto = {"associados": associados, "planos": planos, "vencimentos": vencimentos,
                "receita": sum(a.plano.valor_anual for a in associados),
                "vencidos": sum(a.dias_vigencia < 0 for a in associados),
                "vencem_90": sum(0 <= a.dias_vigencia <= 90 for a in associados),
                "uso_medio": sum(a.resumo["percentual"] for a in associados) / len(associados) if associados else 0,
                "abertas": sum(a.abertas for a in associados), "tipos": Counter(a.tipo for a in associados),
                "pode_gerir_at": pode_gerir_associados(request.user)}
    return render(request, "gestao_at/acompanhamento.html", contexto)

@login_required
def associado(request, pk):
    if not pode_ver_associados(request.user):
        return sem_permissao(request)
    a = get_object_or_404(Associado.objects.select_related("plano").prefetch_related("usos"), pk=pk)
    email_form = AssociadoEmailForm(initial={"email": a.email})
    if request.method == "POST":
        if not pode_gerir_associados(request.user):
            return sem_permissao(request)
        if request.POST.get("acao") == "email":
            email_form = AssociadoEmailForm(request.POST)
            if email_form.is_valid():
                with transaction.atomic():
                    registro = Associado.objects.select_for_update().get(pk=pk)
                    anterior = registro.email
                    registro.email = email_form.cleaned_data["email"]
                    registro.save(update_fields=["email"])
                    if anterior != registro.email:
                        registrar_auditoria(request.user, "EDITAR_ASSOCIADO", "AssociadoAT", pk, "email", anterior, registro.email)
                messages.success(request, "E-mail da associada atualizado.")
                return redirect("gestao_at:associado", pk=pk)
        else:
            try:
                atualizar_usos(a, request.user, request.POST)
                messages.success(request, "Uso dos benefícios atualizado.")
                return redirect("gestao_at:associado", pk=pk)
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
    resumo = resumo_beneficios(a)
    vagas = [i for i in resumo["itens"] if i["beneficio"].codigo in ("lato", "aperf", "work")]
    horas = [i for i in resumo["itens"] if i["beneficio"].codigo in ("mini", "ment", "tt")]
    solicitacoes = list(a.solicitacoes.all())
    return render(request, "gestao_at/associado.html", {"associado": a, "associados": Associado.objects.all(),
        "resumo": resumo, "vagas_usadas": sum(i["usado"] for i in vagas), "vagas_meta": sum(i["plano_beneficio"].cota for i in vagas),
        "horas_usadas": sum(i["usado"] for i in horas), "horas_meta": sum(i["plano_beneficio"].cota for i in horas),
        "solicitacoes": solicitacoes, "solicitacoes_abertas": sum(s.respondida_em is None for s in solicitacoes),
        "solicitacoes_respondidas": sum(s.respondida_em is not None for s in solicitacoes),
        "tem_cotas": any(i["beneficio"].quantitativo and i["plano_beneficio"].cota for i in resumo["itens"]),
        "email_form": email_form, "pode_gerir_at": pode_gerir_associados(request.user)})

@login_required
def associado_form(request, pk=None):
    if not pode_gerir_associados(request.user):
        return sem_permissao(request)
    a = get_object_or_404(Associado, pk=pk) if pk else None
    anterior = {c: str(getattr(a, c)) for c in AssociadoForm.Meta.fields} if a else {}
    form = AssociadoForm(request.POST or None, instance=a)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            a = form.save()
            for campo in form.changed_data:
                registrar_auditoria(request.user, "EDITAR_ASSOCIADO" if pk else "CRIAR_ASSOCIADO", "AssociadoAT", a.pk, campo, anterior.get(campo, ""), str(getattr(a, campo)))
        messages.success(request, "Associado salvo.")
        return redirect("gestao_at:associado", pk=a.pk)
    return render(request, "features/form.html", {"form": form, "titulo": "Editar associado" if pk else "Novo associado", "voltar": "gestao_at:acompanhamento"})

@login_required
def solicitacoes(request):
    qs = solicitacoes_visiveis(request.user)
    # Técnicos dos demais pilares acompanham apenas solicitações encaminhadas ao seu pilar.
    from apps.core.permissions import pilares_visiveis
    if not pilares_visiveis(request.user).exists():
        return sem_permissao(request)
    todas = list(qs)
    filtros = {c: request.GET.get(c, "").strip() for c in ("status", "plano", "categoria", "q")}
    if filtros["status"]:
        qs = qs.filter(status=filtros["status"])
    if filtros["plano"]:
        qs = qs.filter(associado__plano__nome=filtros["plano"])
    if filtros["categoria"]:
        qs = qs.filter(categoria=filtros["categoria"])
    if filtros["q"]:
        qs = qs.filter(Q(associado__nome__icontains=filtros["q"]) | Q(assunto__icontains=filtros["q"]))
    respostas = [s for s in todas if s.respondida_em]
    return render(request, "gestao_at/solicitacoes.html", {"solicitacoes": qs, "filtros": filtros,
        "status_choices": Solicitacao.STATUS, "categorias": Solicitacao.CATEGORIAS, "planos": Plano.objects.all(),
        "abertas": sum(s.respondida_em is None for s in todas), "respondidas": len(respostas),
        "media": sum(s.dias for s in respostas) / len(respostas) if respostas else 0, "atrasadas": sum(s.atrasada for s in todas),
        "pode_gerir_at": pode_gerir_associados(request.user)})

@login_required
def solicitacao_criar(request):
    if not pode_gerir_associados(request.user):
        return sem_permissao(request)
    form = SolicitacaoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            s = form.save(commit=False)
            codigo, s.responsavel_tecnico = RESPONSAVEIS[s.categoria]
            s.responsavel_pilar = Pilar.objects.filter(codigo=codigo).first()
            s.criado_por = request.user
            s.full_clean()
            s.save()
            HistoricoSolicitacao.objects.create(solicitacao=s, usuario=request.user, descricao="Recebida por Cintia Pereira (ponto focal da Associação)", status="Recebida")
            registrar_auditoria(request.user, "CRIAR_SOLICITACAO", "SolicitacaoAT", s.pk, "assunto", "", s.assunto)
        messages.success(request, "Solicitação registrada.")
        return redirect("gestao_at:solicitacao", pk=s.pk)
    return render(request, "features/form.html", {"form": form, "titulo": "Registrar solicitação", "descricao": "Pedido recebido pelo ponto focal da Associação. Prazo de referência: 10 dias.", "voltar": "gestao_at:solicitacoes"})

@login_required
def solicitacao(request, pk):
    s = get_object_or_404(solicitacoes_visiveis(request.user), pk=pk)
    erro = ""
    if request.method == "POST":
        try:
            registrar_andamento(pk, request.user, request.POST.get("status", ""), request.POST.get("texto", ""))
            messages.success(request, "Andamento registrado.")
            return redirect("gestao_at:solicitacao", pk=pk)
        except ValidationError as exc:
            erro = "; ".join(exc.messages)
    return render(request, "gestao_at/solicitacao.html", {"solicitacao": s, "historico": s.historico.select_related("usuario"), "status_choices": Solicitacao.STATUS, "erro": erro, "pode_registrar": pode_lancar(request.user)})
