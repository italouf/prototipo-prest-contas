"""Geometria SVG genérica de barras agrupadas (L20) — funções puras.

`apps/planning/charts.py` delega para cá (saída idêntica); mensal/semestral
usam direto com rótulos de mês/pilar. Templates emitem o SVG a partir destes
dicionários; nenhuma matemática vive no template. Números saem arredondados
(ponto decimal — SVG não aceita vírgula).
"""
ALTURA_MINIMA = 1.5
OPACIDADE_DIM = 0.3


def _num(v):
    return float(v or 0)


def _barra(x_esq, valor, teto, plot_h, base_y, larg_barra):
    h = max(ALTURA_MINIMA, valor / teto * plot_h) if valor > 0 else ALTURA_MINIMA
    y = base_y - h
    return {"x": round(x_esq, 2), "y": round(y, 2),
            "w": round(larg_barra, 2), "h": round(h, 2), "valor": valor,
            "cx": round(x_esq + larg_barra / 2, 2), "ry": round(y - 4, 2)}


def geometria_barras(eixos, serie_a, serie_b, destaque, *, largura, altura, pad,
                     larg_barra_max, espaco, divisor=None):
    """N grupos de 2 barras (a × b); `eixos[i] = (linha1, linha2)`.

    `destaque`: índice da categoria selecionada ou None. `divisor`: índice da
    categoria acumulada (linha tracejada à esquerda dela) ou None.
    """
    n = len(eixos)
    vals_a = [_num(v) for v in serie_a]
    vals_b = [_num(v) for v in serie_b]
    if len(vals_a) != n or len(vals_b) != n:
        raise ValueError(
            f"séries com {len(vals_a)}/{len(vals_b)} valores para {n} rótulos")
    teto = max([1, *vals_a, *vals_b]) * 1.18
    plot_w = largura - pad["esq"] - pad["dir"]
    plot_h = altura - pad["topo"] - pad["base"]
    base_y = pad["topo"] + plot_h
    larg_grupo = plot_w / n
    larg_barra = min(larg_barra_max, larg_grupo * 0.3)

    grupos = []
    for i in range(n):
        centro = pad["esq"] + larg_grupo * (i + 0.5)
        sel = destaque is not None and i == destaque
        grupos.append({
            "eixo": eixos[i],
            "cx_eixo": round(centro, 2),
            "a": _barra(centro - espaco / 2 - larg_barra, vals_a[i],
                        teto, plot_h, base_y, larg_barra),
            "b": _barra(centro + espaco / 2, vals_b[i],
                        teto, plot_h, base_y, larg_barra),
            "opacidade": 1 if (destaque is None or sel) else OPACIDADE_DIM,
            "destaque": sel,
            "divisor": divisor is not None and i == divisor,
            "divisor_x": round(pad["esq"] + larg_grupo * divisor, 2)
            if divisor is not None else 0.0,
        })
    return {
        "largura": largura, "altura": altura, "base_y": round(base_y, 2),
        "topo_y": pad["topo"], "divisor_y1": pad["topo"] - 6,
        "eixo_y1": altura - pad["base"] + 18,
        "eixo_y2": altura - pad["base"] + 31,
        "base_x1": pad["esq"], "base_x2": largura - pad["dir"],
        "grupos": grupos,
    }
