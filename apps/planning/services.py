"""Agregações do painel anual (L2) — funções puras sobre `PlanoAnual`.

Todo cálculo de negócio vive aqui (nunca no template). `painel()` lê as linhas
em 2 queries e computa cards, gráficos, tabela, consolidado e chips em memória.
"""
from decimal import Decimal, ROUND_HALF_UP

ANOS = [2024, 2025, 2026, 2027]
BASE_FINANCEIRO = "financeiro"
BASE_FISICO = "fisico"
BASES = (BASE_FINANCEIRO, BASE_FISICO)
# Códigos curtos da URL (?base=fin|fis) → valor armazenado.
BASES_URL = {"fin": BASE_FINANCEIRO, "fis": BASE_FISICO}

PILARES_PPI = ("PDI", "FORMACAO", "STARTUPS", "INFRA")

ROTULOS_PAINEL = {
    "PDI": "PDI",
    "FORMACAO": "Formação FCRH",
    "STARTUPS": "ACS",
    "INFRA": "Infraestrutura",
    "AT": "Associação Tecnológica (AT)",
    "OUTRASFONTES": "Outras fontes",
}

FAIXA_OK = "ok"
FAIXA_PARCIAL = "parcial"
FAIXA_CRITICA = "critica"
FAIXA_NEUTRA = "neutra"

ROTULO_FAROL = {
    FAIXA_OK: "Meta atingida",
    FAIXA_PARCIAL: "Execução parcial",
    FAIXA_CRITICA: "Execução crítica",
    FAIXA_NEUTRA: "Sem meta",
}


def percentual(executado, previsto):
    """% executado (RN-018). None quando não há denominador (RN-020)."""
    previsto = Decimal(previsto or 0)
    if previsto <= 0:
        return None
    return (Decimal(executado or 0) / previsto) * 100


def faixa(p):
    """Faixa do farol (RN-019); None ⇒ neutra."""
    if p is None:
        return FAIXA_NEUTRA
    if p >= 90:
        return FAIXA_OK
    if p >= 50:
        return FAIXA_PARCIAL
    return FAIXA_CRITICA


def pct_inteiro(executado, previsto):
    """Percentual inteiro (meio para cima) ou None sem denominador."""
    p = percentual(executado, previsto)
    if p is None:
        return None
    return int(p.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def rotulo_previsto(codigo_pilar):
    """Projetado nos pilares PPI; captado em AT e Outras fontes (RN-018)."""
    return "Projetado" if codigo_pilar in PILARES_PPI else "Captado"


def rotulo_periodo(ano):
    if ano is None:
        return "Acumulado 2024 a 2027"
    return f"Ano {ANOS.index(ano) + 1}: {ano}"


def _validar(ano, base):
    base = BASES_URL.get(base, base)
    if base not in BASES:
        raise ValueError(f"base inválida: {base!r}")
    if ano is not None and ano not in ANOS:
        raise ValueError(f"ano inválido: {ano!r}")
    return base


def painel(ano, base):
    """DTO completo do painel para (ano|None, base). `ano=None` = todos os anos."""
    from .models import PlanoAnual

    base = _validar(ano, base)
    linhas = list(
        PlanoAnual.objects.filter(base=base).select_related("pilar").order_by("pilar__ordem")
    )
    por_pilar = {}
    for linha in linhas:
        por_pilar.setdefault(linha.pilar.codigo, {"pilar": linha.pilar, "valores": {}})
        por_pilar[linha.pilar.codigo]["valores"][linha.ano] = (
            Decimal(linha.previsto), Decimal(linha.executado),
        )
    for codigo in (*PILARES_PPI, "AT", "OUTRASFONTES"):
        por_pilar.setdefault(codigo, {"pilar": None, "valores": {}})

    def serie_anos(codigo, campo):
        """4 valores anuais (sem acumulado) — base dos valores do período."""
        idx = 0 if campo == "previsto" else 1
        return [por_pilar.get(codigo, {"valores": {}})["valores"].get(a, (Decimal(0), Decimal(0)))[idx]
                for a in ANOS]

    def serie(codigo, campo):
        """5 pontos para os gráficos (4 anos + acumulado)."""
        vals = serie_anos(codigo, campo)
        return vals + [sum(vals, Decimal(0))]

    def no_periodo(vals_anos):
        return sum(vals_anos, Decimal(0)) if ano is None else vals_anos[ANOS.index(ano)]

    soma4 = lambda listas: [sum(col, Decimal(0)) for col in zip(*listas)]
    ppi_prev_anos = soma4([serie_anos(c, "previsto") for c in PILARES_PPI])
    ppi_exec_anos = soma4([serie_anos(c, "executado") for c in PILARES_PPI])
    ppi_prev, ppi_exec = ppi_prev_anos + [sum(ppi_prev_anos, Decimal(0))], ppi_exec_anos + [sum(ppi_exec_anos, Decimal(0))]
    at_prev, at_exec = serie("AT", "previsto"), serie("AT", "executado")
    ou_prev, ou_exec = serie("OUTRASFONTES", "previsto"), serie("OUTRASFONTES", "executado")

    p_ppi, p_at, p_ou = no_periodo(ppi_prev_anos), no_periodo(at_prev[:4]), no_periodo(ou_prev[:4])
    e_ppi, e_at, e_ou = no_periodo(ppi_exec_anos), no_periodo(at_exec[:4]), no_periodo(ou_exec[:4])
    p_tot, e_tot = p_ppi + p_at + p_ou, e_ppi + e_at + e_ou

    def card(chave, titulo, executado, previsto, denominador):
        pct = pct_inteiro(executado, previsto)
        return {
            "chave": chave, "titulo": titulo, "executado": executado,
            "previsto": previsto, "denominador": denominador,
            "pct": pct, "faixa": faixa(percentual(executado, previsto)),
        }

    cards = [
        card("ppi", "Recursos PPI executados", e_ppi, p_ppi, "projetados"),
        card("at", "Captação AT executada", e_at, p_at, "captados"),
        card("outras", "Outras fontes executadas", e_ou, p_ou, "captados"),
        card("total", "Execução consolidada", e_tot, p_tot, "previstos"),
    ]

    def bloco_grafico(chave, serie_p, serie_e, nome_p, nome_e):
        exe, prev = no_periodo(serie_e[:4]), no_periodo(serie_p[:4])
        pct = pct_inteiro(exe, prev)
        return {
            "chave": chave, "serie_previsto": serie_p, "serie_executado": serie_e,
            "nome_previsto": nome_p, "nome_executado": nome_e,
            "rodape_pct": pct,
            "rodape_faixa": faixa(percentual(exe, prev)),
        }

    graficos = {
        "ppi": bloco_grafico("ppi", ppi_prev, ppi_exec, "Projetado", "Executado"),
        "at": bloco_grafico("at", at_prev, at_exec, "Captado", "Executado"),
        "outras": bloco_grafico("outras", ou_prev, ou_exec, "Captado", "Executado"),
    }

    grupos = []
    linhas_ppi = []
    for codigo in PILARES_PPI:
        prev = no_periodo(serie_anos(codigo, "previsto"))
        exe = no_periodo(serie_anos(codigo, "executado"))
        pct = pct_inteiro(exe, prev)
        linhas_ppi.append(_linha_tabela(por_pilar[codigo]["pilar"], codigo, prev, exe, pct))
    grupos.append({"titulo": "4.1 PPI: projetado x executado", "linhas": linhas_ppi + [
        _linha_tabela(None, "Total PPI", p_ppi, e_ppi, pct_inteiro(e_ppi, p_ppi), total=True),
    ]})
    grupos.append({"titulo": "4.2 Captação de recursos: captado x executado", "linhas": [
        _linha_tabela(por_pilar["AT"]["pilar"], "AT", p_at, e_at, pct_inteiro(e_at, p_at)),
    ]})
    grupos.append({"titulo": "4.3 Outras fontes: captado x executado", "linhas": [
        _linha_tabela(por_pilar["OUTRASFONTES"]["pilar"], "OUTRASFONTES", p_ou, e_ou, pct_inteiro(e_ou, p_ou)),
    ]})

    consolidado = {
        "anos": list(ANOS),
        "series": [
            {"nome": "PPI executado", "valores": ppi_exec[:4]},
            {"nome": "Captação AT executada", "valores": at_exec[:4]},
            {"nome": "Outras fontes executadas", "valores": ou_exec[:4]},
        ],
        "total_acumulado": e_ppi + e_at + e_ou if ano is None else None,
    }

    return {
        "ano": ano, "base": base,
        "unidade": "R$ mi" if base == BASE_FINANCEIRO else "metas",
        "rotulo_periodo": rotulo_periodo(ano),
        "cards": cards, "graficos": graficos,
        "tabela": {"grupos": grupos}, "consolidado": consolidado,
    }


def _linha_tabela(pilar, codigo, previsto, executado, pct, total=False):
    return {
        "pilar": pilar,
        "rotulo": ROTULOS_PAINEL.get(codigo, getattr(pilar, "nome", codigo) if pilar else codigo),
        "previsto": previsto, "executado": executado,
        "saldo": previsto - executado, "pct": pct,
        "faixa": faixa(percentual(executado, previsto)),
        "grupo": False, "total": total or codigo == "Total PPI",
    }
