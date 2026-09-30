"""Geometria dos gráficos do painel anual (L2) — delega ao genérico (L20).

Os templates emitem o SVG a partir destes dicionários; nenhuma matemática
vive no template. O eixo anual mostra somente os quatro anos do programa;
totais acumulados ficam nos cards/tabelas, nunca como um quinto ano.
"""
from apps.core.charts import ALTURA_MINIMA, OPACIDADE_DIM, _num, geometria_barras

LARGURA_FONTE, ALTURA_FONTE = 430, 268
PAD_FONTE = {"esq": 8, "dir": 8, "topo": 26, "base": 46}
LARGURA_BARRA_MAX, ESPACO_BARRAS = 26, 5

LARGURA_CONSOL, ALTURA_CONSOL = 1100, 280
PAD_CONSOL = {"esq": 52, "dir": 20, "topo": 26, "base": 50}
LARGURA_BARRA_CONSOL, ESPACO_CONSOL = 44, 10

EIXOS_FONTE = (("Ano 1", "2024"), ("Ano 2", "2025"), ("Ano 3", "2026"),
               ("Ano 4", "2027"))


def geometria_fonte(serie_previsto, serie_executado, destaque):
    """Barras agrupadas (previsto × executado) nos quatro anos do programa.

    `destaque`: índice 0..3 da categoria selecionada ou None (todos os anos).
    """
    return geometria_barras(
        list(EIXOS_FONTE), serie_previsto, serie_executado, destaque,
        largura=LARGURA_FONTE, altura=ALTURA_FONTE, pad=PAD_FONTE,
        larg_barra_max=LARGURA_BARRA_MAX, espaco=ESPACO_BARRAS,
    )


def geometria_consolidado(series, destaque):
    """3 séries por ano (PPI/AT/Outras executados). `destaque`: 0..3 ou None."""
    nomes = list(series.keys())
    valores = {n: list(series[n]) for n in nomes}
    vals = {n: [_num(v) for v in valores[n]] for n in nomes}
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
            valor = valores[nome][i]
            v = vals[nome][i]
            h = max(ALTURA_MINIMA, v / teto * plot_h) if v > 0 else ALTURA_MINIMA
            x_barra = x0 + j * (LARGURA_BARRA_CONSOL + ESPACO_CONSOL)
            y_barra = base_y - h
            barras.append({"serie": nome, "valor": valor,
                           "disponivel": valor is not None,
                           "x": round(x_barra, 2),
                           "y": round(y_barra, 2),
                           "cx": round(x_barra + LARGURA_BARRA_CONSOL / 2, 2),
                           "ry": round(y_barra - 4, 2),
                           "w": LARGURA_BARRA_CONSOL, "h": round(h, 2)})
        sel = destaque is not None and i == destaque
        grupos.append({
            "eixo": f"Ano {i + 1}: {2024 + i}",
            "categoria": f"Ano {i + 1} {2024 + i}",
            "cx_eixo": round(centro, 2),
            "barras": barras,
            "fundo": sel,
            "x0": round(centro - larg_grupo / 2 + 6, 2),
            "largura_fundo": round(larg_grupo - 12, 2),
            "opacidade": 1 if (destaque is None or sel) else OPACIDADE_DIM,
        })
    passo = teto / 4
    linhas_grade = [{"valor": round(passo * s, 2), "y": round(base_y - passo * s / teto * plot_h, 2),
                    "lx": PAD_CONSOL["esq"] - 8 - 4,
                    "ly": round(base_y - passo * s / teto * plot_h + 4, 2)}
                   for s in range(5)]
    return {
        "largura": LARGURA_CONSOL, "altura": ALTURA_CONSOL, "base_y": round(base_y, 2),
        "eixo_y": round(base_y + 22, 2), "grade_x": PAD_CONSOL["esq"] - 8,
        "grade_x2": LARGURA_CONSOL - PAD_CONSOL["dir"],
        "topo_y": PAD_CONSOL["topo"], "fundo_h": round(base_y - PAD_CONSOL["topo"], 2),
        "grupos": grupos, "linhas_grade": linhas_grade, "series": nomes,
    }
