"""Painel anual alimentado pelos snapshots importados (SDD §8).

Devolve **o mesmo DTO** de `planning.services.painel()` — chaves `ano, base,
unidade, rotulo_periodo, cards, graficos, tabela, consolidado` — para que
`_panel.html`, `pilares-table.html` e os filtros de SVG continuem sem mudança.

Duas representações do mesmo dado convivem aqui (contratos diferentes de
template e de geometria):

- `tabela.grupos[*].linhas[*]` aceita `previsto/executado/saldo = None` com
  `pct = None` e `faixa = "neutra"` — `numero_curto(None)` e o template
  renderizam `—` (nunca `0%` nem farol quando não há dado);
- `graficos[*].serie_*` e `consolidado.series` são **sempre numéricos**
  (`Decimal(0)` para dado ausente), porque `contexto_painel` faz `float(v)`
  em `geometria_fonte`/`geometria_consolidado` e `None` quebraria o render.

Fontes (Ruling 9 da revisão do Task 2):

- consolidado (`ano is None`): `origem in ("TAB. 1", "TAB. 9")` com
  `ano isnull` — PPI usa `recurso_ou_meta`/`realizado`; AT e OUTRASFONTES
  usam `captado`/`realizado`. Os totais de reconciliação TAB. 3/5/8 repetem
  o realizado do pilar e **nunca** entram em soma;
- anual: `origem="TAB. 1.1"` com `ano` **preenchido** (a linha consolidada
  da TAB. 1.1 não pode virar ano) — `previsto` vem de `projetado` e
  `executado` de `realizado`;
- físico: `KpiAcompanhamento`, `meta_<ano>` × `executado_<2024|2025>`
  (`None` em 2026/2027, que só têm projeção) e `meta_total` × `acumulado`
  em `todos`. Projeções nunca entram como "executado" (SDD §8).

Valores de KPI são `Decimal(18,6)` e **nunca** são quantizados (Ruling 11);
campos monetários são `Decimal(18,2)`.

Override manual (SDD §9): `OverrideAcompanhamento` vence o valor importado **no
ano correspondente** — aplicado já na extração (`_resumos_financeiros`,
`_campos_kpi`), de modo que a grade de edição e o painel leem os mesmos
efetivos e `saldo`/`pct`/`faixa` recalculam em `_linha`. O consolidado
(TAB. 1/TAB. 9) e o acumulado do físico (`meta_total`/`acumulado`) são figuras
importadas próprias e **não** são afetados por overrides anuais.
"""
from decimal import Decimal

from apps.planning.services import (
    ANOS,
    PILARES_PPI,
    ROTULOS_PAINEL,
    faixa,
    pct_inteiro,
    percentual,
)

from .models import Acompanhamento, KpiAcompanhamento, ResumoFinanceiro
from .temporal import agregar_despesas_por_ano

# `?base=fin|fis` (curto) e o valor canônico armazenado no DTO.
BASES_CANONICAS = {
    "fin": "financeiro", "fis": "fisico",
    "financeiro": "financeiro", "fisico": "fisico",
}
BASE_FINANCEIRO = "financeiro"
BASE_FISICO = "fisico"

# Ordem canônica dos pilares nos blocos e na tabela (PDI sempre primeiro).
ORDEM_PILARES = (*PILARES_PPI, "AT", "OUTRASFONTES")

# Títulos dos blocos da tabela financeira (mesmos do painel legado).
GRUPOS_FINANCEIRO = (
    ("4.1 PPI: projetado x executado", "4.1 PPI", PILARES_PPI),
    ("4.2 Captação de recursos: captado x executado", "4.2 Captação de recursos", ("AT",)),
    ("4.3 Outras fontes: captado x executado", "4.3 Outras fontes", ("OUTRASFONTES",)),
)


# --------------------------------------------------------------- acompanhamento

def acompanhamento_padrao():
    """Acompanhamento mais recente; `None` quando nada foi importado."""
    return Acompanhamento.objects.order_by("-criado_em", "-pk").first()


def lista_acompanhamentos():
    """Acompanhamentos para o seletor (mais recente primeiro)."""
    return list(
        Acompanhamento.objects.select_related("centro").order_by("-criado_em", "-pk")
    )


# ------------------------------------------------------------------ utilitários

def _somar(valores):
    """Soma ignorando `None`; `None` quando não há **nenhum** valor.

    Agregado nunca converte dado ausente em 0 implícito (Ruling 4): se tudo
    falta, o campo fica `None` e renderiza `—`.
    """
    presentes = [v for v in valores if v is not None]
    return sum(presentes, Decimal(0)) if presentes else None


def _num(valores):
    """Versão numérica de uma série (gráficos/consolidado): `None` vira 0."""
    return [Decimal(0) if v is None else v for v in valores]


def _serie_anos(lookup):
    """4 posições para `ANOS`; `None` quando não há linha importada."""
    return [lookup(ano) for ano in ANOS]


def _linha(rotulo, previsto, executado, total=False, codigo=None, pilar=None):
    """Linha da tabela gerencial; `None` renderiza `—` (SDD §8)."""
    if previsto is None or executado is None:
        saldo = None
        pct = None
    else:
        saldo = previsto - executado
        pct = pct_inteiro(executado, previsto)
    return {
        "pilar": pilar,
        "codigo": codigo,
        "rotulo": rotulo,
        "previsto": previsto,
        "executado": executado,
        "saldo": saldo,
        "pct": pct,
        "faixa": "neutra" if pct is None else faixa(percentual(executado, previsto)),
        "grupo": False,
        "total": total,
    }


def _card(chave, titulo, executado, previsto, denominador):
    pct = None if previsto is None or executado is None else pct_inteiro(executado, previsto)
    return {
        "chave": chave,
        "titulo": titulo,
        "executado": executado,
        "previsto": previsto,
        "denominador": denominador,
        "pct": pct,
        "faixa": "neutra" if pct is None else faixa(percentual(executado, previsto)),
        "barra": min(pct, 100) if pct is not None else 0,
    }


def _bloco_grafico(chave, serie_previsto, serie_executado, nome_previsto,
                   nome_executado, previsto_periodo, executado_periodo):
    pct = (
        None if previsto_periodo is None or executado_periodo is None
        else pct_inteiro(executado_periodo, previsto_periodo)
    )
    return {
        "chave": chave,
        "serie_previsto": _num(serie_previsto),
        "serie_executado": _num(serie_executado),
        "nome_previsto": nome_previsto,
        "nome_executado": nome_executado,
        "rodape_pct": pct,
        "rodape_faixa": (
            "neutra" if pct is None
            else faixa(percentual(executado_periodo, previsto_periodo))
        ),
    }


def _rotulo_periodo(ano):
    if ano is None:
        return "Acumulado 2024 a 2027"
    return f"Ano {ANOS.index(ano) + 1}: {ano}"


def _dto(ano, base, cards, graficos, grupos, series, total_acumulado):
    return {
        "ano": ano,
        "base": base,
        "unidade": "R$ mi" if base == BASE_FINANCEIRO else "metas",
        "rotulo_periodo": _rotulo_periodo(ano),
        "cards": cards,
        "graficos": graficos,
        "tabela": {"grupos": grupos},
        "consolidado": {
            "anos": list(ANOS),
            "series": series,
            "total_acumulado": total_acumulado,
        },
    }


# ------------------------------------------------------------- base financeira

def _resumos_financeiros(acomp):
    """(consolidado, anual) por código de pilar — só TAB. 1/TAB. 9 e TAB. 1.1.

    `consolidado[codigo] = (previsto, executado)` com `ano isnull`;
    `anual[(codigo, ano)] = (previsto, executado)` só com `ano` preenchido.
    """
    consolidado = {}
    linhas = ResumoFinanceiro.objects.filter(
        acompanhamento=acomp, origem__in=("TAB. 1", "TAB. 9"), ano__isnull=True,
    ).select_related("pilar").order_by("origem", "pilar__ordem", "pilar__codigo")
    for linha in linhas:
        previsto = (
            linha.recurso_ou_meta if linha.pilar.codigo in PILARES_PPI
            else linha.captado
        )
        # TAB. 1 alimenta o PPI e TAB. 9 alimenta AT/Outras fontes; a primeira
        # linha vence se alguma duplicata existir na importação.
        consolidado.setdefault(linha.pilar.codigo, (previsto, linha.realizado))

    anual = {}
    linhas = ResumoFinanceiro.objects.filter(
        acompanhamento=acomp, origem="TAB. 1.1", ano__isnull=False,
    ).select_related("pilar")
    for linha in linhas:
        anual[(linha.pilar.codigo, linha.ano)] = (linha.projetado, linha.realizado)
    # Override manual vence o importado no ano correspondente (SDD §9).
    for override in acomp.overrides.filter(base="financeiro").select_related("pilar"):
        if override.campo not in ("previsto", "executado"):
            continue
        par = list(anual.get((override.pilar.codigo, override.ano), (None, None)))
        par[0 if override.campo == "previsto" else 1] = override.valor
        anual[(override.pilar.codigo, override.ano)] = (par[0], par[1])
    return consolidado, anual


def _painel_financeiro(ano, acomp):
    consolidado, anual = _resumos_financeiros(acomp)
    temporal = agregar_despesas_por_ano(acomp)

    def fonte_codigo(codigo):
        if codigo in PILARES_PPI:
            return "ppi"
        if codigo == "AT":
            return "at"
        if codigo == "OUTRASFONTES":
            return "outras"
        return None

    def executado_temporal(codigos, ano_coluna):
        """Executado anual dos lançamentos, ou ``None`` sem fonte temporal."""
        fontes = {fonte_codigo(codigo) for codigo in codigos}
        fontes.discard(None)
        if len(fontes) != 1:
            return None
        fonte = fontes.pop()
        if fonte not in temporal["fontes_com_dados"]:
            return None
        return temporal["fontes"][fonte][ano_coluna]

    def executado_pilar_temporal(codigo, ano_coluna):
        fonte = fonte_codigo(codigo)
        if fonte not in temporal["fontes_com_dados"]:
            return None
        return temporal["pilares"].get((codigo, ano_coluna), Decimal("0"))

    def valor(codigos, indice):
        """Soma do campo (0=previsto, 1=executado) no período selecionado."""
        if indice == 1 and ano is not None:
            temporal_valor = executado_temporal(codigos, ano)
            if temporal_valor is not None:
                return temporal_valor
        valores = []
        for codigo in codigos:
            par = anual.get((codigo, ano)) if ano is not None else consolidado.get(codigo)
            valores.append(None if par is None else par[indice])
        return _somar(valores)

    def serie_anual(codigos, indice):
        def lookup(ano_coluna):
            if indice == 1:
                temporal_valor = executado_temporal(codigos, ano_coluna)
                if temporal_valor is not None:
                    return temporal_valor
            valores = []
            for codigo in codigos:
                par = anual.get((codigo, ano_coluna))
                valores.append(None if par is None else par[indice])
            return _somar(valores)
        return _serie_anos(lookup)

    def serie_bloco(codigos, indice):
        # 4 anos + acumulado (o consolidado dos snapshots — mesmo valor do card).
        return serie_anual(codigos, indice) + [valor(codigos, indice)]

    cards = [
        _card("ppi", "Recursos PPI executados",
              valor(PILARES_PPI, 1), valor(PILARES_PPI, 0), "projetados"),
        _card("at", "Captação AT executada",
              valor(("AT",), 1), valor(("AT",), 0), "captados"),
        _card("outras", "Outras fontes executadas",
              valor(("OUTRASFONTES",), 1), valor(("OUTRASFONTES",), 0), "captados"),
    ]
    cards.append(_card(
        "total", "Execução consolidada",
        _somar([c["executado"] for c in cards]),
        _somar([c["previsto"] for c in cards]), "previstos"))

    graficos = {}
    for chave, codigos, nome_previsto in (
        ("ppi", PILARES_PPI, "Projetado"),
        ("at", ("AT",), "Captado"),
        ("outras", ("OUTRASFONTES",), "Captado"),
    ):
        graficos[chave] = _bloco_grafico(
            chave, serie_bloco(codigos, 0), serie_bloco(codigos, 1),
            nome_previsto, "Executado", valor(codigos, 0), valor(codigos, 1))

    def linha_pilar(codigo):
        previsto, executado = (
            anual.get((codigo, ano), (None, None)) if ano is not None
            else consolidado.get(codigo, (None, None))
        )
        if ano is not None:
            temporal_executado = executado_pilar_temporal(codigo, ano)
            if temporal_executado is not None:
                executado = temporal_executado
        return _linha(ROTULOS_PAINEL.get(codigo, codigo), previsto, executado,
                      codigo=codigo)

    grupos = []
    for titulo, bloco, codigos in GRUPOS_FINANCEIRO:
        linhas = [linha_pilar(codigo) for codigo in codigos]
        if bloco == "4.1 PPI":
            linhas.append(_linha(
                "Total PPI", cards[0]["previsto"], cards[0]["executado"], total=True))
        grupos.append({"titulo": titulo, "bloco": bloco, "linhas": linhas})

    series = [
        {"nome": "PPI executado", "valores": _num(serie_anual(PILARES_PPI, 1))},
        {"nome": "Captação AT executada", "valores": _num(serie_anual(("AT",), 1))},
        {"nome": "Outras fontes executadas",
         "valores": _num(serie_anual(("OUTRASFONTES",), 1))},
    ]
    return _dto(
        ano, BASE_FINANCEIRO, cards, graficos, grupos, series,
        cards[3]["executado"] if ano is None else None)


# ----------------------------------------------------------------- base física

def _unidade_majoritaria(kpis):
    """Unidade com mais KPIs no bloco; empate ⇒ unidade do primeiro KPI do PE.

    Unidades diferentes nunca são somadas (SDD §1.7): os KPIs de outra unidade
    ficam apenas na tabela.
    """
    contagem = {}
    for kpi in kpis:
        contagem[kpi.unidade] = contagem.get(kpi.unidade, 0) + 1
    if not contagem:
        return None
    maior = max(contagem.values())
    for kpi in kpis:
        if contagem[kpi.unidade] == maior:
            return kpi.unidade
    return None


def _campos_kpi(kpi, referencia):
    """(previsto, executado) do KPI em `referencia` (ano ou None = acumulado).

    2026/2027 só têm projeção — o executado é `None`, nunca projeção (SDD §8).
    Override manual vence o importado quando cobre o ano (SDD §9); o acumulado
    (`referencia=None`) é figura importada própria e nunca é afetado.
    """
    if referencia is None:
        return kpi.meta_total, kpi.acumulado
    metas = {2024: kpi.meta_2024, 2025: kpi.meta_2025,
             2026: kpi.meta_2026, 2027: kpi.meta_2027}
    executados = {2024: kpi.executado_2024, 2025: kpi.executado_2025,
                  2026: None, 2027: None}
    previsto, executado = metas[referencia], executados[referencia]
    for override in kpi.overrides.all():
        if override.ano != referencia:
            continue
        if override.campo == "previsto":
            previsto = override.valor
        elif override.campo == "executado":
            executado = override.valor
    return previsto, executado


def _painel_fisico(ano, acomp):
    kpis = list(
        KpiAcompanhamento.objects.filter(acompanhamento=acomp)
        .select_related("pilar").prefetch_related("overrides").order_by("sequencia", "codigo")
    )
    por_pilar = {}
    for kpi in kpis:
        por_pilar.setdefault(kpi.pilar.codigo, []).append(kpi)
    codigos_ordenados = [c for c in ORDEM_PILARES if c in por_pilar]
    codigos_ordenados += sorted(set(por_pilar) - set(ORDEM_PILARES))

    grupos = []
    for codigo in codigos_ordenados:
        linhas = []
        for kpi in por_pilar[codigo]:
            previsto, executado = _campos_kpi(kpi, ano)
            linhas.append(_linha(
                f"{kpi.nome} ({kpi.unidade})", previsto, executado,
                codigo=kpi.codigo, pilar=kpi.pilar))
        primeiro = por_pilar[codigo][0].pilar
        titulo = ROTULOS_PAINEL.get(codigo, primeiro.nome)
        grupos.append({"titulo": titulo, "bloco": titulo, "linhas": linhas})

    def bloco_kpis(codigos):
        """KPIs do bloco restritos à unidade majoritária (soma válida)."""
        do_bloco = [k for k in kpis if k.pilar.codigo in codigos]
        unidade = _unidade_majoritaria(do_bloco)
        return [k for k in do_bloco if k.unidade == unidade]

    def soma(sub, referencia, indice):
        return _somar([_campos_kpi(k, referencia)[indice] for k in sub])

    def serie_kpis(sub, indice):
        return _serie_anos(lambda a: soma(sub, a, indice)) + [soma(sub, None, indice)]

    cards = []
    graficos = {}
    series = []
    for chave, codigos, nome_previsto, titulo_card, denominador in (
        ("ppi", PILARES_PPI, "Meta", "Recursos PPI executados", "projetados"),
        ("at", ("AT",), "Meta", "Captação AT executada", "captados"),
        ("outras", ("OUTRASFONTES",), "Meta", "Outras fontes executadas", "captados"),
    ):
        sub = bloco_kpis(codigos)
        previsto, executado = soma(sub, ano, 0), soma(sub, ano, 1)
        cards.append(_card(chave, titulo_card, executado, previsto, denominador))
        graficos[chave] = _bloco_grafico(
            chave, serie_kpis(sub, 0), serie_kpis(sub, 1),
            nome_previsto, "Executado", previsto, executado)
        series.append({
            "nome": {"ppi": "PPI executado",
                     "at": "Captação AT executada",
                     "outras": "Outras fontes executadas"}[chave],
            "valores": _num(_serie_anos(lambda a: soma(sub, a, 1))),
        })

    # Total só soma KPIs de uma única unidade (a majoritária do conjunto) —
    # nunca mistura "Percentual" com "Número absoluto".
    sub_total = bloco_kpis(tuple(por_pilar))
    cards.append(_card(
        "total", "Execução consolidada",
        soma(sub_total, ano, 1), soma(sub_total, ano, 0), "previstos"))

    return _dto(
        ano, BASE_FISICO, cards, graficos, grupos, series,
        soma(sub_total, None, 1) if ano is None else None)


# ----------------------------------------------------------------- interface

def painel_acompanhamento(ano, base, acomp):
    """DTO do painel anual (ano|None, base) a partir dos snapshots importados.

    Mesmo contrato de `planning.services.painel()`; `ano=None` = todos os anos.
    """
    if acomp is None:
        raise ValueError("acompanhamento obrigatório")
    base = BASES_CANONICAS.get(base)
    if base is None:
        raise ValueError(f"base inválida: {base!r}")
    if ano is not None and ano not in ANOS:
        raise ValueError(f"ano inválido: {ano!r}")
    if base == BASE_FINANCEIRO:
        return _painel_financeiro(ano, acomp)
    return _painel_fisico(ano, acomp)
