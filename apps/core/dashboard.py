"""Agregações de apresentação do dashboard executivo (R2).

Funções puras: recebem as `linhas` já calculadas pela view (sem novas queries).
"""
import json
from decimal import Decimal

from django.urls import reverse

NIVEL_OK = "ok"
NIVEL_ATENCAO = "atencao"
NIVEL_CRITICO = "critico"
NIVEL_NEUTRO = "neutro"


def _nivel(percentual):
    if percentual is None:
        return NIVEL_NEUTRO
    if percentual >= 100:
        return NIVEL_OK
    if percentual >= 50:
        return NIVEL_ATENCAO
    return NIVEL_CRITICO


def _formatar_percentual(percentual):
    if percentual is None:
        return "—"
    return f"{percentual:.0f}%"


def kpi_por_pilar(linhas):
    """KPIs agregados por pilar: média de execução e contagens."""
    kpis = []
    for linha in linhas:
        itens = linha["itens"]
        percentuais = [i["percentual"] for i in itens if i["percentual"] is not None]
        com_meta = sum(1 for i in itens if i.get("meta") is not None)
        atingidos = sum(1 for i in itens if i["percentual"] is not None and i["percentual"] >= 100)
        pendentes = sum(1 for i in itens if i["realizado"] is None and i.get("meta") is not None)
        percentual = None
        if percentuais:
            percentual = sum(percentuais, Decimal("0")) / len(percentuais)
        kpis.append(
            {
                "pilar": linha["pilar"],
                "percentual": percentual,
                "percentual_fmt": _formatar_percentual(percentual),
                "nivel": _nivel(percentual),
                "barra_pct": float(min(percentual or 0, 100)),
                "com_meta": com_meta,
                "atingidos": atingidos,
                "pendentes": pendentes,
                "total": len(itens),
            }
        )
    return kpis


def heatmap_por_pilar(linhas):
    """Células de status por indicador (verde/amarelo/vermelho/cinza)."""
    grupos = []
    for linha in linhas:
        celulas = []
        for item in linha["itens"]:
            indicador = item["indicador"]
            nivel = _nivel(item["percentual"])
            meta = item.get("meta")
            realizado = item.get("realizado")
            titulo = f"{indicador.nome}: "
            if item["percentual"] is None:
                titulo += "sem valor/meta"
            else:
                titulo += f"{realizado} de {meta} ({item['percentual']:.0f}%)"
            celulas.append({"codigo": indicador.codigo, "titulo": titulo, "nivel": nivel})
        ok = sum(1 for c in celulas if c["nivel"] == NIVEL_OK)
        grupos.append(
            {
                "pilar": linha["pilar"],
                "celulas": celulas,
                "resumo": f"{ok}/{len(celulas)} indicadores na meta",
            }
        )
    return grupos


def avisos_do_dashboard(periodo, pendencias, status_counts, total_pendencias):
    """Avisos críticos: pendências de aprovação e pilares com lacunas."""
    avisos = []
    if not periodo:
        return avisos
    enviados = (status_counts.get("ENVIADO") or {}).get("quantidade", 0)
    if enviados:
        avisos.append(
            {
                "texto": f"{enviados} lançamento{'s' if enviados != 1 else ''} aguardando aprovação em {periodo.rotulo}.",
                "acao": "Revisar",
                "url": reverse("entries:aprovacao", args=[periodo.pk]),
            }
        )
    for pendencia in pendencias:
        faltantes = pendencia["faltantes"]
        if faltantes:
            avisos.append(
                {
                    "texto": (
                        f"{pendencia['pilar'].nome}: {len(faltantes)} indicador"
                        f"{'es' if len(faltantes) != 1 else ''} sem lançamento aprovado."
                    ),
                    "acao": "Abrir pilar",
                    "url": reverse("core:pilar", args=[pendencia["pilar"].pk]),
                }
            )
    if periodo.status in ("ABERTO", "REABERTO") and not total_pendencias:
        avisos.append(
            {
                "texto": f"Período {periodo.rotulo} aberto sem pendências bloqueantes.",
                "acao": "Fechar",
                "url": reverse("core:dashboard"),
            }
        )
    return avisos


def graficos_dados(chart_mensal, chart_financeiro):
    """Serializa os dados dos gráficos como JSON seguro."""
    mensal = [
        {"rotulo": p["rotulo"], "captado": float(p["captado"] or 0), "executado": float(p["executado"] or 0)}
        for p in chart_mensal
    ]
    financeiro = [
        {
            "nome": p["nome"],
            "captado": float(p["captado"] or 0),
            "executado": float(p["executado"] or 0),
        }
        for p in chart_financeiro
    ]
    return json.dumps(mensal), json.dumps(financeiro)
