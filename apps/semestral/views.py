"""Views da Prestação de Contas SEMESTRAL (QuIIN / SENAI CIMATEC - EMBRAPII v3.1)."""
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.audit.services import registrar_auditoria
from apps.core.permissions import (
    eh_auditor,
    eh_gestor,
    eh_lideranca,
    eh_pontofocal,
    pode_aprovar,
    sem_permissao,
    usuario_pode_pilar,
)
from apps.periods.models import Periodo
from apps.semestral.management.commands.seed_semestral_v31 import (
    calcular_prazo_competencia,
    seed_pilares_e_ciclos,
)

from .forms import (
    CicloSemestralConfigForm,
    PilarSemestralConfigForm,
    SubmissaoCompetenciaForm,
    build_tab_record_form,
)
from .integracao import (
    aplicar_sugestao_operacional,
    aprovar_integracao_operacional,
    calcular_semaforo_coerencia,
    calcular_sugestoes_competencia,
    listar_projetos_oficiais_para_pilar,
    sincronizar_projeto_para_catalogo_oficial,
)
from .models import (
    CicloSemestral,
    CompetenciaMensalPilar,
    ConfiguracaoPilarSemestral,
    LogNotificacaoSLA,
)
from .registry import (
    TAB_FORM_SPECS,
    get_project_code_suggestions,
    get_tab_spec,
    tabs_for_pilar,
)
from .sla import (
    aprovar_competencia,
    arquivar_competencia,
    devolver_competencia,
    disparar_alertas_mensais,
    gerar_link_direto,
    submeter_competencia,
    verificar_sla_e_emitir_its1,
)
from .xlsx_exporter import (
    TEMPLATE_MAP,
    exportar_pacote_semestral_zip,
    exportar_planilha_embrapii,
)

MESES_PT = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}


def _usuario_tem_leitura_semestral(usuario) -> bool:
    return (
        eh_gestor(usuario)
        or eh_pontofocal(usuario)
        or eh_lideranca(usuario)
        or eh_auditor(usuario)
    )


def _usuario_pode_acessar_config(usuario, cfg: ConfiguracaoPilarSemestral) -> bool:
    if eh_gestor(usuario) or eh_lideranca(usuario) or eh_auditor(usuario):
        return True
    if eh_pontofocal(usuario):
        if cfg.responsavel_id == usuario.id:
            return True
        if cfg.pilar_id and usuario_pode_pilar(usuario, cfg.pilar):
            return True
    return False


def _usuario_pode_editar_config(usuario, cfg: ConfiguracaoPilarSemestral) -> bool:
    if eh_gestor(usuario):
        return True
    if eh_pontofocal(usuario):
        if cfg.responsavel_id == usuario.id:
            return True
        if cfg.pilar_id and usuario_pode_pilar(usuario, cfg.pilar):
            return True
    return False


def _usuario_pode_mutar_competencia(usuario, comp: CompetenciaMensalPilar) -> bool:
    """Regra central de escrita: ciclo Consolidado/Enviado ou competência Aprovada
    bloqueiam edição/envio para todos os perfis, com exceção exclusiva de Master/Admin."""
    if eh_gestor(usuario):
        return True
    if comp.ciclo.bloqueado_para_edicao_focal:
        return False
    if comp.status_aprovacao == "APROVADO":
        return False
    return _usuario_pode_editar_config(usuario, comp.configuracao_pilar)


def _prefixo_auditoria_ciclo(ciclo: CicloSemestral) -> str:
    if ciclo.bloqueado_para_edicao_focal:
        return f"[Ajuste excepcional Master/Admin em ciclo {ciclo.status}] "
    return ""


def _painel_aprovacao_padrao_url() -> str:
    periodo = (
        Periodo.objects.filter(status__in=["ABERTO", "REABERTO"]).order_by("-competencia").first()
        or Periodo.objects.order_by("-competencia").first()
    )
    if periodo is not None:
        return f"{reverse('entries:aprovacao', args=[periodo.pk])}#semestral-board"
    return reverse("core:semestral")


def _safe_next_url(request, fallback: str) -> str:
    destino = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if destino and url_has_allowed_host_and_scheme(
        url=destino,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return destino
    return fallback


def _garantir_ciclo(ano: int, semestre: int) -> CicloSemestral:
    if not ConfiguracaoPilarSemestral.objects.exists():
        seed_pilares_e_ciclos(anos=(ano,))
    ciclo, _ = CicloSemestral.objects.get_or_create(
        ano=ano,
        semestre=semestre,
        defaults={
            "centro_competencia": "QuIIN (SENAI CIMATEC)",
            "abreviacao_cc": "QIN",
            "termo_cooperacao": "001/2023",
            "periodo_referencia_label": f"{semestre}º semestre/{ano}",
            "coordenacao_nome": "Mabel",
            "coordenacao_email": "mabel.gestao@quiin.local",
        },
    )
    configs = list(ConfiguracaoPilarSemestral.objects.filter(ativo=True).order_by("ordem", "codigo"))
    existentes = set(
        CompetenciaMensalPilar.objects.filter(ciclo=ciclo).values_list(
            "configuracao_pilar_id", "competencia"
        )
    )
    for cfg in configs:
        for comp_data in ciclo.competencias_datas:
            if (cfg.id, comp_data) not in existentes:
                CompetenciaMensalPilar.objects.create(
                    ciclo=ciclo,
                    configuracao_pilar=cfg,
                    competencia=comp_data,
                    prazo_limite=calcular_prazo_competencia(comp_data, cfg.dia_limite_mensal),
                )
    return ciclo


def _resolver_ano_semestre(params) -> tuple[int, int]:
    hoje = date.today()
    ano_padrao = hoje.year
    sem_padrao = 1 if hoje.month <= 6 else 2
    try:
        ano = int(params.get("ano", ano_padrao))
        if ano < 2023 or ano > 2035:
            ano = ano_padrao
    except (TypeError, ValueError):
        ano = ano_padrao
    try:
        sem = int(params.get("semestre", sem_padrao))
        if sem not in (1, 2):
            sem = sem_padrao
    except (TypeError, ValueError):
        sem = sem_padrao
    return ano, sem


def _contar_registros_por_competencia(ciclo: CicloSemestral) -> Dict[int, int]:
    contagens: Dict[int, int] = {}
    modelos_processados = set()
    for spec in TAB_FORM_SPECS:
        key = (spec.model, spec.arquivo if spec.is_comment_sheet else None, spec.aba if spec.is_comment_sheet else None)
        if key in modelos_processados:
            continue
        modelos_processados.add(key)
        qs = spec.model.objects.filter(competencia_mensal__ciclo=ciclo)
        if spec.is_comment_sheet:
            qs = qs.filter(arquivo=spec.arquivo, aba=spec.aba)
        for comp_id in qs.values_list("competencia_mensal_id", flat=True):
            contagens[comp_id] = contagens.get(comp_id, 0) + 1
    return contagens


def _resumir_abas_competencia(comp: CompetenciaMensalPilar) -> Dict[str, Any]:
    resumo_abas = []
    total = 0
    primeira_aba = ""
    for t in tabs_for_pilar(comp.configuracao_pilar.codigo):
        q_t = t.model.objects.filter(competencia_mensal=comp)
        if t.is_comment_sheet:
            q_t = q_t.filter(arquivo=t.arquivo, aba=t.aba)
        cnt = q_t.count()
        total += cnt
        if cnt > 0:
            if not primeira_aba:
                primeira_aba = t.slug
            resumo_abas.append(
                {
                    "slug": t.slug,
                    "titulo": t.titulo_curto,
                    "aba": t.aba,
                    "count": cnt,
                }
            )
    return {
        "total_registros": total,
        "resumo_abas": resumo_abas,
        "primeira_aba_com_dados": primeira_aba,
    }


def listar_aprovacoes_semestrais_por_competencia(
    competencia_date: Optional[date] = None,
    filtro_pilar: str = "",
    busca: str = "",
    apenas_competencia_selecionada: bool = False,
) -> Dict[str, Any]:
    """Agrupa entregas semestrais submetidas para o Painel de Aprovação."""
    qs = (
        CompetenciaMensalPilar.objects.select_related(
            "ciclo",
            "configuracao_pilar",
            "configuracao_pilar__pilar",
            "submetido_por",
            "revisado_por",
        )
        .filter(
            configuracao_pilar__ativo=True,
            status_aprovacao__in=("EM_ANALISE", "DEVOLVIDO", "APROVADO"),
        )
        .order_by("-competencia", "configuracao_pilar__ordem", "configuracao_pilar__codigo")
    )
    if apenas_competencia_selecionada and competencia_date is not None:
        qs = qs.filter(competencia=competencia_date)
    if filtro_pilar:
        qs = qs.filter(configuracao_pilar__pilar_id=filtro_pilar)
    if busca:
        termo = busca.strip()
        if termo:
            qs = qs.filter(
                Q(configuracao_pilar__codigo__icontains=termo)
                | Q(configuracao_pilar__nome__icontains=termo)
                | Q(configuracao_pilar__responsavel_nome__icontains=termo)
                | Q(observacao_submissao__icontains=termo)
            )

    buckets: Dict[str, List[Dict[str, Any]]] = {
        "EM_ANALISE": [],
        "DEVOLVIDO": [],
        "APROVADO": [],
    }
    arquivados: List[Dict[str, Any]] = []
    for comp in qs:
        resumo = _resumir_abas_competencia(comp)
        inspecionar_url = reverse("semestral:competencia_form", args=[comp.pk])
        if resumo["primeira_aba_com_dados"]:
            inspecionar_url = f"{inspecionar_url}?aba={resumo['primeira_aba_com_dados']}"
        sugestoes_pendentes = 0
        ponte_url = ""
        if comp.status_aprovacao == "APROVADO" and not comp.arquivado_painel and resumo["total_registros"] > 0:
            pacote_ponte = calcular_sugestoes_competencia(comp)
            sugestoes_pendentes = (
                pacote_ponte["total_pendentes"]
                + pacote_ponte.get("total_aguardando_aprovacao", 0)
            )
            if pacote_ponte["sugestoes"] or pacote_ponte.get("projetos_novos_sem_vinculo"):
                ponte_url = f"{reverse('semestral:competencia_form', args=[comp.pk])}#ponte-operacional"
        entry = {
            "comp": comp,
            "cfg": comp.configuracao_pilar,
            "total_registros": resumo["total_registros"],
            "resumo_abas": resumo["resumo_abas"],
            "inspecionar_url": inspecionar_url,
            "ponte_url": ponte_url,
            "sugestoes_pendentes": sugestoes_pendentes,
            "mesma_competencia_painel": competencia_date is None or comp.competencia == competencia_date,
        }
        if comp.status_aprovacao == "APROVADO" and comp.arquivado_painel:
            arquivados.append(entry)
        else:
            buckets[comp.status_aprovacao].append(entry)

    colunas = [
        {"status": "EM_ANALISE", "titulo": "Em análise", "itens": buckets["EM_ANALISE"], "total": len(buckets["EM_ANALISE"])},
        {"status": "DEVOLVIDO", "titulo": "Devolvidos", "itens": buckets["DEVOLVIDO"], "total": len(buckets["DEVOLVIDO"])},
        {"status": "APROVADO", "titulo": "Aprovados", "itens": buckets["APROVADO"], "total": len(buckets["APROVADO"])},
    ]
    total_geral = sum(c["total"] for c in colunas)
    return {
        "colunas": colunas,
        "arquivados": arquivados,
        "total_arquivados": len(arquivados),
        "total_em_analise": len(buckets["EM_ANALISE"]),
        "total_geral": total_geral,
    }


@login_required
def painel_semestral(request):
    """Painel principal da Prestação de Contas SEMESTRAL (QuIIN / EMBRAPII v3.1)."""
    if not _usuario_tem_leitura_semestral(request.user):
        return sem_permissao(request)

    ano, semestre = _resolver_ano_semestre(request.GET)
    ciclo = _garantir_ciclo(ano, semestre)

    configs_all = list(
        ConfiguracaoPilarSemestral.objects.filter(ativo=True)
        .select_related("pilar", "responsavel")
        .order_by("ordem", "codigo")
    )
    configs_visiveis = [c for c in configs_all if _usuario_pode_acessar_config(request.user, c)]

    comps_qs = (
        CompetenciaMensalPilar.objects.filter(
            ciclo=ciclo, configuracao_pilar__in=configs_visiveis
        )
        .select_related("configuracao_pilar")
        .order_by("configuracao_pilar__ordem", "competencia")
    )
    comp_map = {(c.configuracao_pilar_id, c.competencia): c for c in comps_qs}
    contagens = _contar_registros_por_competencia(ciclo)

    meses_datas = ciclo.competencias_datas
    meses_header = [
        {"data": d, "iso": d.strftime("%Y-%m"), "mm_aaaa": d.strftime("%m/%Y"), "nome": MESES_PT[d.month]}
        for d in meses_datas
    ]

    matriz = []
    totais_status = {
        "total": 0,
        "no_prazo": 0,
        "regularizado": 0,
        "atrasado_its1": 0,
        "alerta_enviado": 0,
        "pendente": 0,
        "em_analise": 0,
        "aprovado": 0,
        "devolvido": 0,
        "registros": 0,
    }
    for cfg in configs_visiveis:
        celulas = []
        total_pilar_regs = 0
        for d in meses_datas:
            comp = comp_map.get((cfg.id, d))
            qtd = contagens.get(comp.id, 0) if comp else 0
            total_pilar_regs += qtd
            if comp:
                totais_status["total"] += 1
                totais_status["registros"] += qtd
                if comp.status == "SUBMETIDO_NO_PRAZO":
                    totais_status["no_prazo"] += 1
                elif comp.status == "REGULARIZADO":
                    totais_status["regularizado"] += 1
                elif comp.status == "ATRASADO_ITS1_EMITIDA":
                    totais_status["atrasado_its1"] += 1
                elif comp.status == "ALERTA_ENVIADO":
                    totais_status["alerta_enviado"] += 1
                else:
                    totais_status["pendente"] += 1

                if comp.status_aprovacao == "EM_ANALISE":
                    totais_status["em_analise"] += 1
                elif comp.status_aprovacao == "APROVADO":
                    totais_status["aprovado"] += 1
                elif comp.status_aprovacao == "DEVOLVIDO":
                    totais_status["devolvido"] += 1
            celulas.append(
                {
                    "competencia": comp,
                    "qtd_registros": qtd,
                    "link_direto": gerar_link_direto(comp) if comp else "",
                }
            )
        matriz.append(
            {
                "config": cfg,
                "pode_editar": eh_gestor(request.user)
                or (
                    not ciclo.bloqueado_para_edicao_focal
                    and _usuario_pode_editar_config(request.user, cfg)
                ),
                "tabs": tabs_for_pilar(cfg.codigo),
                "celulas": celulas,
                "total_registros": total_pilar_regs,
            }
        )

    logs_sla = (
        LogNotificacaoSLA.objects.filter(
            competencia__ciclo=ciclo,
            competencia__configuracao_pilar__in=configs_visiveis,
        )
        .select_related("competencia__configuracao_pilar")
        .order_by("-enviado_em", "-id")[:25]
    )

    periodos_portal = list(
        Periodo.objects.filter(
            competencia__year=ano, competencia__month__in=ciclo.meses_indices
        ).order_by("competencia")
    )
    periodo_aprovacao = (
        Periodo.objects.filter(status__in=["ABERTO", "REABERTO"]).order_by("-competencia").first()
        or Periodo.objects.order_by("-competencia").first()
    )

    export_arquivos = []
    for tag, meta in (
        ("FIN", "Planilha 1 — Financeiro (Aba 10 + Abas Azuis 11–18)"),
        ("FCRH", "Planilha 2 — Técnico FCRH"),
        ("ACS", "Planilha 3 — Técnico ACS"),
        ("AFCCT", "Planilha 4 — Técnico AFCCT"),
        ("AT", "Planilha 5 — Técnico AT"),
    ):
        pode_baixar = eh_gestor(request.user) or eh_lideranca(request.user) or eh_auditor(request.user) or any(
            c.arquivo_embrapii == tag and _usuario_pode_editar_config(request.user, c)
            for c in configs_visiveis
        )
        export_arquivos.append({"tag": tag, "rotulo": meta, "disponivel": pode_baixar})

    anos_disponiveis = sorted(
        {2025, 2026, 2027, ano}
        | set(CicloSemestral.objects.values_list("ano", flat=True))
    )

    semaforo_coerencia = (
        calcular_semaforo_coerencia(ciclo=ciclo)
        if (eh_gestor(request.user) or eh_auditor(request.user))
        else None
    )

    return render(
        request,
        "semestral/painel.html",
        {
            "ciclo": ciclo,
            "ano": ano,
            "semestre": semestre,
            "anos_disponiveis": anos_disponiveis,
            "meses_header": meses_header,
            "matriz": matriz,
            "totais": totais_status,
            "logs_sla": logs_sla,
            "periodos_portal": periodos_portal,
            "periodo_aprovacao": periodo_aprovacao,
            "export_arquivos": export_arquivos,
            "semaforo_coerencia": semaforo_coerencia,
            "eh_gestor": eh_gestor(request.user),
            "pode_exportar_pacote": eh_gestor(request.user)
            or eh_lideranca(request.user)
            or eh_auditor(request.user),
        },
    )


@login_required
def acesso_direto(request, token):
    """Resolve link direto tokenizado do alerta mensal / ITS1 para o formulário da competência."""
    comp = get_object_or_404(
        CompetenciaMensalPilar.objects.select_related("ciclo", "configuracao_pilar"),
        token_acesso=token,
    )
    if not _usuario_pode_acessar_config(request.user, comp.configuracao_pilar):
        return sem_permissao(request)
    aba = request.GET.get("aba", "")
    destino = reverse("semestral:competencia_form", args=[comp.pk])
    if aba:
        destino = f"{destino}?aba={aba}"
    return redirect(destino)


def _serialize_cell_display(obj, attr_name: str):
    val = getattr(obj, attr_name, "")
    if val is None or val == "":
        return "—"
    if isinstance(val, date):
        return val.strftime("%d/%m/%Y")
    return val


@login_required
def competencia_form(request, pk: int):
    """Coleta mensal por pilar/aba com validações oficiais v3.1 e submissão."""
    comp = get_object_or_404(
        CompetenciaMensalPilar.objects.select_related(
            "ciclo", "configuracao_pilar", "submetido_por", "revisado_por"
        ),
        pk=pk,
    )
    cfg = comp.configuracao_pilar
    if not _usuario_pode_acessar_config(request.user, cfg):
        return sem_permissao(request)

    gestor = eh_gestor(request.user)
    bloqueada_por_ciclo = comp.ciclo.bloqueado_para_edicao_focal
    bloqueada_aprovacao = comp.status_aprovacao == "APROVADO" and not gestor
    pode_editar = _usuario_pode_mutar_competencia(request.user, comp)
    tabs = tabs_for_pilar(cfg.codigo)
    spec = get_tab_spec(cfg.codigo, request.GET.get("aba"))

    editar_id = request.GET.get("editar")
    instancia = None
    if editar_id and pode_editar:
        qs_edit = spec.model.objects.filter(competencia_mensal=comp, pk=editar_id)
        if spec.is_comment_sheet:
            qs_edit = qs_edit.filter(arquivo=spec.arquivo, aba=spec.aba)
        instancia = get_object_or_404(qs_edit)

    if request.method == "POST":
        if not pode_editar:
            return sem_permissao(request)
        form = build_tab_record_form(
            spec, comp.ciclo, request.POST, instance=instancia
        )
        if form.is_valid():
            with transaction.atomic():
                obj = form.save(commit=False)
                obj.competencia_mensal = comp
                if not obj.pk:
                    obj.criado_por = request.user
                if spec.is_comment_sheet:
                    obj.arquivo = spec.arquivo
                    obj.aba = spec.aba
                obj.save()
                nota_vinculo = ""
                proj_of = getattr(obj, "projeto_oficial", None)
                if proj_of is not None:
                    nota_vinculo = f" [Portfólio oficial: {proj_of.nome} ({proj_of.pk})]"
                registrar_auditoria(
                    usuario=request.user,
                    acao="SEMESTRAL_REGISTRO_ATUALIZADO" if instancia else "SEMESTRAL_REGISTRO_CRIADO",
                    entidade=spec.model.__name__,
                    registro_id=obj.pk,
                    campo=spec.aba,
                    valor_novo=str(getattr(obj, spec.list_columns[0], obj.pk))[:200],
                    justificativa=(
                        f"{_prefixo_auditoria_ciclo(comp.ciclo)}"
                        f"Coleta mensal {comp.competencia_mm_aaaa} ({cfg.codigo}).{nota_vinculo}"
                    ),
                    origem="Portal",
                )
            messages.success(
                request,
                f"Registro salvo em '{spec.aba}' ({comp.competencia_mm_aaaa}).",
            )
            return redirect(f"{reverse('semestral:competencia_form', args=[comp.pk])}?aba={spec.slug}")
    else:
        form = build_tab_record_form(spec, comp.ciclo, instance=instancia)

    # Contagens por aba desta competência
    tabs_nav = []
    for t in tabs:
        q_t = t.model.objects.filter(competencia_mensal=comp)
        if t.is_comment_sheet:
            q_t = q_t.filter(arquivo=t.arquivo, aba=t.aba)
        tabs_nav.append(
            {
                "spec": t,
                "count": q_t.count(),
                "ativa": t.slug == spec.slug,
            }
        )

    # Registros existentes na aba ativa
    qs_regs = spec.model.objects.filter(competencia_mensal=comp)
    if spec.portfolio_pilar_codigo:
        qs_regs = qs_regs.select_related("projeto_oficial")
    if spec.is_comment_sheet:
        qs_regs = qs_regs.filter(arquivo=spec.arquivo, aba=spec.aba)
    registros = list(qs_regs.order_by("id"))

    # Prévia determinística de códigos (quando aplicável)
    codigos_preview: Dict[int, str] = {}
    if spec.has_code_preview:
        all_cycle_projs = list(
            spec.model.objects.filter(competencia_mensal__ciclo=comp.ciclo).order_by(
                "competencia_mensal__competencia", "id"
            )
        )
        seen_dates: Dict[date, int] = {}
        abrev = comp.ciclo.abreviacao_cc or "QIN"
        for p in all_cycle_projs:
            d = getattr(p, "data_inicio", None)
            if d:
                seq = seen_dates.get(d, 0) + 1
                seen_dates[d] = seq
                codigos_preview[p.pk] = p.codigo_preview(seq=seq, abrev=abrev)

    colunas_labels = [
        (
            "Contrib. Total (R$)"
            if c == "contrib_total"
            else spec.model._meta.get_field(c).verbose_name
        )
        for c in spec.list_columns
    ]
    linhas_tabela = []
    for r in registros:
        linhas_tabela.append(
            {
                "obj": r,
                "codigo_preview": codigos_preview.get(r.pk, ""),
                "projeto_oficial": getattr(r, "projeto_oficial", None),
                "celulas": [_serialize_cell_display(r, c) for c in spec.list_columns],
            }
        )

    sugestoes_projetos = get_project_code_suggestions(comp.ciclo, spec)
    projetos_oficiais = (
        listar_projetos_oficiais_para_pilar(spec.portfolio_pilar_codigo)
        if spec.portfolio_pilar_codigo
        else []
    )
    ponte_operacional = (
        calcular_sugestoes_competencia(comp)
        if (gestor and comp.status_aprovacao == "APROVADO")
        else None
    )
    logs_comp = comp.logs_sla.order_by("-enviado_em", "-id")[:10]
    periodo_aprovacao = (
        Periodo.objects.filter(status__in=["ABERTO", "REABERTO"]).order_by("-competencia").first()
        or Periodo.objects.order_by("-competencia").first()
    )

    return render(
        request,
        "semestral/competencia_form.html",
        {
            "ciclo": comp.ciclo,
            "comp": comp,
            "cfg": cfg,
            "spec": spec,
            "tabs_nav": tabs_nav,
            "form": form,
            "instancia": instancia,
            "pode_editar": pode_editar,
            "bloqueada_por_ciclo": bloqueada_por_ciclo,
            "bloqueada_aprovacao": bloqueada_aprovacao,
            "eh_gestor": gestor,
            "periodo_aprovacao": periodo_aprovacao,
            "colunas_labels": colunas_labels,
            "linhas_tabela": linhas_tabela,
            "sugestoes_projetos": sugestoes_projetos,
            "projetos_oficiais": projetos_oficiais,
            "ponte_operacional": ponte_operacional,
            "submissao_form": SubmissaoCompetenciaForm(),
            "logs_comp": logs_comp,
            "link_direto": request.build_absolute_uri(gerar_link_direto(comp, aba_codigo=spec.slug)),
        },
    )


@login_required
@require_POST
def integrar_operacional_view(request, pk: int):
    """Ponte assistida com 1 clique (Fase 2): gera ou publica LancamentoOperacional a partir do Semestral."""
    if not eh_gestor(request.user):
        return sem_permissao(request)
    comp = get_object_or_404(
        CompetenciaMensalPilar.objects.select_related("ciclo", "configuracao_pilar"),
        pk=pk,
    )
    tipo_alvo = (request.POST.get("tipo_alvo") or "").strip()
    valor_alvo_final = (request.POST.get("valor_alvo_final") or "").strip()
    modo = (request.POST.get("modo") or "PROPOSTA").strip().upper()
    justificativa = (request.POST.get("justificativa") or "").strip()
    reaplicar = request.POST.get("reaplicar") == "1"

    fallback_url = f"{reverse('semestral:competencia_form', args=[comp.pk])}#ponte-operacional"
    try:
        integracao = aplicar_sugestao_operacional(
            comp=comp,
            tipo_alvo=tipo_alvo,
            usuario=request.user,
            valor_alvo_final=valor_alvo_final or None,
            modo=modo,
            justificativa=justificativa,
            reaplicar=reaplicar,
        )
        if modo == "DIRETO":
            messages.success(
                request,
                f"Integração aplicada e publicada diretamente nos Dashboards ({integracao.tipo_alvo}). "
                f"Lançamento operacional registrado e auditado.",
            )
        else:
            messages.success(
                request,
                f"Proposta operacional enviada para o Painel de aprovação ({integracao.tipo_alvo}). "
                f"Os Dashboards serão atualizados assim que a proposta for aprovada.",
            )
    except PermissionDenied:
        return sem_permissao(request)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect(_safe_next_url(request, fallback_url))


@login_required
@require_POST
def aprovar_integracao_operacional_view(request, integracao_pk: int):
    """Aprova em 1 clique uma proposta operacional da Ponte Semestral e publica nos Dashboards."""
    if not eh_gestor(request.user):
        return sem_permissao(request)
    from .models import IntegracaoSemestralOperacional

    integ_ref = get_object_or_404(
        IntegracaoSemestralOperacional.objects.select_related("competencia_mensal"),
        pk=integracao_pk,
    )
    fallback_url = f"{reverse('semestral:competencia_form', args=[integ_ref.competencia_mensal_id])}#ponte-operacional"
    try:
        integ = aprovar_integracao_operacional(integracao_pk, request.user)
        messages.success(
            request,
            f"Proposta operacional aprovada e publicada nos Dashboards ({integ.tipo_alvo}).",
        )
    except PermissionDenied:
        return sem_permissao(request)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect(_safe_next_url(request, fallback_url))


@login_required
@require_POST
def sincronizar_projeto_oficial_view(request, pk: int, aba: str, reg_id: int):
    """Promove projeto novo do Semestral aprovado ao Portfólio Oficial (Entregáveis + Financeiro + Base)."""
    if not eh_gestor(request.user):
        return sem_permissao(request)
    comp = get_object_or_404(
        CompetenciaMensalPilar.objects.select_related("ciclo", "configuracao_pilar"),
        pk=pk,
    )
    fallback_url = f"{reverse('semestral:competencia_form', args=[comp.pk])}?aba={aba}#ponte-operacional"
    try:
        resultado = sincronizar_projeto_para_catalogo_oficial(
            comp=comp,
            aba_slug=aba,
            reg_id=reg_id,
            usuario=request.user,
        )
        proj = resultado["projeto"]
        messages.success(
            request,
            f"Projeto '{proj.nome}' cadastrado no Portfólio Oficial e na tabela financeira do pilar "
            f"(com Realizado inicial R$ 0,00). Ele já aparece em Entregáveis dos projetos e está pronto "
            f"para receber lançamentos financeiros de Realizado.",
        )
    except PermissionDenied:
        return sem_permissao(request)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect(_safe_next_url(request, fallback_url))


@login_required
@require_POST
def excluir_registro(request, pk: int, aba: str, reg_id: int):
    comp = get_object_or_404(
        CompetenciaMensalPilar.objects.select_related("ciclo", "configuracao_pilar"),
        pk=pk,
    )
    if not _usuario_pode_mutar_competencia(request.user, comp):
        return sem_permissao(request)
    spec = get_tab_spec(comp.configuracao_pilar.codigo, aba)
    qs = spec.model.objects.filter(competencia_mensal=comp, pk=reg_id)
    if spec.is_comment_sheet:
        qs = qs.filter(arquivo=spec.arquivo, aba=spec.aba)
    reg = get_object_or_404(qs)
    resumo = str(getattr(reg, spec.list_columns[0], reg.pk))[:200]
    reg.delete()
    registrar_auditoria(
        usuario=request.user,
        acao="SEMESTRAL_REGISTRO_EXCLUIDO",
        entidade=spec.model.__name__,
        registro_id=reg_id,
        campo=spec.aba,
        valor_anterior=resumo,
        justificativa=(
            f"{_prefixo_auditoria_ciclo(comp.ciclo)}"
            f"Exclusão em {comp.competencia_mm_aaaa} ({comp.configuracao_pilar.codigo})."
        ),
        origem="Portal",
    )
    messages.info(request, f"Registro removido de '{spec.aba}'.")
    return redirect(f"{reverse('semestral:competencia_form', args=[comp.pk])}?aba={spec.slug}")


@login_required
@require_POST
def submeter_competencia_view(request, pk: int):
    comp = get_object_or_404(
        CompetenciaMensalPilar.objects.select_related("ciclo", "configuracao_pilar"),
        pk=pk,
    )
    if not _usuario_pode_mutar_competencia(request.user, comp):
        return sem_permissao(request)
    form = SubmissaoCompetenciaForm(request.POST)
    obs = form.cleaned_data["observacao_submissao"] if form.is_valid() else ""
    submeter_competencia(comp, usuario=request.user, observacao=obs)
    if comp.status == "REGULARIZADO":
        messages.success(
            request,
            f"Competência {comp.competencia_mm_aaaa} ({comp.configuracao_pilar.codigo}) regularizada após ITS1 e enviada para análise da Coordenação!",
        )
    else:
        messages.success(
            request,
            f"Competência {comp.competencia_mm_aaaa} ({comp.configuracao_pilar.codigo}) submetida no prazo e enviada para análise no Painel de aprovação.",
        )
    return redirect("semestral:competencia_form", pk=comp.pk)


@login_required
@require_POST
def aprovar_competencia_view(request, pk: int):
    if not pode_aprovar(request.user):
        return sem_permissao(request)
    comp = get_object_or_404(
        CompetenciaMensalPilar.objects.select_related("ciclo", "configuracao_pilar"),
        pk=pk,
    )
    base_url = request.build_absolute_uri("/")[:-1]
    comentario = (request.POST.get("comentario") or "").strip()
    try:
        aprovar_competencia(comp, usuario=request.user, comentario=comentario, base_url=base_url)
        messages.success(
            request,
            f"Competência {comp.competencia_mm_aaaa} ({comp.configuracao_pilar.codigo}) aprovada pela Coordenação.",
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect(_safe_next_url(request, _painel_aprovacao_padrao_url()))


@login_required
@require_POST
def devolver_competencia_view(request, pk: int):
    if not pode_aprovar(request.user):
        return sem_permissao(request)
    comp = get_object_or_404(
        CompetenciaMensalPilar.objects.select_related("ciclo", "configuracao_pilar"),
        pk=pk,
    )
    base_url = request.build_absolute_uri("/")[:-1]
    justificativa = (request.POST.get("justificativa") or "").strip()
    try:
        devolver_competencia(
            comp, usuario=request.user, justificativa=justificativa, base_url=base_url
        )
        messages.warning(
            request,
            f"Competência {comp.competencia_mm_aaaa} ({comp.configuracao_pilar.codigo}) devolvida para correção do Ponto Focal.",
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect(_safe_next_url(request, _painel_aprovacao_padrao_url()))


@login_required
@require_POST
def arquivar_competencia_view(request, pk: int):
    if not pode_aprovar(request.user):
        return sem_permissao(request)
    comp = get_object_or_404(
        CompetenciaMensalPilar.objects.select_related("ciclo", "configuracao_pilar"),
        pk=pk,
    )
    acao = (request.POST.get("acao") or "arquivar").strip().lower()
    arquivar = acao != "desarquivar"
    try:
        arquivar_competencia(comp, usuario=request.user, arquivar=arquivar)
        if arquivar:
            messages.info(
                request,
                f"Entrega aprovada {comp.configuracao_pilar.codigo} ({comp.competencia_mm_aaaa}) arquivada no painel.",
            )
        else:
            messages.info(
                request,
                f"Entrega aprovada {comp.configuracao_pilar.codigo} ({comp.competencia_mm_aaaa}) restaurada na coluna Aprovados.",
            )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect(_safe_next_url(request, _painel_aprovacao_padrao_url()))


@login_required
@require_POST
def arquivar_aprovados_em_lote_view(request):
    if not pode_aprovar(request.user):
        return sem_permissao(request)
    qs = CompetenciaMensalPilar.objects.select_related("configuracao_pilar").filter(
        status_aprovacao="APROVADO",
        arquivado_painel=False,
        configuracao_pilar__ativo=True,
    )
    qtd = 0
    for comp in qs:
        arquivar_competencia(comp, usuario=request.user, arquivar=True)
        qtd += 1
    if qtd:
        messages.info(request, f"{qtd} entrega(s) aprovada(s) arquivada(s) no painel.")
    else:
        messages.info(request, "Nenhuma entrega aprovada ativa para arquivar.")
    return redirect(_safe_next_url(request, _painel_aprovacao_padrao_url()))


@login_required
def exportar_xlsx_view(request, arquivo: str):
    tag = arquivo.upper()
    if tag not in TEMPLATE_MAP:
        return sem_permissao(request)
    ano, semestre = _resolver_ano_semestre(request.GET)
    ciclo = _garantir_ciclo(ano, semestre)

    autorizado = eh_gestor(request.user) or eh_lideranca(request.user) or eh_auditor(request.user) or any(
        _usuario_pode_editar_config(request.user, cfg)
        for cfg in ConfiguracaoPilarSemestral.objects.filter(arquivo_embrapii=tag, ativo=True)
    )
    if not autorizado:
        return sem_permissao(request)

    filename, content = exportar_planilha_embrapii(ciclo, tag)
    registrar_auditoria(
        usuario=request.user,
        acao="SEMESTRAL_EXPORTACAO_XLSX",
        entidade="CicloSemestral",
        registro_id=ciclo.pk,
        campo=tag,
        valor_novo=filename,
        justificativa=f"Exportação EMBRAPII v3.1 ({ciclo.rotulo_painel}).",
        origem="Portal",
    )
    resp = HttpResponse(
        content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


@login_required
def exportar_pacote_zip_view(request):
    if not (eh_gestor(request.user) or eh_lideranca(request.user) or eh_auditor(request.user)):
        return sem_permissao(request)
    ano, semestre = _resolver_ano_semestre(request.GET)
    ciclo = _garantir_ciclo(ano, semestre)
    zip_name, zip_bytes = exportar_pacote_semestral_zip(ciclo)
    registrar_auditoria(
        usuario=request.user,
        acao="SEMESTRAL_EXPORTACAO_ZIP",
        entidade="CicloSemestral",
        registro_id=ciclo.pk,
        campo="PACOTE_5_ARQUIVOS",
        valor_novo=zip_name,
        justificativa=f"Exportação consolidada dos 5 arquivos EMBRAPII v3.1 ({ciclo.rotulo_painel}).",
        origem="Portal",
    )
    resp = HttpResponse(zip_bytes, content_type="application/zip")
    resp["Content-Disposition"] = f'attachment; filename="{zip_name}"'
    return resp


@login_required
@require_POST
def sla_disparar_alertas_view(request):
    if not eh_gestor(request.user):
        return sem_permissao(request)
    ano, semestre = _resolver_ano_semestre(request.POST)
    ciclo = _garantir_ciclo(ano, semestre)
    comp_iso = (request.POST.get("competencia") or "").strip()
    comp_date = None
    if comp_iso:
        try:
            y, m = [int(p) for p in comp_iso.split("-")]
            comp_date = date(y, m, 1)
        except ValueError:
            comp_date = None
    base_url = request.build_absolute_uri("/")[:-1]
    res = disparar_alertas_mensais(
        competencia_date=comp_date,
        ciclo=ciclo,
        base_url=base_url,
        actor=request.user,
        incluir_relembrar=bool(request.POST.get("reenviar")),
    )
    messages.success(
        request,
        f"Alertas mensais disparados: {res['enviados']} notificação(ões) com link direto e prazo enviadas.",
    )
    return redirect(f"{reverse('core:semestral')}?ano={ano}&semestre={semestre}")


@login_required
@require_POST
def sla_verificar_its1_view(request):
    if not eh_gestor(request.user):
        return sem_permissao(request)
    ano, semestre = _resolver_ano_semestre(request.POST)
    ciclo = _garantir_ciclo(ano, semestre)
    ref_raw = (request.POST.get("referencia_dt") or "").strip()
    agora = timezone.now()
    if ref_raw:
        try:
            parsed = datetime.fromisoformat(ref_raw)
            agora = (
                timezone.make_aware(parsed, timezone.get_current_timezone())
                if timezone.is_naive(parsed)
                else parsed
            )
        except ValueError:
            pass
    base_url = request.build_absolute_uri("/")[:-1]
    res = verificar_sla_e_emitir_its1(
        agora=agora, ciclo=ciclo, base_url=base_url, actor=request.user
    )
    if res["emitidas"]:
        messages.warning(
            request,
            f"SLA verificado: {res['emitidas']} advertência(s) ITS1 emitida(s) com comunicado à Coordenação ({ciclo.coordenacao_nome}).",
        )
    else:
        messages.info(
            request,
            "Verificação SLA concluída: nenhuma nova competência vencida sem submissão para a data informada.",
        )
    return redirect(f"{reverse('core:semestral')}?ano={ano}&semestre={semestre}")


@login_required
def configurar_ciclo_view(request):
    if not eh_gestor(request.user):
        return sem_permissao(request)
    ano, semestre = _resolver_ano_semestre(request.GET or request.POST)
    ciclo = _garantir_ciclo(ano, semestre)
    pilares = list(ConfiguracaoPilarSemestral.objects.order_by("ordem", "codigo"))
    semaforo_coerencia = calcular_semaforo_coerencia(ciclo=ciclo)

    if request.method == "POST":
        status_anterior = ciclo.status
        ciclo_form = CicloSemestralConfigForm(request.POST, instance=ciclo, prefix="ciclo")
        pilar_forms = [
            PilarSemestralConfigForm(request.POST, instance=p, prefix=f"pilar_{p.codigo}")
            for p in pilares
        ]
        if ciclo_form.is_valid() and all(pf.is_valid() for pf in pilar_forms):
            with transaction.atomic():
                ciclo_salvo = ciclo_form.save()
                for pf in pilar_forms:
                    pf.save()
                justificativa = f"Parâmetros e responsáveis atualizados ({ciclo_salvo.rotulo_painel})."
                if (
                    ciclo_salvo.status != status_anterior
                    and ciclo_salvo.status in ("CONSOLIDADO", "ENVIADO")
                    and semaforo_coerencia.get("disponivel")
                ):
                    r = semaforo_coerencia["resumo"]
                    justificativa += (
                        f" Semáforo de coerência no fechamento: {r['alinhados']} alinhado(s), "
                        f"{r['divergentes']} divergente(s), {r['integracoes_aplicadas']} integração(ões) aplicada(s)."
                    )
                registrar_auditoria(
                    usuario=request.user,
                    acao="SEMESTRAL_CONFIG_ATUALIZADA",
                    entidade="CicloSemestral",
                    registro_id=ciclo_salvo.pk,
                    campo="status" if ciclo_salvo.status != status_anterior else "",
                    valor_anterior=status_anterior if ciclo_salvo.status != status_anterior else "",
                    valor_novo=ciclo_salvo.status if ciclo_salvo.status != status_anterior else "",
                    justificativa=justificativa,
                    origem="Portal",
                )
            messages.success(request, "Configurações do ciclo semestral e responsáveis atualizadas.")
            return redirect(f"{reverse('core:semestral')}?ano={ano}&semestre={semestre}")
    else:
        ciclo_form = CicloSemestralConfigForm(instance=ciclo, prefix="ciclo")
        pilar_forms = [
            PilarSemestralConfigForm(instance=p, prefix=f"pilar_{p.codigo}")
            for p in pilares
        ]

    return render(
        request,
        "semestral/configurar.html",
        {
            "ciclo": ciclo,
            "ano": ano,
            "semestre": semestre,
            "ciclo_form": ciclo_form,
            "pilar_forms": list(zip(pilares, pilar_forms)),
            "semaforo_coerencia": semaforo_coerencia,
        },
    )


@login_required
def exportar_csv_semestral(request):
    """Exporta resumo consolidado CSV das competências mensais e contagens do semestre."""
    if not _usuario_tem_leitura_semestral(request.user):
        return sem_permissao(request)
    ano, semestre = _resolver_ano_semestre(request.GET)
    ciclo = _garantir_ciclo(ano, semestre)
    configs = [
        c
        for c in ConfiguracaoPilarSemestral.objects.filter(ativo=True).order_by("ordem", "codigo")
        if _usuario_pode_acessar_config(request.user, c)
    ]
    contagens = _contar_registros_por_competencia(ciclo)
    comps = (
        CompetenciaMensalPilar.objects.filter(ciclo=ciclo, configuracao_pilar__in=configs)
        .select_related("configuracao_pilar")
        .order_by("competencia", "configuracao_pilar__ordem")
    )
    linhas = ["ciclo;pilar;planilha;competencia;status;status_aprovacao;prazo_limite;registros;responsavel_email"]
    for c in comps:
        linhas.append(
            f"{ciclo.rotulo_painel};{c.configuracao_pilar.codigo};{c.configuracao_pilar.arquivo_embrapii};"
            f"{c.competencia_mm_aaaa};{c.get_status_display()};{c.get_status_aprovacao_display()};"
            f"{c.prazo_limite.strftime('%Y-%m-%d %H:%M')};"
            f"{contagens.get(c.pk, 0)};{c.configuracao_pilar.responsavel_email}"
        )
    resp = HttpResponse("\ufeff" + "\n".join(linhas) + "\n", content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="quiin_semestral_{ano}_S{semestre}.csv"'
    return resp
