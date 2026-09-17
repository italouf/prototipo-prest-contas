"""Geometria dos gráficos do painel anual (L2) — funções puras.

Os templates emitem o SVG a partir destes dicionários; nenhuma matemática
vive no template. Proporções espelham o mockup (5 categorias com divisor
antes do acumulado; consolidado com 3 séries por ano).
"""
LARGURA_FONTE, ALTURA_FONTE = 430, 268
PAD_FONTE = {"esq": 8, "dir": 8, "topo": 26, "base": 46}
LARGURA_BARRA_MAX, ESPACO_BARRAS = 26, 5
ALTURA_MINIMA = 1.5
OPACIDADE_DIM = 0.3

LARGURA_CONSOL, ALTURA_CONSOL = 1100, 280
PAD_CONSOL = {"esq": 52, "dir": 20, "topo": 26, "base": 50}
LARGURA_BARRA_CONSOL, ESPACO_CONSOL = 44, 10


def _num(v):
    return float(v or 0)


def geometria_fonte(serie_previsto, serie_executado, destaque):
    """Barras agrupadas (previsto × executado) em 5 categorias.

    `destaque`: índice 0..4 da categoria selecionada ou None (todos os anos).
    """
    vals_a = [_num(v) for v in serie_previsto]
    vals_b = [_num(v) for v in serie_executado]
    teto = max([1, *vals_a, *vals_b]) * 1.18
    plot_w = LARGURA_FONTE - PAD_FONTE["esq"] - PAD_FONTE["dir"]
    plot_h = ALTURA_FONTE - PAD_FONTE["topo"] - PAD_FONTE["base"]
    base_y = PAD_FONTE["topo"] + plot_h
    larg_grupo = plot_w / 5
    larg_barra = min(LARGURA_BARRA_MAX, larg_grupo * 0.3)

    def barra(x_centro, valor):
        h = max(ALTURA_MINIMA, valor / teto * plot_h) if valor > 0 else ALTURA_MINIMA
        return {"x": round(x_centro, 2), "y": round(base_y - h, 2),
                "w": round(larg_barra, 2), "h": round(h, 2), "valor": valor}

    eixos = [("Ano 1", "2024"), ("Ano 2", "2025"), ("Ano 3", "2026"),
             ("Ano 4", "2027"), ("Todos os anos", "2024 a 2027")]
    grupos = []
    for i in range(5):
        centro = PAD_FONTE["esq"] + larg_grupo * (i + 0.5)
        sel = destaque is not None and i == destaque
        grupos.append({
            "eixo": eixos[i],
            "a": barra(centro - larg_barra / 2 - ESPACO_BARRAS / 2, vals_a[i]),
            "b": barra(centro + larg_barra / 2 + ESPACO_BARRAS / 2, vals_b[i]),
            "opacidade": 1 if (destaque is None or sel) else OPACIDADE_DIM,
            "destaque": sel,
            "divisor": i == 4,
            "divisor_x": round(PAD_FONTE["esq"] + larg_grupo * 4, 2),
        })
    return {
        "largura": LARGURA_FONTE, "altura": ALTURA_FONTE, "base_y": round(base_y, 2),
        "topo_y": PAD_FONTE["topo"], "grupos": grupos,
    }


def geometria_consolidado(series, destaque):
    """3 séries por ano (PPI/AT/Outras executados). `destaque`: 0..3 ou None."""
    nomes = list(series.keys())
    vals = {n: [_num(v) for v in series[n]] for n in nomes}
    teto = max([1, *[v for serie in vals.values() for v in serie]]) * 1.12
    plot_w = LARGURA_CONSOL - PAD_CONSOL["esq"] - PAD_CONSOL["dir"]
    plot_h = ALTURA_CONSOL - PAD_CONSOL["topo"] - PAD_CONSOL["base"]
    base_y = PAD_CONSOL["topo"] + plot_h
    larg_grupo = plot_w / 4
    bloco = LARGURA_BARRA_CONSOL * 3 + ESPACO_CONSOL * 2

    grupos = []
    for i in range(4):
        centro = PAD_CONSOL["esq"] + larg_grupo * (i + 0.5)
        x0 = centro - bloco / 2
        barras = []
        for j, nome in enumerate(nomes):
            v = vals[nome][i]
            h = max(ALTURA_MINIMA, v / teto * plot_h) if v > 0 else ALTURA_MINIMA
            barras.append({"serie": nome, "valor": v,
                           "x": round(x0 + j * (LARGURA_BARRA_CONSOL + ESPACO_CONSOL), 2),
                           "y": round(base_y - h, 2),
                           "w": LARGURA_BARRA_CONSOL, "h": round(h, 2)})
        sel = destaque is not None and i == destaque
        grupos.append({
            "eixo": f"Ano {i + 1}: {2024 + i}",
            "barras": barras,
            "fundo": sel,
            "x0": round(centro - larg_grupo / 2 + 6, 2),
            "largura_fundo": round(larg_grupo - 12, 2),
            "opacidade": 1 if (destaque is None or sel) else OPACIDADE_DIM,
        })
    passo = teto / 4
    linhas_grade = [{"valor": round(passo * s, 2), "y": round(base_y - passo * s / teto * plot_h, 2)}
                   for s in range(5)]
    return {
        "largura": LARGURA_CONSOL, "altura": ALTURA_CONSOL, "base_y": round(base_y, 2),
        "grupos": grupos, "linhas_grade": linhas_grade, "series": nomes,
    }
