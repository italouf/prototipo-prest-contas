"""Integração assistida entre Prestação Semestral (EMBRAPII v3.1) e Base Operacional / FINANCEIRO_GERAL.

Implementa as 3 fases de integração mantendo governança, idempotência e auditabilidade:
- Fase 1: Lista única de projetos oficiais (FINANCEIRO_GERAL -> formulários semestrais).
- Fase 2: Ponte assistida com 1 clique (competência semestral aprovada -> Base Operacional).
- Fase 3: Semáforo de coerência na conciliação (FINANCEIRO_GERAL / Base Operacional vs Semestral v3.1).
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.urls import reverse

from apps.accountability.models import (
    Acompanhamento,
    KpiAcompanhamento,
    ProjetoFinanceiro,
    ResumoFinanceiro,
)
from apps.audit.services import registrar_auditoria
from apps.core.permissions import eh_gestor
from apps.core.templatetags.core_extras import numero_ptbr
from apps.entries import operational as op
from apps.entries.effective import estado as ler_estado_operacional, invalidar as invalidar_cache_operacional
from apps.entries.models import (
    BaseOperacional,
    IndicadorOperacional,
    ProjetoFinanceiroFonte,
)
from apps.periods.models import Periodo
from apps.periods.services import abrir_periodo
from apps.pillars.models import Pilar
from apps.projects.models import Projeto

from .models import (
    CicloSemestral,
    CompetenciaMensalPilar,
    IntegracaoSemestralOperacional,
)
from .models_registros import (
    RegAcsEmpresa,
    RegAcsPedidoPi,
    RegAcsProjetoPdi,
    RegAcsPublicacao,
    RegAfcctPedidoPi,
    RegAfcctProjetoPdi,
    RegAfcctPublicacao,
    RegAtAtividade,
    RegFcrhProfissional,
    RegFcrhProjeto,
    RegFinAssociadas,
    RegFinOutrasFontes,
)

ZERO = Decimal("0")
TOLERANCIA_MONETARIA = Decimal("0.01")
CARTEIRA_SEMESTRAL_NOME = "Consolidação Semestral v3.1"

ABA_PARA_PILAR_OFICIAL: Dict[str, str] = {
    "afcct-2": "PDI",
    "fcrh-2": "FORMACAO",
    "acs-2": "STARTUPS",
}

PILAR_OFICIAL_PARA_MODELO_SEMESTRAL = {
    "PDI": ("AFCCT", "afcct-2", RegAfcctProjetoPdi),
    "FORMACAO": ("FCRH", "fcrh-2", RegFcrhProjeto),
    "STARTUPS": ("ACS", "acs-2", RegAcsProjetoPdi),
}


def acompanhamento_vigente(acompanhamento: Optional[Acompanhamento] = None) -> Optional[Acompanhamento]:
    if acompanhamento is not None:
        return acompanhamento
    return Acompanhamento.objects.select_related("centro").order_by("-criado_em", "-pk").first()


def formatar_valor_integracao(valor: Optional[Decimal], tipo: str, unidade: str = "") -> str:
    if valor is None:
        return "—"
    if tipo == "MON":
        return f"R$ {numero_ptbr(valor)}"
    if tipo == "QTD":
        sufixo = f" {unidade}" if unidade and unidade != "un" else ""
        return f"{int(valor)}{sufixo}"
    return numero_ptbr(valor)


def parse_decimal_integracao(bruto: Any, tipo: str) -> Decimal:
    texto = str(bruto if bruto is not None else "").strip().replace("R$", "").replace(" ", "")
    if not texto:
        raise ValidationError("Informe um valor numérico válido.")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        valor = Decimal(texto)
    except (InvalidOperation, ValueError):
        raise ValidationError("Informe um valor numérico válido.")
    if not valor.is_finite() or valor < ZERO or valor >= Decimal("1000000000000"):
        raise ValidationError("Valor fora do intervalo permitido.")
    if tipo == "QTD":
        if valor != valor.to_integral_value():
            raise ValidationError("Indicadores de quantidade exigem números inteiros.")
        return valor.quantize(Decimal("1"))
    if tipo == "MON":
        if valor != valor.quantize(Decimal("0.01")):
            raise ValidationError("Valores monetários aceitam no máximo 2 casas decimais.")
        return valor.quantize(Decimal("0.01"))
    return valor


# ---------------------------------------------------------------------------
# FASE 1 — LISTA ÚNICA DE PROJETOS (FINANCEIRO_GERAL -> SEMESTRAL)
# ---------------------------------------------------------------------------


def listar_projetos_oficiais_para_pilar(
    pilar_codigo: str,
    acompanhamento: Optional[Acompanhamento] = None,
) -> List[Dict[str, Any]]:
    """Retorna o catálogo oficial de projetos do pilar enriquecido com metadados do FINANCEIRO_GERAL."""
    if not pilar_codigo:
        return []

    acomp = acompanhamento_vigente(acompanhamento)
    projetos = list(
        Projeto.objects.filter(ativo=True, pilar__codigo=pilar_codigo)
        .select_related("pilar", "centro")
        .order_by("nome", "pk")
    )
    if not projetos:
        return []

    # Mapa de metadados do ProjetoFinanceiro mais recente para cada projeto
    fin_por_projeto: Dict[Any, ProjetoFinanceiro] = {}
    if acomp is not None:
        for pf in ProjetoFinanceiro.objects.filter(
            acompanhamento=acomp, projeto_id__in=[p.pk for p in projetos]
        ).order_by("sequencia", "id"):
            fin_por_projeto.setdefault(pf.projeto_id, pf)

    faltantes = [p.pk for p in projetos if p.pk not in fin_por_projeto]
    if faltantes:
        for pf in ProjetoFinanceiro.objects.filter(projeto_id__in=faltantes).order_by(
            "-acompanhamento__criado_em", "-pk"
        ):
            fin_por_projeto.setdefault(pf.projeto_id, pf)

    resultado: List[Dict[str, Any]] = []
    for proj in projetos:
        pf = fin_por_projeto.get(proj.pk)
        codigo_emb = (pf.codigo_projeto_embrapii if pf and pf.codigo_projeto_embrapii else proj.codigo_embrapii) or ""
        status_fin = (pf.status if pf and pf.status else "").strip()
        orcado = pf.orcado if pf and pf.orcado is not None else None
        data_inicio = (pf.data_kickoff or pf.inicio) if pf else None
        data_termino = (pf.fim_previsto_real or pf.fim) if pf else None

        partes_rotulo = [proj.nome]
        if codigo_emb:
            partes_rotulo.append(f"Cód. {codigo_emb}")
        if orcado is not None:
            partes_rotulo.append(f"Orçado R$ {numero_ptbr(orcado)}")

        resultado.append(
            {
                "id": str(proj.pk),
                "nome": proj.nome,
                "codigo_embrapii": codigo_emb,
                "status": status_fin,
                "valor_orcado": f"{orcado:.2f}" if orcado is not None else "",
                "data_inicio": data_inicio.isoformat() if data_inicio else "",
                "data_termino": data_termino.isoformat() if data_termino else "",
                "rotulo": " · ".join(partes_rotulo),
            }
        )
    return resultado


def validar_vinculo_projeto_oficial(spec, projeto_oficial: Optional[Projeto]) -> None:
    """Garante integridade referencial de pilar no vínculo Projeto oficial <-> Semestral."""
    if projeto_oficial is None:
        return
    pilar_esperado = getattr(spec, "portfolio_pilar_codigo", None) or ABA_PARA_PILAR_OFICIAL.get(spec.slug)
    if not pilar_esperado:
        raise ValidationError("Esta aba não aceita vínculo com projeto do portfólio oficial.")
    if not projeto_oficial.ativo:
        raise ValidationError("O projeto oficial selecionado está inativo no catálogo.")
    if projeto_oficial.pilar.codigo != pilar_esperado:
        raise ValidationError(
            f"Projeto oficial pertence ao pilar {projeto_oficial.pilar.codigo}, "
            f"incompatível com esta aba (esperado: {pilar_esperado})."
        )


# ---------------------------------------------------------------------------
# FASE 2 — PONTE ASSISTIDA COM 1 CLIQUE (SEMESTRAL APROVADO -> BASE OPERACIONAL)
# ---------------------------------------------------------------------------


def _eh_sim(valor: Any) -> bool:
    return str(valor or "").strip().lower().startswith("sim")


def _eh_origem_outra_fonte(valor: Any) -> bool:
    texto = str(valor or "").strip().lower()
    return "outra" in texto or "outro" in texto


def _obter_carteira_semestral(acomp: Acompanhamento, pilar: Pilar) -> Optional[ProjetoFinanceiroFonte]:
    return ProjetoFinanceiroFonte.objects.filter(
        centro=acomp.centro, pilar=pilar, nome=CARTEIRA_SEMESTRAL_NOME, ativo=True
    ).first()


def _garantir_indicador_fonte_semestral(
    base: BaseOperacional, pilar: Pilar, campo: str, usuario
) -> IndicadorOperacional:
    """Garante a carteira 'Consolidação Semestral v3.1' (abertura 0/0) e retorna seu IndicadorOperacional."""
    acomp = base.acompanhamento
    total_base = op.decimal(base.snapshot.get("totais", {}).get(pilar.codigo, {}).get(campo))
    if total_base is None:
        raise ValidationError(
            f"O pilar {pilar.codigo} não possui saldo consolidado de '{campo}' (TAB. 9) "
            f"na Base Operacional atual. Importe o FINANCEIRO_GERAL e concilie a base antes de integrar."
        )

    carteira = _obter_carteira_semestral(acomp, pilar)
    if carteira is None or not IndicadorOperacional.objects.filter(
        acompanhamento=acomp, chave=f"fonte:{carteira.pk}:{campo}", ativo=True
    ).exists():
        carteira = op.criar_projeto_fonte(base, pilar, CARTEIRA_SEMESTRAL_NOME, "0", "0", usuario)

    chave = f"fonte:{carteira.pk}:{campo}"
    indicador = IndicadorOperacional.objects.filter(
        acompanhamento=acomp, chave=chave, ativo=True
    ).first()
    if indicador is None:
        raise ValidationError("Não foi possível inicializar o indicador operacional da carteira semestral.")
    return indicador


def _coletar_candidatos_competencia(comp: CompetenciaMensalPilar) -> List[Dict[str, Any]]:
    """Extrai incrementos determinísticos dos registros lançados na competência semestral."""
    codigo = comp.configuracao_pilar.codigo
    candidatos: List[Dict[str, Any]] = []

    if codigo == "FIN_QUIIN":
        regs_of = list(RegFinOutrasFontes.objects.filter(competencia_mensal=comp))
        soma_of = sum((r.valor or ZERO for r in regs_of), ZERO)
        if soma_of > ZERO:
            candidatos.append(
                {
                    "tipo_alvo": "OUTRASFONTES_REALIZADO",
                    "titulo": "Outras Fontes — Executado (R$)",
                    "categoria": "Financeiro",
                    "alvo": "FONTE",
                    "pilar_codigo": "OUTRASFONTES",
                    "campo": "realizado",
                    "kpi_codigo": None,
                    "tipo": "MON",
                    "unidade": "R$",
                    "incremento": soma_of.quantize(Decimal("0.01")),
                    "qtd_registros_origem": len(regs_of),
                    "detalhe_origem": f"{len(regs_of)} movimentação(ões) na Aba 10. Conta Ação - Outras Fontes",
                }
            )

        regs_assoc = list(RegFinAssociadas.objects.filter(competencia_mensal=comp))
        soma_assoc = sum((Decimal(r.contrib_total or ZERO) for r in regs_assoc), ZERO)
        if soma_assoc > ZERO:
            candidatos.append(
                {
                    "tipo_alvo": "AT_CAPTADO",
                    "titulo": "Associação Tecnológica (AT) — Captado (R$)",
                    "categoria": "Financeiro",
                    "alvo": "FONTE",
                    "pilar_codigo": "AT",
                    "campo": "captado",
                    "kpi_codigo": None,
                    "tipo": "MON",
                    "unidade": "R$",
                    "incremento": soma_assoc.quantize(Decimal("0.01")),
                    "qtd_registros_origem": len(regs_assoc),
                    "detalhe_origem": f"{len(regs_assoc)} empresa(s) associada(s) na Aba 13. Associadas",
                }
            )

        assoc_vigentes = [r for r in regs_assoc if _eh_sim(r.associacao_vigente)]
        if assoc_vigentes:
            candidatos.append(
                {
                    "tipo_alvo": "KPI_PE-03",
                    "titulo": "PE-03 · Empresas associadas à AT (Físico)",
                    "categoria": "Físico",
                    "alvo": "KPI",
                    "pilar_codigo": "AT",
                    "campo": "realizado",
                    "kpi_codigo": "PE-03",
                    "tipo": "QTD",
                    "unidade": "empresas",
                    "incremento": Decimal(len(assoc_vigentes)),
                    "qtd_registros_origem": len(assoc_vigentes),
                    "detalhe_origem": f"{len(assoc_vigentes)} associada(s) vigente(s) na Aba 13",
                }
            )

    elif codigo == "AT":
        regs_at = list(RegAtAtividade.objects.filter(competencia_mensal=comp))
        at_proprio = [r for r in regs_at if not _eh_origem_outra_fonte(r.origem_valor)]
        at_outras = [r for r in regs_at if _eh_origem_outra_fonte(r.origem_valor)]

        soma_at = sum((r.valor_executado or ZERO for r in at_proprio), ZERO)
        if soma_at > ZERO:
            candidatos.append(
                {
                    "tipo_alvo": "AT_REALIZADO",
                    "titulo": "Associação Tecnológica (AT) — Executado (R$)",
                    "categoria": "Financeiro",
                    "alvo": "FONTE",
                    "pilar_codigo": "AT",
                    "campo": "realizado",
                    "kpi_codigo": None,
                    "tipo": "MON",
                    "unidade": "R$",
                    "incremento": soma_at.quantize(Decimal("0.01")),
                    "qtd_registros_origem": len(at_proprio),
                    "detalhe_origem": f"{len(at_proprio)} atividade(s) com recurso AT na Aba 2. Atividades AT",
                }
            )

        soma_outras_at = sum((r.valor_executado or ZERO for r in at_outras), ZERO)
        if soma_outras_at > ZERO:
            candidatos.append(
                {
                    "tipo_alvo": "OUTRASFONTES_REALIZADO_AT",
                    "titulo": "Outras Fontes — Executado via Atividades AT (R$)",
                    "categoria": "Financeiro",
                    "alvo": "FONTE",
                    "pilar_codigo": "OUTRASFONTES",
                    "campo": "realizado",
                    "kpi_codigo": None,
                    "tipo": "MON",
                    "unidade": "R$",
                    "incremento": soma_outras_at.quantize(Decimal("0.01")),
                    "qtd_registros_origem": len(at_outras),
                    "detalhe_origem": f"{len(at_outras)} atividade(s) AT custeadas por Outra Fonte",
                }
            )

    elif codigo == "AFCCT":
        qtd_projs = RegAfcctProjetoPdi.objects.filter(competencia_mensal=comp).count()
        if qtd_projs > 0:
            candidatos.append(
                {
                    "tipo_alvo": "KPI_PE-01",
                    "titulo": "PE-01 · Projetos de PD&I (Físico)",
                    "categoria": "Físico",
                    "alvo": "KPI",
                    "pilar_codigo": "PDI",
                    "campo": "realizado",
                    "kpi_codigo": "PE-01",
                    "tipo": "QTD",
                    "unidade": "projetos",
                    "incremento": Decimal(qtd_projs),
                    "qtd_registros_origem": qtd_projs,
                    "detalhe_origem": f"{qtd_projs} projeto(s) na Aba 2. Info Projetos PD&I AFCCT",
                }
            )
        qtd_pis = RegAfcctPedidoPi.objects.filter(competencia_mensal=comp).count()
        if qtd_pis > 0:
            candidatos.append(
                {
                    "tipo_alvo": "KPI_PE-08",
                    "titulo": "PE-08 · Pedidos de Propriedade Intelectual (Físico)",
                    "categoria": "Físico",
                    "alvo": "KPI",
                    "pilar_codigo": "PDI",
                    "campo": "realizado",
                    "kpi_codigo": "PE-08",
                    "tipo": "QTD",
                    "unidade": "pedidos",
                    "incremento": Decimal(qtd_pis),
                    "qtd_registros_origem": qtd_pis,
                    "detalhe_origem": f"{qtd_pis} pedido(s) de PI na Aba 2.1 (AFCCT)",
                }
            )
        qtd_pubs = RegAfcctPublicacao.objects.filter(competencia_mensal=comp).count()
        if qtd_pubs > 0:
            candidatos.append(
                {
                    "tipo_alvo": "KPI_PE-09",
                    "titulo": "PE-09 · Publicações em periódicos (Físico)",
                    "categoria": "Físico",
                    "alvo": "KPI",
                    "pilar_codigo": "PDI",
                    "campo": "realizado",
                    "kpi_codigo": "PE-09",
                    "tipo": "QTD",
                    "unidade": "publicações",
                    "incremento": Decimal(qtd_pubs),
                    "qtd_registros_origem": qtd_pubs,
                    "detalhe_origem": f"{qtd_pubs} publicação(ões) na Aba 2.2 (AFCCT)",
                }
            )

    elif codigo == "FCRH":
        soma_concl = (
            RegFcrhProjeto.objects.filter(competencia_mensal=comp).aggregate(s=Sum("qtd_concluiram"))["s"]
            or 0
        )
        qtd_prof = RegFcrhProfissional.objects.filter(competencia_mensal=comp).count()
        capacitados = max(soma_concl, qtd_prof)
        if capacitados > 0:
            candidatos.append(
                {
                    "tipo_alvo": "KPI_PE-07",
                    "titulo": "PE-07 · Profissionais Capacitados em PD&I (Físico)",
                    "categoria": "Físico",
                    "alvo": "KPI",
                    "pilar_codigo": "FORMACAO",
                    "campo": "realizado",
                    "kpi_codigo": "PE-07",
                    "tipo": "QTD",
                    "unidade": "profissionais",
                    "incremento": Decimal(capacitados),
                    "qtd_registros_origem": capacitados,
                    "detalhe_origem": (
                        f"Maior entre concluintes nos projetos ({soma_concl}) "
                        f"e nominais na Aba 3 ({qtd_prof})"
                    ),
                }
            )

    elif codigo == "ACS":
        qtd_ebts = sum(
            1
            for e in RegAcsEmpresa.objects.filter(competencia_mensal=comp)
            if _eh_sim(e.eh_ebt_ou_startup)
        )
        if qtd_ebts > 0:
            candidatos.append(
                {
                    "tipo_alvo": "KPI_PE-05",
                    "titulo": "PE-05 · EBTs / Startups envolvidas (Físico)",
                    "categoria": "Físico",
                    "alvo": "KPI",
                    "pilar_codigo": "STARTUPS",
                    "campo": "realizado",
                    "kpi_codigo": "PE-05",
                    "tipo": "QTD",
                    "unidade": "startups",
                    "incremento": Decimal(qtd_ebts),
                    "qtd_registros_origem": qtd_ebts,
                    "detalhe_origem": f"{qtd_ebts} EBT/Startup(s) na Aba 5. Empresas envolvidas (ACS)",
                }
            )
        qtd_projs_acs = RegAcsProjetoPdi.objects.filter(competencia_mensal=comp).count()
        if qtd_projs_acs > 0:
            candidatos.append(
                {
                    "tipo_alvo": "KPI_PE-06",
                    "titulo": "PE-06 · Projetos ACS inovação aberta (Físico)",
                    "categoria": "Físico",
                    "alvo": "KPI",
                    "pilar_codigo": "STARTUPS",
                    "campo": "realizado",
                    "kpi_codigo": "PE-06",
                    "tipo": "QTD",
                    "unidade": "projetos",
                    "incremento": Decimal(qtd_projs_acs),
                    "qtd_registros_origem": qtd_projs_acs,
                    "detalhe_origem": f"{qtd_projs_acs} projeto(s) na Aba 2. Info projetos PD&I ACS",
                }
            )
        qtd_pis_acs = RegAcsPedidoPi.objects.filter(competencia_mensal=comp).count()
        if qtd_pis_acs > 0:
            candidatos.append(
                {
                    "tipo_alvo": "KPI_PE-08",
                    "titulo": "PE-08 · Pedidos de Propriedade Intelectual (Físico)",
                    "categoria": "Físico",
                    "alvo": "KPI",
                    "pilar_codigo": "PDI",
                    "campo": "realizado",
                    "kpi_codigo": "PE-08",
                    "tipo": "QTD",
                    "unidade": "pedidos",
                    "incremento": Decimal(qtd_pis_acs),
                    "qtd_registros_origem": qtd_pis_acs,
                    "detalhe_origem": f"{qtd_pis_acs} pedido(s) de PI na Aba 2.1 (ACS)",
                }
            )
        qtd_pubs_acs = RegAcsPublicacao.objects.filter(competencia_mensal=comp).count()
        if qtd_pubs_acs > 0:
            candidatos.append(
                {
                    "tipo_alvo": "KPI_PE-09",
                    "titulo": "PE-09 · Publicações em periódicos (Físico)",
                    "categoria": "Físico",
                    "alvo": "KPI",
                    "pilar_codigo": "PDI",
                    "campo": "realizado",
                    "kpi_codigo": "PE-09",
                    "tipo": "QTD",
                    "unidade": "publicações",
                    "incremento": Decimal(qtd_pubs_acs),
                    "qtd_registros_origem": qtd_pubs_acs,
                    "detalhe_origem": f"{qtd_pubs_acs} publicação(ões) na Aba 2.2 (ACS)",
                }
            )

    return candidatos


def calcular_sugestoes_competencia(
    comp: CompetenciaMensalPilar,
    acompanhamento: Optional[Acompanhamento] = None,
) -> Dict[str, Any]:
    """Calcula sugestões transparentes de atualização da Base Operacional para uma competência semestral."""
    acomp = acompanhamento_vigente(acompanhamento)
    base = BaseOperacional.objects.filter(acompanhamento=acomp).first() if acomp else None
    oficial = ler_estado_operacional(acomp) if base else None

    existentes_map: Dict[str, IntegracaoSemestralOperacional] = {}
    if acomp is not None:
        for reg in IntegracaoSemestralOperacional.objects.filter(
            competencia_mensal=comp,
            acompanhamento=acomp,
            status_execucao="APLICADA",
        ).select_related("lancamento_operacional", "indicador_operacional", "executado_por"):
            existentes_map[reg.tipo_alvo] = reg

    candidatos = _coletar_candidatos_competencia(comp)
    sugestoes: List[Dict[str, Any]] = []
    total_pendentes = 0
    total_aplicadas = 0

    for cand in candidatos:
        disponivel = True
        motivo_indisponivel = ""
        valor_vigente: Optional[Decimal] = None

        if acomp is None or base is None or oficial is None:
            disponivel = False
            motivo_indisponivel = "Confirme a Base Operacional antes de integrar resultados aos Dashboards."
        elif comp.competencia < base.competencia_corte:
            disponivel = False
            motivo_indisponivel = (
                f"Competência {comp.competencia_mm_aaaa} é anterior ao corte da Base Operacional "
                f"({base.competencia_corte.strftime('%m/%Y')}). Concilie a base para habilitar."
            )
        elif cand["alvo"] == "FONTE":
            valor_vigente = oficial.total(cand["pilar_codigo"], cand["campo"])
            if valor_vigente is None:
                disponivel = False
                motivo_indisponivel = (
                    f"Sem saldo consolidado (TAB. 9) para {cand['pilar_codigo']} ({cand['campo']}) na Base Operacional."
                )
        else:
            chave_kpi = f"kpi:{cand['kpi_codigo']}"
            if chave_kpi not in base.snapshot.get("alvos", {}):
                disponivel = False
                motivo_indisponivel = (
                    f"Indicador {cand['kpi_codigo']} ainda não está no snapshot da Base Operacional. "
                    f"Execute 'Conciliar base' para incorporá-lo."
                )
                kpi_obj = KpiAcompanhamento.objects.filter(
                    acompanhamento=acomp, codigo=cand["kpi_codigo"]
                ).first()
                valor_vigente = kpi_obj.acumulado if kpi_obj else None
            else:
                valor_vigente = oficial.valor(chave_kpi)
                if valor_vigente is None:
                    valor_vigente = ZERO

        novo_sugerido = (
            (valor_vigente + cand["incremento"]) if valor_vigente is not None else cand["incremento"]
        )
        if cand["tipo"] == "MON":
            novo_sugerido = novo_sugerido.quantize(Decimal("0.01"))
        else:
            novo_sugerido = novo_sugerido.quantize(Decimal("1"))

        integracao_existente = existentes_map.get(cand["tipo_alvo"])
        ja_integrado = integracao_existente is not None
        if ja_integrado:
            total_aplicadas += 1
        elif disponivel:
            total_pendentes += 1

        valor_input = f"{novo_sugerido:.2f}" if cand["tipo"] == "MON" else str(int(novo_sugerido))
        sugestoes.append(
            {
                **cand,
                "valor_vigente": valor_vigente,
                "valor_vigente_fmt": formatar_valor_integracao(valor_vigente, cand["tipo"], cand["unidade"]),
                "incremento_fmt": formatar_valor_integracao(cand["incremento"], cand["tipo"], cand["unidade"]),
                "novo_total_sugerido": novo_sugerido,
                "novo_total_sugerido_fmt": formatar_valor_integracao(novo_sugerido, cand["tipo"], cand["unidade"]),
                "valor_input": valor_input,
                "disponivel": disponivel,
                "motivo_indisponivel": motivo_indisponivel,
                "ja_integrado": ja_integrado,
                "integracao": integracao_existente,
            }
        )

    return {
        "acompanhamento": acomp,
        "base_operacional": base,
        "sugestoes": sugestoes,
        "total_pendentes": total_pendentes,
        "total_aplicadas": total_aplicadas,
    }


@transaction.atomic
def aplicar_sugestao_operacional(
    comp: CompetenciaMensalPilar,
    tipo_alvo: str,
    usuario,
    valor_alvo_final: Any = None,
    modo: str = "PROPOSTA",
    justificativa: str = "",
    acompanhamento: Optional[Acompanhamento] = None,
    reaplicar: bool = False,
) -> IntegracaoSemestralOperacional:
    """Converte uma sugestão de competência semestral aprovada em LancamentoOperacional auditado."""
    if not eh_gestor(usuario):
        raise PermissionDenied("Apenas Master/Admin pode integrar dados semestrais à Base Operacional.")
    if comp.status_aprovacao != "APROVADO":
        raise ValidationError(
            "Apenas competências semestrais aprovadas podem gerar atualização na Base Operacional."
        )
    if modo not in ("PROPOSTA", "DIRETO"):
        raise ValidationError("Modo de integração inválido. Use 'PROPOSTA' ou 'DIRETO'.")

    acomp = acompanhamento_vigente(acompanhamento)
    if acomp is None:
        raise ValidationError("Nenhum acompanhamento financeiro/físico importado para receber a integração.")
    base = BaseOperacional.objects.select_for_update().filter(acompanhamento=acomp).first()
    if base is None:
        raise ValidationError("Confirme a Base Operacional antes de integrar dados do Semestral.")
    if comp.competencia < base.competencia_corte:
        raise ValidationError(
            f"A competência {comp.competencia_mm_aaaa} é anterior à data de corte da Base Operacional "
            f"({base.competencia_corte.strftime('%m/%Y')}). Concilie a base antes de integrar."
        )

    pacote = calcular_sugestoes_competencia(comp, acompanhamento=acomp)
    sugestao = next((s for s in pacote["sugestoes"] if s["tipo_alvo"] == tipo_alvo), None)
    if sugestao is None:
        raise ValidationError(f"Nenhuma sugestão aplicável encontrada para '{tipo_alvo}' nesta competência.")
    if not sugestao["disponivel"]:
        raise ValidationError(sugestao["motivo_indisponivel"] or "Alvo indisponível na Base Operacional.")

    anterior_integracao = IntegracaoSemestralOperacional.objects.select_for_update().filter(
        competencia_mensal=comp,
        acompanhamento=acomp,
        tipo_alvo=tipo_alvo,
        status_execucao="APLICADA",
    ).first()
    if anterior_integracao is not None:
        if not reaplicar:
            raise ValidationError(
                f"Esta sugestão ({tipo_alvo}) já foi integrada em "
                f"{anterior_integracao.executado_em.strftime('%d/%m/%Y %H:%M')}. "
                f"Para evitar dupla contagem, a integração é idempotente."
            )
        anterior_integracao.status_execucao = "SUPERADA"
        anterior_integracao.save(update_fields=["status_execucao"])

    periodo = Periodo.objects.filter(competencia=comp.competencia).first()
    if periodo is None:
        periodo = Periodo.objects.create(competencia=comp.competencia, status="PLANEJADO")
        abrir_periodo(periodo, usuario)
    elif not periodo.permite_edicao:
        raise ValidationError(
            f"O período mensal {periodo.rotulo} está com status '{periodo.get_status_display()}' "
            f"e não permite novos lançamentos. Reabra o período antes de integrar."
        )

    if sugestao["alvo"] == "FONTE":
        pilar = Pilar.objects.get(codigo=sugestao["pilar_codigo"])
        indicador = _garantir_indicador_fonte_semestral(base, pilar, sugestao["campo"], usuario)
        # Re-lê o estado após possível criação da carteira de consolidação (versão da base atualizada)
        invalidar_cache_operacional()
        oficial_atual = ler_estado_operacional(acomp)
        valor_vigente_dashboard = oficial_atual.total(pilar.codigo, sugestao["campo"])
        valor_carteira_atual = op.valor_atual(indicador, periodo.competencia) or ZERO

        if valor_alvo_final not in (None, ""):
            novo_total_dashboard = parse_decimal_integracao(valor_alvo_final, "MON")
        else:
            novo_total_dashboard = (valor_vigente_dashboard + sugestao["incremento"]).quantize(Decimal("0.01"))

        delta_aplicado = novo_total_dashboard - valor_vigente_dashboard
        novo_valor_indicador = (valor_carteira_atual + delta_aplicado).quantize(Decimal("0.01"))
        if novo_valor_indicador < ZERO:
            raise ValidationError(
                "O novo total informado é inferior ao saldo histórico da planilha oficial e geraria "
                "valor negativo na carteira de consolidação semestral. Use 'Conciliar base' para reduzir o saldo histórico."
            )
        bruto_operacional = f"{novo_valor_indicador:.2f}"
    else:
        chave_kpi = f"kpi:{sugestao['kpi_codigo']}"
        indicador = IndicadorOperacional.objects.filter(
            acompanhamento=acomp, chave=chave_kpi, ativo=True
        ).first()
        if indicador is None or chave_kpi not in base.snapshot.get("alvos", {}):
            raise ValidationError(
                f"Indicador {sugestao['kpi_codigo']} não está disponível na Base Operacional. "
                f"Execute 'Conciliar base' antes de integrar."
            )
        valor_vigente_dashboard = op.valor_atual(indicador, periodo.competencia) or ZERO
        if valor_alvo_final not in (None, ""):
            novo_total_dashboard = parse_decimal_integracao(valor_alvo_final, "QTD")
        else:
            novo_total_dashboard = (valor_vigente_dashboard + sugestao["incremento"]).quantize(Decimal("1"))
        bruto_operacional = str(int(novo_total_dashboard))

    justificativa_limpa = (justificativa or "").strip()
    nota_origem = (
        f"[Integração Semestral · {comp.configuracao_pilar.codigo} {comp.competencia_mm_aaaa}] "
        f"{sugestao['detalhe_origem']} (+{sugestao['incremento_fmt']})."
    )
    if anterior_integracao is not None:
        nota_origem += f" Substitui integração anterior #{anterior_integracao.pk}."
    comentario_final = f"{nota_origem} {justificativa_limpa}".strip()

    lancamento = op.salvar(
        indicador,
        periodo,
        usuario,
        bruto=bruto_operacional,
        comentario=comentario_final,
        enviar=(modo == "PROPOSTA"),
        direto=(modo == "DIRETO"),
    )
    lancamento.origem = "Integração Semestral (Direto)" if modo == "DIRETO" else "Integração Semestral"
    lancamento.save(update_fields=["origem"])

    integracao = IntegracaoSemestralOperacional.objects.create(
        competencia_mensal=comp,
        acompanhamento=acomp,
        indicador_operacional=indicador,
        lancamento_operacional=lancamento,
        tipo_alvo=tipo_alvo,
        incremento_calculado=sugestao["incremento"],
        valor_vigente_anterior=valor_vigente_dashboard,
        valor_proposto=novo_total_dashboard,
        modo=modo,
        status_execucao="APLICADA",
        justificativa=comentario_final,
        executado_por=usuario,
    )

    registrar_auditoria(
        usuario=usuario,
        acao="SEMESTRAL_INTEGRAR_BASE_OPERACIONAL",
        entidade="IntegracaoSemestralOperacional",
        registro_id=integracao.pk,
        campo=tipo_alvo,
        valor_anterior=str(valor_vigente_dashboard),
        valor_novo=str(novo_total_dashboard),
        justificativa=(
            f"{comentario_final} | Competência #{comp.pk} -> Lançamento {lancamento.pk} "
            f"(modo={modo}, status={lancamento.status})."
        ),
        origem="Integração Semestral",
    )
    invalidar_cache_operacional()
    return integracao


# ---------------------------------------------------------------------------
# FASE 3 — SEMÁFORO DE COERÊNCIA (FINANCEIRO_GERAL / BASE vs SEMESTRAL v3.1)
# ---------------------------------------------------------------------------


def _resumo_financeiro_base(acomp: Acompanhamento, base: Optional[BaseOperacional], pilar_codigo: str, campo: str) -> Optional[Decimal]:
    if base is not None:
        oficial = ler_estado_operacional(acomp)
        if oficial is not None:
            val = oficial.total(pilar_codigo, campo)
            if val is not None:
                return val
    resumo = ResumoFinanceiro.objects.filter(
        acompanhamento=acomp, origem="TAB. 9", pilar__codigo=pilar_codigo, ano__isnull=True
    ).first()
    if resumo is None:
        return None
    return getattr(resumo, campo, None)


def _linha_coerencia(
    codigo: str,
    titulo: str,
    tipo: str,
    unidade: str,
    valor_base: Optional[Decimal],
    valor_sem_aprovado: Decimal,
    valor_sem_total: Decimal,
    detalhe: str,
    acao_url: str = "",
) -> Dict[str, Any]:
    if valor_sem_total == ZERO:
        status = "SEM_DADOS"
        badge_variant = "neutral"
        status_label = "Sem registros no ciclo"
        diferenca = None
    elif valor_base is None:
        status = "DIVERGENTE"
        badge_variant = "orange"
        status_label = "Sem base financeira"
        diferenca = None
    else:
        diferenca = valor_base - valor_sem_aprovado
        tolerancia = TOLERANCIA_MONETARIA if tipo == "MON" else ZERO
        if abs(diferenca) <= tolerancia:
            status = "ALINHADO"
            badge_variant = "green"
            status_label = "Alinhado"
        else:
            status = "DIVERGENTE"
            badge_variant = "orange"
            sinal = "+" if diferenca > ZERO else "-"
            status_label = f"Diferença ({sinal}{formatar_valor_integracao(abs(diferenca), tipo, unidade)})"

    return {
        "codigo": codigo,
        "titulo": titulo,
        "tipo": tipo,
        "unidade": unidade,
        "valor_base": valor_base,
        "valor_base_fmt": formatar_valor_integracao(valor_base, tipo, unidade),
        "valor_semestral_aprovado": valor_sem_aprovado,
        "valor_semestral_aprovado_fmt": formatar_valor_integracao(valor_sem_aprovado, tipo, unidade),
        "valor_semestral_total": valor_sem_total,
        "valor_semestral_total_fmt": formatar_valor_integracao(valor_sem_total, tipo, unidade),
        "diferenca": diferenca,
        "diferenca_fmt": (
            ("+" if diferenca > ZERO else "-" if diferenca < ZERO else "")
            + formatar_valor_integracao(abs(diferenca), tipo, unidade)
            if diferenca is not None
            else "—"
        ),
        "status": status,
        "badge_variant": badge_variant,
        "status_label": status_label,
        "detalhe": detalhe,
        "acao_url": acao_url,
    }


def calcular_semaforo_coerencia(
    acompanhamento: Optional[Acompanhamento] = None,
    ciclo: Optional[CicloSemestral] = None,
) -> Dict[str, Any]:
    """Compara lado a lado Base Operacional / FINANCEIRO_GERAL vs Prestação Semestral v3.1."""
    acomp = acompanhamento_vigente(acompanhamento)
    base = BaseOperacional.objects.filter(acompanhamento=acomp).first() if acomp else None
    if ciclo is None:
        ciclo = CicloSemestral.objects.order_by("-ano", "-semestre").first()

    if acomp is None or ciclo is None:
        return {
            "disponivel": False,
            "acompanhamento": acomp,
            "base_operacional": base,
            "ciclo": ciclo,
            "linhas": [],
            "resumo": {
                "alinhados": 0,
                "divergentes": 0,
                "sem_dados": 0,
                "projetos_vinculados": 0,
                "projetos_semestral_total": 0,
                "integracoes_aplicadas": 0,
            },
        }

    semestral_url = f"{reverse('core:semestral')}?ano={ciclo.ano}&semestre={ciclo.semestre}"

    # 1. Outras Fontes — Realizado (Aba 10 + Atividades AT com origem outra fonte)
    of_qs = RegFinOutrasFontes.objects.filter(competencia_mensal__ciclo=ciclo)
    of_aprov = of_qs.filter(competencia_mensal__status_aprovacao="APROVADO").aggregate(s=Sum("valor"))["s"] or ZERO
    of_total = of_qs.aggregate(s=Sum("valor"))["s"] or ZERO

    at_qs = list(
        RegAtAtividade.objects.filter(competencia_mensal__ciclo=ciclo).select_related("competencia_mensal")
    )
    of_at_aprov = sum(
        (
            r.valor_executado or ZERO
            for r in at_qs
            if _eh_origem_outra_fonte(r.origem_valor) and r.competencia_mensal.status_aprovacao == "APROVADO"
        ),
        ZERO,
    )
    of_at_total = sum(
        (r.valor_executado or ZERO for r in at_qs if _eh_origem_outra_fonte(r.origem_valor)),
        ZERO,
    )

    base_of_realizado = _resumo_financeiro_base(acomp, base, "OUTRASFONTES", "realizado")
    linha_of = _linha_coerencia(
        codigo="OUTRASFONTES_REALIZADO",
        titulo="Outras Fontes — Executado (TAB. 9 vs Aba 10)",
        tipo="MON",
        unidade="R$",
        valor_base=base_of_realizado,
        valor_sem_aprovado=(of_aprov + of_at_aprov).quantize(Decimal("0.01")),
        valor_sem_total=(of_total + of_at_total).quantize(Decimal("0.01")),
        detalhe="Base Operacional acumulada (2024–atual) vs somatório do ciclo na Aba 10 (e AT Outras Fontes).",
        acao_url=semestral_url,
    )

    # 2. AT — Captado (Aba 13 Associadas)
    assoc_qs = list(
        RegFinAssociadas.objects.filter(competencia_mensal__ciclo=ciclo).select_related("competencia_mensal")
    )
    at_cap_aprov = sum(
        (Decimal(r.contrib_total or ZERO) for r in assoc_qs if r.competencia_mensal.status_aprovacao == "APROVADO"),
        ZERO,
    )
    at_cap_total = sum((Decimal(r.contrib_total or ZERO) for r in assoc_qs), ZERO)
    base_at_captado = _resumo_financeiro_base(acomp, base, "AT", "captado")
    linha_at_cap = _linha_coerencia(
        codigo="AT_CAPTADO",
        titulo="Associação Tecnológica — Captado (TAB. 9 vs Aba 13)",
        tipo="MON",
        unidade="R$",
        valor_base=base_at_captado,
        valor_sem_aprovado=at_cap_aprov.quantize(Decimal("0.01")),
        valor_sem_total=at_cap_total.quantize(Decimal("0.01")),
        detalhe="Contribuições compromissadas das empresas associadas na Aba 13 do ciclo.",
        acao_url=semestral_url,
    )

    # 3. AT — Realizado (AT · Aba 2 Atividades AT com recurso AT)
    at_real_aprov = sum(
        (
            r.valor_executado or ZERO
            for r in at_qs
            if not _eh_origem_outra_fonte(r.origem_valor) and r.competencia_mensal.status_aprovacao == "APROVADO"
        ),
        ZERO,
    )
    at_real_total = sum(
        (r.valor_executado or ZERO for r in at_qs if not _eh_origem_outra_fonte(r.origem_valor)),
        ZERO,
    )
    base_at_realizado = _resumo_financeiro_base(acomp, base, "AT", "realizado")
    linha_at_real = _linha_coerencia(
        codigo="AT_REALIZADO",
        titulo="Associação Tecnológica — Executado (TAB. 9 vs AT Aba 2)",
        tipo="MON",
        unidade="R$",
        valor_base=base_at_realizado,
        valor_sem_aprovado=at_real_aprov.quantize(Decimal("0.01")),
        valor_sem_total=at_real_total.quantize(Decimal("0.01")),
        detalhe="Atividades AT custeadas com recursos da Associação Tecnológica no ciclo.",
        acao_url=semestral_url,
    )

    linhas = [linha_of, linha_at_cap, linha_at_real]

    # 4..6. Portfólio de Projetos (TAB. 2 PDI, TAB. 4 FORMACAO, TAB. 6 STARTUPS)
    projetos_vinculados = 0
    projetos_semestral_total = 0
    for pilar_cod, (pilar_sem, _aba_slug, model_cls) in PILAR_OFICIAL_PARA_MODELO_SEMESTRAL.items():
        qtd_base = Decimal(
            ProjetoFinanceiro.objects.filter(acompanhamento=acomp, pilar__codigo=pilar_cod).count()
        )
        qs_sem = model_cls.objects.filter(competencia_mensal__ciclo=ciclo)
        qtd_sem_total = qs_sem.count()
        qtd_sem_aprov = qs_sem.filter(competencia_mensal__status_aprovacao="APROVADO").count()
        qtd_vinc = qs_sem.filter(projeto_oficial__isnull=False).count()
        projetos_vinculados += qtd_vinc
        projetos_semestral_total += qtd_sem_total

        rotulo_pilar = {
            "PDI": "Projetos PD&I (TAB. 2 vs AFCCT)",
            "FORMACAO": "Projetos Formação (TAB. 4 vs FCRH)",
            "STARTUPS": "Projetos Startups (TAB. 6 vs ACS)",
        }[pilar_cod]

        linhas.append(
            _linha_coerencia(
                codigo=f"PROJETOS_{pilar_cod}",
                titulo=rotulo_pilar,
                tipo="QTD",
                unidade="projetos",
                valor_base=qtd_base,
                valor_sem_aprovado=Decimal(qtd_sem_aprov),
                valor_sem_total=Decimal(qtd_sem_total),
                detalhe=(
                    f"{qtd_vinc} de {qtd_sem_total} registro(s) vinculados ao portfólio oficial ({pilar_sem})."
                    if qtd_sem_total
                    else f"Nenhum projeto lançado em {pilar_sem} neste ciclo."
                ),
                acao_url=semestral_url,
            )
        )

    integracoes_aplicadas = IntegracaoSemestralOperacional.objects.filter(
        competencia_mensal__ciclo=ciclo,
        acompanhamento=acomp,
        status_execucao="APLICADA",
    ).count()

    return {
        "disponivel": True,
        "acompanhamento": acomp,
        "base_operacional": base,
        "ciclo": ciclo,
        "linhas": linhas,
        "resumo": {
            "alinhados": sum(1 for item in linhas if item["status"] == "ALINHADO"),
            "divergentes": sum(1 for item in linhas if item["status"] == "DIVERGENTE"),
            "sem_dados": sum(1 for item in linhas if item["status"] == "SEM_DADOS"),
            "projetos_vinculados": projetos_vinculados,
            "projetos_semestral_total": projetos_semestral_total,
            "integracoes_aplicadas": integracoes_aplicadas,
        },
    }
