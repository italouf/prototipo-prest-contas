"""Painel anual alimentado pelos snapshots importados (SDD §8).

Devolve **o mesmo DTO** de `planning.services.painel()` — chaves `ano, base,
unidade, rotulo_periodo, cards, graficos, tabela, consolidado` — para que
`_panel.html`, `pilares-table.html` e os filtros de SVG continuem sem mudança.

Duas representações do mesmo dado convivem aqui (contratos diferentes de
template e de geometria):

- `tabela.grupos[*].linhas[*]` aceita `previsto/executado/saldo = None` com
  `pct = None` e `faixa = "neutra"` — `numero_curto(None)` e o template
  renderizam `—` (nunca `0%` nem farol quando não há dado);
- `graficos[*].serie_*` e `consolidado.series` preservam `None` quando o ano
  não possui lançamento/linha importada; a geometria mantém a lacuna e os
  templates exibem `—`, sem fabricar zero.

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
efetivos e `saldo`/`pct`/`faixa` recalculam em `_linha`. O consolidado financeiro
(TAB. 1/TAB. 9) é uma figura importada própria. No físico, os ajustes anuais
corrigem `meta_total`/`acumulado` pela diferença em relação ao ano importado.
O editor do Geral usa `ano=0` para definir explicitamente os valores do ciclo
completo, com prioridade sobre esse cálculo.
"""
from decimal import Decimal

from apps.pillars.models import Pilar
from apps.planning.services import (
    ANOS,
    PILARES_PPI,
    ROTULOS_PAINEL,
    faixa,
    pct_inteiro,
    percentual,
    painel_pilar as painel_pilar_legado,
)

from .models import (
    Acompanhamento,
    KpiAcompanhamento,
    ProjetoFinanceiro,
    ResumoFinanceiro,
)
from .temporal import agregar_despesas_por_ano
from apps.planning.physical import percentual_fisico, resumo_fisico, saldo_fisico

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


def _card(chave, titulo, executado, previsto, denominador, valores_em_reais=False):
    pct = None if previsto is None or executado is None else pct_inteiro(executado, previsto)
    card = {
        "chave": chave,
        "titulo": titulo,
        "executado": executado,
        "previsto": previsto,
        "denominador": denominador,
        "pct": pct,
        "faixa": "neutra" if pct is None else faixa(percentual(executado, previsto)),
        "barra": min(pct, 100) if pct is not None else 0,
    }
    if valores_em_reais:
        card["valores_em_reais"] = True
    return card


def _bloco_grafico(chave, serie_previsto, serie_executado, nome_previsto,
                   nome_executado, previsto_periodo, executado_periodo,
                   acumulado_previsto, acumulado_executado,
                   valores_em_reais=False):
    pct = (
        None if previsto_periodo is None or executado_periodo is None
        else pct_inteiro(executado_periodo, previsto_periodo)
    )
    bloco_grafico = {
        "chave": chave,
        "serie_previsto": list(serie_previsto),
        "serie_executado": list(serie_executado),
        "nome_previsto": nome_previsto,
        "nome_executado": nome_executado,
        "acumulado_previsto": acumulado_previsto,
        "acumulado_executado": acumulado_executado,
        "rodape_pct": pct,
        "rodape_faixa": (
            "neutra" if pct is None
            else faixa(percentual(executado_periodo, previsto_periodo))
        ),
    }
    if valores_em_reais:
        bloco_grafico["valores_em_reais"] = True
    return bloco_grafico


def _rotulo_periodo(ano):
    if isinstance(ano, tuple):
        return f"Anos {ano[0]} a {ano[-1]}"
    if ano is None:
        return "Acumulado 2024 a 2027"
    return f"Ano {ANOS.index(ano) + 1}: {ano}"


def _dto(ano, base, cards, graficos, grupos, series, total_acumulado,
         valores_em_reais=False):
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
            "valores_em_reais": valores_em_reais,
        },
        "valores_em_reais": valores_em_reais,
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
        if override.campo not in ("previsto", "executado", "projetado"):
            continue
        if override.ano == 0:
            if override.campo == "projetado":
                continue
            par = list(consolidado.get(override.pilar.codigo, (None, None)))
            par[0 if override.campo == "previsto" else 1] = override.valor
            consolidado[override.pilar.codigo] = tuple(par)
            continue
        par = list(anual.get((override.pilar.codigo, override.ano), (None, None)))
        par[1 if override.campo == "executado" else 0] = override.valor
        anual[(override.pilar.codigo, override.ano)] = (par[0], par[1])
    return consolidado, anual


def _overrides_financeiros(acomp):
    """Mapa dos overrides financeiros por pilar, ano e campo."""
    return {
        (override.pilar.codigo, override.ano, override.campo): override.valor
        for override in acomp.overrides.filter(base="financeiro").select_related("pilar")
    }


ROTULOS_TAB_PPI = (
    ("PDI", "AFCCT / PD&I"),
    ("FORMACAO", "FCRH"),
    ("STARTUPS", "ACS"),
    ("INFRA", "INFRAESTRUTURA"),
)


def _percentual_disponivel(numerador, denominador):
    if numerador is None or denominador is None:
        return None
    return percentual(numerador, denominador)


def _linha_tab1(rotulo, recurso, realizado, projetado, combinado, total=False):
    pct = _percentual_disponivel(realizado, recurso)
    return {
        "rotulo": rotulo, "recurso": recurso, "realizado": realizado,
        "projetado": projetado, "combinado": combinado,
        "diferenca": recurso - realizado if recurso is not None and realizado is not None else None,
        "pct": pct, "faixa": faixa(pct), "total": total,
    }


def _linha_tab11(rotulo, recurso, r2024, r2025, r2026, p2026, p2027, projetado_total, total=False):
    realizado_total = _somar((r2024, r2025, r2026))
    combinado = (realizado_total + projetado_total
                 if realizado_total is not None and projetado_total is not None else None)
    pct = _percentual_disponivel(combinado, recurso)
    return {
        "rotulo": rotulo, "recurso": recurso,
        "realizado_2024": r2024, "realizado_2025": r2025,
        "realizado_2026": r2026, "projetado_2026": p2026, "projetado_2027": p2027,
        "projetado_total": projetado_total, "combinado": combinado,
        "diferenca": recurso - combinado if recurso is not None and combinado is not None else None,
        "pct": pct, "faixa": faixa(pct), "total": total,
    }


def _visao_financeiro_geral(acomp, pilares_selecionados=None):
    """Valores do ciclo completo das TAB. 1, 1.1 e 9, sem inferir anos da TAB. 9."""
    resumos = ResumoFinanceiro.objects.filter(
        acompanhamento=acomp, origem__in=("TAB. 1", "TAB. 1.1", "TAB. 9"),
    ).select_related("pilar")
    por_chave = {(r.origem, r.pilar.codigo, r.ano): r for r in resumos}
    ajustes = _overrides_financeiros(acomp)

    def resumo(origem, codigo, ano=None):
        linha = por_chave.get((origem, codigo, ano))
        if linha is None and any(c == codigo and a == (ano or 0) for c, a, _ in ajustes):
            pilar = next((r.pilar for r in resumos if r.pilar.codigo == codigo), None)
            pilar = pilar or Pilar.objects.filter(codigo=codigo, ativo=True).first()
            if pilar:
                linha = ResumoFinanceiro(pilar=pilar, origem=origem, ano=ano)
        return linha

    def campo(linha, nome):
        if linha is None:
            return None
        codigo = linha.pilar.codigo
        referencia = linha.ano or 0
        chave = {"realizado": "executado", "projetado": "projetado"}.get(nome)
        if nome == "recurso_ou_meta" and codigo in PILARES_PPI:
            chave, referencia = "previsto", 0
        elif nome == "captado" and codigo not in PILARES_PPI:
            chave = "previsto"
        elif nome == "projetado" and linha.ano is not None:
            if (codigo, referencia, "projetado") not in ajustes:
                chave = "previsto"
        if chave and (codigo, referencia, chave) in ajustes:
            return ajustes[(codigo, referencia, chave)]
        if nome == "realizado_mais_projetado":
            realizado, projetado = campo(linha, "realizado"), campo(linha, "projetado")
            if any((codigo, referencia, c) in ajustes for c in ("executado", "projetado")):
                return realizado + projetado if realizado is not None and projetado is not None else None
        return getattr(linha, nome)

    linhas_tab1 = []
    linhas_tab11 = []
    for codigo, rotulo in ROTULOS_TAB_PPI:
        if pilares_selecionados is not None and codigo not in pilares_selecionados:
            continue
        tab1 = resumo("TAB. 1", codigo)
        tab11 = resumo("TAB. 1.1", codigo)
        ano24 = resumo("TAB. 1.1", codigo, 2024)
        ano25 = resumo("TAB. 1.1", codigo, 2025)
        ano26 = resumo("TAB. 1.1", codigo, 2026)
        ano27 = resumo("TAB. 1.1", codigo, 2027)
        linhas_tab1.append(_linha_tab1(
            rotulo, campo(tab1, "recurso_ou_meta"), campo(tab1, "realizado"),
            campo(tab1, "projetado"), campo(tab1, "realizado_mais_projetado")))
        p2026 = campo(ano26, "projetado")
        p2027 = campo(ano27, "projetado")
        projetado_total = campo(tab11, "projetado")
        if projetado_total is None:
            projetado_total = _somar((p2026, p2027))
        recurso_tab11 = campo(tab11, "recurso_ou_meta")
        if recurso_tab11 is None:
            # Imports anteriores descartavam a linha da TAB. 1.1 quando O:S
            # estavam vazios. O recurso da TAB. 1 recupera a mesma meta PPI.
            recurso_tab11 = campo(tab1, "recurso_ou_meta")
        linhas_tab11.append(_linha_tab11(
            rotulo, recurso_tab11, campo(ano24, "realizado"),
            campo(ano25, "realizado"), campo(ano26, "realizado"),
            p2026, p2027, projetado_total))

    def totalizar(linhas, campos):
        return {campo: _somar(linha[campo] for linha in linhas) for campo in campos}

    soma1 = totalizar(linhas_tab1, ("recurso", "realizado", "projetado", "combinado"))
    linhas_tab1.append(_linha_tab1("TOTAL", **soma1, total=True))
    soma11 = totalizar(linhas_tab11, (
        "recurso", "realizado_2024", "realizado_2025", "realizado_2026",
        "projetado_2026", "projetado_2027", "projetado_total"))
    linhas_tab11.append(_linha_tab11(
        "TOTAL", soma11["recurso"], soma11["realizado_2024"],
        soma11["realizado_2025"], soma11["realizado_2026"],
        soma11["projetado_2026"], soma11["projetado_2027"], soma11["projetado_total"], total=True))

    ppi_total = linhas_tab1[-1]
    graficos = {
        "ppi": {
            "serie_previsto": [l["recurso"] for l in linhas_tab1[:-1]],
            "serie_executado": [l["realizado"] for l in linhas_tab1[:-1]],
            "nome_previsto": "RECURSO PPI", "nome_executado": "REALIZADO",
            "valores_em_reais": True, "precisao_financeira": True,
            "rodape_pct": ppi_total["pct"], "rodape_faixa": ppi_total["faixa"],
        },
    }
    for chave, codigo in (("at", "AT"), ("outras", "OUTRASFONTES")):
        linha = resumo("TAB. 9", codigo)
        meta = campo(linha, "recurso_ou_meta")
        captado = campo(linha, "captado")
        realizado = campo(linha, "realizado")
        pct_meta = _percentual_disponivel(captado, meta)
        pct_exec = _percentual_disponivel(realizado, captado)
        graficos[chave] = {
            "meta": meta, "captado": captado, "realizado": realizado,
            "pct_meta": pct_meta, "pct_exec": pct_exec,
            "pct_meta_inteiro": pct_inteiro(captado, meta) if captado is not None else None,
            "pct_exec_inteiro": pct_inteiro(realizado, captado) if realizado is not None else None,
            "anel_meta": round(float(min(max(pct_meta, 0), 100)), 2) if pct_meta is not None else 0,
            "anel_exec": round(float(min(max(pct_exec, 0), 100)), 2) if pct_exec is not None else 0,
        }
    linhas_programa = list(linhas_tab1[:-1])
    for codigo, rotulo in (("AT", "AT"), ("OUTRASFONTES", "Outras fontes")):
        if pilares_selecionados is not None and codigo not in pilares_selecionados:
            continue
        linha = resumo("TAB. 9", codigo)
        linhas_programa.append(_linha_tab1(
            rotulo, campo(linha, "captado"), campo(linha, "realizado"),
            campo(linha, "projetado"), campo(linha, "realizado_mais_projetado")))
    total_programa = totalizar(linhas_programa, ("recurso", "realizado", "projetado", "combinado"))
    linhas_programa.append(_linha_tab1("TOTAL", **total_programa, total=True))
    return {"tabela_tab1": {"linhas": linhas_tab1, "total": linhas_tab1[-1]},
            "tabela_programa": {"linhas": linhas_programa, "total": linhas_programa[-1]},
            "tabela_tab11": {"linhas": linhas_tab11, "total": linhas_tab11[-1]}, "graficos_ciclo": graficos}


def _painel_financeiro(ano, acomp, pilares_selecionados=None):
    consolidado, anual = _resumos_financeiros(acomp)
    if pilares_selecionados is not None:
        consolidado = {c: v for c, v in consolidado.items() if c in pilares_selecionados}
        anual = {chave: v for chave, v in anual.items() if chave[0] in pilares_selecionados}
    temporal = agregar_despesas_por_ano(acomp)
    overrides = _overrides_financeiros(acomp)

    def fonte_codigo(codigo):
        if codigo in PILARES_PPI:
            return "ppi"
        if codigo == "AT":
            return "at"
        if codigo == "OUTRASFONTES":
            return "outras"
        return None

    def executado_pilar(codigo, ano_coluna):
        if pilares_selecionados is not None and codigo not in pilares_selecionados:
            return None
        override_key = (codigo, ano_coluna, "executado")
        if override_key in overrides:
            return overrides[override_key]
        fonte = fonte_codigo(codigo)
        if fonte in temporal["fontes_com_dados"]:
            return temporal["pilares_por_fonte"][fonte].get(
                (codigo, ano_coluna), Decimal("0")
            )
        par = anual.get((codigo, ano_coluna))
        return None if par is None else par[1]

    def executado_temporal(codigos, ano_coluna):
        """Executado anual efetivo, com override vencendo o temporal."""
        return _somar([executado_pilar(codigo, ano_coluna) for codigo in codigos])

    def valor(codigos, indice):
        """Soma do campo (0=previsto, 1=executado) no período selecionado."""
        if indice == 1 and ano is not None:
            return executado_temporal(codigos, ano)
        valores = []
        for codigo in codigos:
            par = anual.get((codigo, ano)) if ano is not None else consolidado.get(codigo)
            valores.append(None if par is None else par[indice])
        return _somar(valores)

    def serie_anual(codigos, indice):
        def lookup(ano_coluna):
            if indice == 1:
                return executado_temporal(codigos, ano_coluna)
            valores = []
            for codigo in codigos:
                par = anual.get((codigo, ano_coluna))
                valores.append(None if par is None else par[indice])
            return _somar(valores)
        return _serie_anos(lookup)

    def valor_total(codigos, indice):
        valores = []
        for codigo in codigos:
            par = consolidado.get(codigo)
            valores.append(None if par is None else par[indice])
        return _somar(valores)

    cards = [
        _card("ppi", "Recursos PPI",
              valor(PILARES_PPI, 1), valor(PILARES_PPI, 0), "projetados",
              valores_em_reais=True),
        _card("at", "Captação AT",
              valor(("AT",), 1), valor(("AT",), 0), "captados",
              valores_em_reais=True),
        _card("outras", "Outras fontes",
              valor(("OUTRASFONTES",), 1), valor(("OUTRASFONTES",), 0), "captados",
              valores_em_reais=True),
    ]
    cards.append(_card(
        "total", "Execução consolidada",
        _somar([c["executado"] for c in cards]),
        _somar([c["previsto"] for c in cards]), "previstos",
        valores_em_reais=True))

    graficos = {}
    for chave, codigos, nome_previsto in (
        ("ppi", PILARES_PPI, "Projetado"),
        ("at", ("AT",), "Captado"),
        ("outras", ("OUTRASFONTES",), "Captado"),
    ):
        graficos[chave] = _bloco_grafico(
            chave, serie_anual(codigos, 0), serie_anual(codigos, 1),
            nome_previsto, "Executado", valor(codigos, 0), valor(codigos, 1),
            valor_total(codigos, 0), valor_total(codigos, 1),
            valores_em_reais=True)

    def linha_pilar(codigo):
        previsto, executado = (
            anual.get((codigo, ano), (None, None)) if ano is not None
            else consolidado.get(codigo, (None, None))
        )
        if ano is not None:
            executado = executado_pilar(codigo, ano)
        return _linha(ROTULOS_PAINEL.get(codigo, codigo), previsto, executado,
                      codigo=codigo)

    grupos = []
    for titulo, bloco, codigos in GRUPOS_FINANCEIRO:
        if pilares_selecionados is not None:
            codigos = [c for c in codigos if c in pilares_selecionados]
        if not codigos:
            continue
        linhas = [linha_pilar(codigo) for codigo in codigos]
        if bloco == "4.1 PPI":
            linhas.append(_linha(
                "Total PPI", cards[0]["previsto"], cards[0]["executado"], total=True))
        grupos.append({"titulo": titulo, "bloco": bloco, "linhas": linhas})

    series = [
         {"nome": "PPI executado", "valores": serie_anual(PILARES_PPI, 1)},
         {"nome": "Captação AT executada", "valores": serie_anual(("AT",), 1)},
         {"nome": "Outras fontes executadas",
          "valores": serie_anual(("OUTRASFONTES",), 1)},
    ]
    dto = _dto(
        ano, BASE_FINANCEIRO, cards, graficos, grupos, series,
        cards[3]["executado"] if ano is None else None,
        valores_em_reais=True)
    if ResumoFinanceiro.objects.filter(acompanhamento=acomp, origem="TAB. 1").exists():
        dto["visao_financeiro_geral"] = True
        dto.update(_visao_financeiro_geral(acomp, pilares_selecionados))
        for card in dto["cards"]:
            card["precisao_financeira"] = True
            card["valor_compacto"] = card["chave"] in ("at", "outras")
        dto["rotulo_periodo"] = "Acumulado do ciclo completo"
    return dto


def _card_pilar(chave, titulo, valor, referencia, denominador, com_farol=True):
    pct = pct_inteiro(valor, referencia) if com_farol else None
    card = {
        "chave": chave,
        "titulo": titulo,
        "executado": valor,
        "previsto": referencia,
        "denominador": denominador,
        "pct": pct,
        "faixa": faixa(percentual(valor, referencia)) if com_farol else "neutra",
        "barra": min(pct or 0, 100) if pct is not None else 0,
    }
    return card


_COLUNAS_VISAO_PDI = (
    ("rotulo", "Coluna1", "texto"),
    ("recurso_ou_meta", "RECURSO PPI AFCCT / PDI", "dinheiro"),
    ("realizado", "REALIZADO", "dinheiro"),
    ("projetado", "PROJETADO TOTAL", "dinheiro"),
    ("realizado_mais_projetado", "REALIZADO + PROJETADO", "dinheiro"),
    ("diferenca", "DIF.  REL. AO  PPI", "dinheiro"),
)
_COLUNAS_PROJECAO_PROJETOS = (
    ("projetado_2026", "PROJETADO 2026", "dinheiro"),
    ("projetado_2027", "PROJETADO 2027", "dinheiro"),
    ("realizado_mais_projetado", "REALIZADO + PROJETADO", "dinheiro"),
    ("diferenca", "DIFERENÇA ORÇADO", "dinheiro"),
)
_COLUNAS_PROJETOS_PDI = (
    ("codigo_projeto_embrapii", "CÓDIGO DO PROJETO EMBRAPII", "texto"),
    ("nome", "PROJETO", "texto"),
    ("status", "STATUS", "texto"),
    ("inicio", "INICIO", "data"),
    ("fim", "FINAL", "data"),
    ("orcado", "ORÇADO SÍNTESE", "dinheiro"),
    ("realizado", "REALIZADO", "dinheiro"),
    *_COLUNAS_PROJECAO_PROJETOS,
    ("percentual", "% REALIZADO ORÇADO", "percentual"),
)
_COLUNAS_PROJETOS_FCRH = (
    ("codigo_projeto_embrapii", "CÓDIGO DO PROJETO EMBRAPII", "texto"),
    ("nome", "PROJETO", "texto"),
    ("status", "STATUS", "texto"),
    ("inicio", "INICIO DO PROJETO", "data"),
    ("fim", "FINAL DO PROJETO", "data"),
    ("orcado", "ORÇADO ORIGINAL", "dinheiro"),
    ("realizado", "REALIZADO TOTAL", "dinheiro"),
    *_COLUNAS_PROJECAO_PROJETOS,
    ("percentual", "% REALIZADO ORÇADO", "percentual"),
)
_COLUNAS_PROJETOS_ACS = (
    ("codigo_projeto_embrapii", "CÓDIGO DO PROJETO EMBRAPII", "texto"),
    ("nome", "PROJETO", "texto"),
    ("status", "STATUS", "texto"),
    ("fim", "DATA FINAL DO PROJETO", "data"),
    ("orcado", "VALOR ORÇADO", "dinheiro"),
    ("realizado", "REALIZADO TOTAL", "dinheiro"),
    *_COLUNAS_PROJECAO_PROJETOS,
    ("percentual", "% REALIZADO", "percentual"),
)
_TABELAS_PILARES_FINANCEIROS = {
    "PDI": {
        "origem_visao": "TAB. 3", "origem_projetos": "TAB. 2",
        "nome_visao": "tbl_VisaoPDI", "nome_projetos": "tbl_ProjetosPDI",
        "recurso": "RECURSO PPI AFCCT / PDI", "diferenca": "DIF.  REL. AO  PPI",
        "colunas_projetos": _COLUNAS_PROJETOS_PDI, "total": "TOTAL GERAL",
    },
    "FORMACAO": {
        "origem_visao": "TAB. 5", "origem_projetos": "TAB. 4",
        "nome_visao": "tbl_VisaoFCRH", "nome_projetos": "tbl_ProjetosFCRH",
        "recurso": "RECURSO PPI FCRH", "diferenca": "DIFERENÇA PPI",
        "colunas_projetos": _COLUNAS_PROJETOS_FCRH, "total": "TOTAL GERAL - ATUAL",
    },
    "STARTUPS": {
        "origem_visao": "TAB. 8", "origem_projetos": "TAB. 6",
        "nome_visao": "tbl_VisaoACS", "nome_projetos": "tbl_ProjetosACS",
        "recurso": "TOTAL ACS", "diferenca": "DIFERENÇA PPI",
        "colunas_projetos": _COLUNAS_PROJETOS_ACS, "total": "TOTAL",
    },
}
PILARES_TABELAS_FINANCEIRAS = tuple(_TABELAS_PILARES_FINANCEIROS)


def _tabela_financeira_pilar(nome, colunas, registros):
    linhas = []
    for registro in registros:
        celulas = []
        for campo, _cabecalho, tipo in colunas:
            valor = registro.get(campo)
            if tipo == "percentual" and valor is not None:
                valor *= 100
            celulas.append({"campo": campo, "tipo": tipo, "valor": valor})
        linhas.append({"celulas": celulas, "total": registro.get("total", False)})
    return {"nome": nome, "cabecalhos": [c[1] for c in colunas], "linhas": linhas}


def painel_financeiro_pilar(pilar, acomp):
    """Visão integral das tabelas PDI, FCRH e ACS, sem recortes por ano.

    A diferença é apresentada em módulo. O PK preserva a ordem de inclusão
    das linhas, inclusive nos arquivos sem coluna ITEM.
    """
    codigo = pilar.codigo
    contrato = _TABELAS_PILARES_FINANCEIROS[codigo]
    colunas_visao = tuple(
        (campo, contrato["recurso"] if campo == "recurso_ou_meta" else
         contrato["diferenca"] if campo == "diferenca" else cabecalho, tipo)
        for campo, cabecalho, tipo in _COLUNAS_VISAO_PDI
    )
    colunas_projetos = contrato["colunas_projetos"]
    resumo = ResumoFinanceiro.objects.filter(
        acompanhamento=acomp, pilar=pilar, origem=contrato["origem_visao"], ano__isnull=True,
    ).values(*(c[0] for c in colunas_visao if c[0] != "rotulo")).first()
    campos_projetos = [c[0] for c in colunas_projetos]
    if "sequencia" not in campos_projetos:
        campos_projetos.append("sequencia")
    projetos = list(ProjetoFinanceiro.objects.filter(
        acompanhamento=acomp, pilar=pilar, origem=contrato["origem_projetos"],
    ).order_by("pk").values(*campos_projetos))
    # Backfill de exibição para snapshots anteriores, cujo ITEM era numérico.
    for registro in projetos:
        if registro.get("codigo_projeto_embrapii") in (None, "") and registro["sequencia"] is not None:
            registro["codigo_projeto_embrapii"] = str(registro["sequencia"])
    if resumo:
        ajustes = _overrides_financeiros(acomp)
        for campo, chave in (("recurso_ou_meta", "previsto"), ("realizado", "executado"), ("projetado", "projetado")):
            if (codigo, 0, chave) in ajustes:
                resumo[campo] = ajustes[(codigo, 0, chave)]
        if any((codigo, 0, campo) in ajustes for campo in ("previsto", "executado", "projetado")):
            real, proj, rec = resumo["realizado"], resumo["projetado"], resumo["recurso_ou_meta"]
            resumo["realizado_mais_projetado"] = real + (proj or Decimal(0)) if real is not None else None
            resumo["diferenca"] = rec - resumo["realizado_mais_projetado"] if rec is not None and real is not None else None
    recurso = resumo.get("recurso_ou_meta") if resumo else None
    realizado = resumo.get("realizado") if resumo else None
    diferenca_importada = resumo.get("diferenca") if resumo else None
    diferenca = abs(diferenca_importada) if diferenca_importada is not None else None
    pct = pct_inteiro(realizado, recurso) if realizado is not None else None
    faixa_execucao = faixa(percentual(realizado, recurso)) if pct is not None else "neutra"
    cards = [
        _card_pilar("previsto", contrato["recurso"], recurso, recurso, "do PPI", False),
        _card_pilar("executado", "REALIZADO", realizado, recurso, "do PPI", realizado is not None),
        _card_pilar("saldo", contrato["diferenca"], diferenca, recurso, "do PPI", diferenca is not None),
    ]
    cards[0]["ocultar_progresso"] = True
    cards[2]["rotulo_percentual"] = "do recurso PPI"
    for card in cards:
        card.update(valores_em_reais=True, precisao_financeira=True)
    linhas_projetos = list(projetos)
    if projetos:
        total = {campo: _somar(p[campo] for p in projetos)
                 for campo, _cabecalho, tipo in colunas_projetos if tipo == "dinheiro"}
        total.update({"nome": contrato["total"], "total": True})
        linhas_projetos.append(total)
    bloco = {
        "pilar": pilar, "codigo": codigo, "rotulo": ROTULOS_PAINEL[codigo],
        "ano": None, "base": BASE_FINANCEIRO, "unidade": "R$",
        "rotulo_periodo": "Acumulado do ciclo completo",
        "rotulo_previsto": contrato["recurso"], "denominador": "do PPI",
        "previsto": recurso, "executado": realizado, "saldo": diferenca,
        "pct": pct, "faixa": faixa_execucao, "cards": cards,
        "serie_previsto": [None] * len(ANOS), "serie_executado": [None] * len(ANOS),
        "tabela": [], "projetos": len(projetos), "unidade_projetos": "projetos",
        "valores_em_reais": True, "visao_financeira_pilar": True,
        "registros_projetos": projetos,
        "tabela_visao_financeira": _tabela_financeira_pilar(
            contrato["nome_visao"], colunas_visao,
            [{**resumo, "rotulo": "RECURSO PPI", "diferenca": diferenca}] if resumo else [],
        ),
        "tabela_projetos_financeiros": _tabela_financeira_pilar(
            contrato["nome_projetos"], colunas_projetos, linhas_projetos,
        ),
    }
    if codigo == "PDI":
        bloco.update(visao_pdi=True, tabela_visao_pdi=bloco["tabela_visao_financeira"],
                     tabela_projetos_pdi=bloco["tabela_projetos_financeiros"])
    return bloco


def painel_pdi_financeiro(pilar, acomp):
    """Compatibilidade com consumidores do DTO PDI."""
    return painel_financeiro_pilar(pilar, acomp)


_COLUNAS_CAPTACAO = (
    ("rotulo", "PILAR", "texto"),
    ("recurso_ou_meta", "META TOTAL", "dinheiro"),
    ("captado_anos_1_2", "CAPTADO (ANO 1 E 2)", "dinheiro"),
    ("captado_ano3_ytd", "CAPTADO (ANO 3 - YTD)", "dinheiro"),
    ("captado", "CAPTADO TOTAL", "dinheiro"),
    ("realizado", "REALIZADO TOTAL", "dinheiro"),
    ("percentual_meta", "% CAPTADO META", "percentual"),
    ("percentual_captado", "% REALIZADO CAPTADO", "percentual"),
)
_ROTULOS_CAPTACAO = {"AT": "ASSOCIAÇÃO TECNOLÓGICA", "OUTRASFONTES": "OUTRAS FONTES"}


def painel_captacao(pilar, ano, base, acomp, *, fontes_autorizadas, anos=None):
    """Dashboard combinado; o escopo explícito vale também para os totais."""
    base = BASES_CANONICAS[base]
    if base == BASE_FISICO and anos:
        ano = tuple(anos)
    fontes = tuple(codigo for codigo in _ROTULOS_CAPTACAO if codigo in fontes_autorizadas)
    bloco = {
        "pilar": pilar, "codigo": "AT", "rotulo": "AT e Outras Fontes",
        "base": base, "ano": ano if base == BASE_FISICO else None,
        "rotulo_periodo": _rotulo_periodo(ano) if base == BASE_FISICO else "Acumulado do ciclo completo",
        "unidade": "unidades por indicador" if base == BASE_FISICO else "R$",
        "visao_captacao": True, "visao_financeira_pilar": base == BASE_FINANCEIRO,
        "serie_previsto": [None] * len(ANOS), "serie_executado": [None] * len(ANOS),
        "tabela": [], "blocos_fisicos": [],
    }
    if base == BASE_FISICO:
        bloco["tabela_gerencial_fisica"] = {"grupos": []}
        for fonte in Pilar.objects.filter(codigo__in=fontes, ativo=True).order_by("ordem", "pk"):
            if acomp is None:
                sub = painel_pilar_legado(fonte, ano, base)
                sub["unidade_indicador"] = "metas"
                blocos = [sub]
            else:
                unidades = list(KpiAcompanhamento.objects.filter(
                    acompanhamento=acomp, pilar=fonte,
                ).order_by("sequencia", "codigo").values_list("unidade", flat=True))
                blocos = [_painel_pilar_fisico(fonte, ano, acomp, unidade=unidade)
                          for unidade in dict.fromkeys(unidades)]
            if blocos:
                bloco["tabela_gerencial_fisica"]["grupos"].extend(
                    blocos[0].get("tabela_gerencial_fisica", {"grupos": []})["grupos"])
            for sub in blocos:
                sub["chave"] = f"captacao-fisica-{fonte.codigo}-{len(bloco['blocos_fisicos'])}"
                sub["barra_percentual"] = min(max(sub["pct"] or 0, 0), 100)
                for card in sub["cards"]:
                    card["unidade"] = sub["unidade_indicador"]
                bloco["blocos_fisicos"].append(sub)
        return bloco

    registros = list(ResumoFinanceiro.objects.filter(
        acompanhamento=acomp, origem="TAB. 9", ano__isnull=True, pilar__codigo__in=fontes,
    ).values("pilar__codigo", *(c[0] for c in _COLUNAS_CAPTACAO if c[0] != "rotulo")))
    por_fonte = {r["pilar__codigo"]: r for r in registros}
    ajustes = _overrides_financeiros(acomp) if acomp else {}
    for codigo, registro in por_fonte.items():
        for campo, chave in (("captado", "previsto"), ("realizado", "executado"), ("recurso_ou_meta", "meta_captacao"), ("captado_anos_1_2", "captado_anos_1_2"), ("captado_ano3_ytd", "captado_ano3_ytd")):
            if (codigo, 0, chave) in ajustes:
                registro[campo] = ajustes[(codigo, 0, chave)]
        registro["percentual_meta"] = _percentual_disponivel(registro["captado"], registro["recurso_ou_meta"])
        registro["percentual_captado"] = _percentual_disponivel(registro["realizado"], registro["captado"])
        for campo in ("percentual_meta", "percentual_captado"):
            if registro[campo] is not None:
                registro[campo] /= 100
    linhas = [{**por_fonte[codigo], "rotulo": _ROTULOS_CAPTACAO[codigo]}
              for codigo in fontes if codigo in por_fonte]
    total = {campo: _somar(r[campo] for r in linhas)
             for campo, _titulo, tipo in _COLUNAS_CAPTACAO if tipo == "dinheiro"}
    captado, realizado = total["captado"], total["realizado"]
    saldo = abs(captado - realizado) if captado is not None and realizado is not None else None
    taxa = _percentual_disponivel(realizado, captado)
    pct = pct_inteiro(realizado, captado) if taxa is not None else None
    cards = [
        _card_pilar("previsto", "CAPTADO TOTAL", captado, captado, "captados", False),
        _card_pilar("executado", "REALIZADO TOTAL", realizado, captado, "captados", realizado is not None),
        _card_pilar("saldo", "SALDO", saldo, captado, "captados", saldo is not None),
    ]
    cards[0]["ocultar_progresso"] = True
    cards[2]["rotulo_percentual"] = "do captado"
    for card in cards:
        card.update(valores_em_reais=True, precisao_financeira=True)
        card["barra"] = min(max(card["pct"] or 0, 0), 100)
    if linhas:
        taxa_meta = _percentual_disponivel(captado, total["recurso_ou_meta"])
        total.update(rotulo="TOTAL", total=True,
                     percentual_meta=taxa_meta / 100 if taxa_meta is not None else None,
                     percentual_captado=taxa / 100 if taxa is not None else None)
        linhas.append(total)
    bloco.update(
        cards=cards, previsto=captado, executado=realizado, saldo=saldo, pct=pct,
        faixa=faixa(taxa), barra_percentual=min(max(pct or 0, 0), 100),
        valores_em_reais=True,
        registros_captacao=linhas[:-1] if linhas and linhas[-1].get("total") else linhas,
        total_captacao=total,
        tabela_captacao=_tabela_financeira_pilar("tbl_CaptaoATeOutros", _COLUNAS_CAPTACAO, linhas),
    )
    return bloco


def _painel_pilar_financeiro(pilar, ano, acomp):
    if pilar.codigo in PILARES_TABELAS_FINANCEIRAS:
        return painel_financeiro_pilar(pilar, acomp)
    consolidado, anual = _resumos_financeiros(acomp)
    temporal = agregar_despesas_por_ano(acomp)
    overrides = _overrides_financeiros(acomp)
    codigo = pilar.codigo
    fonte = {
        **{pilar_codigo: "ppi" for pilar_codigo in PILARES_PPI},
        "AT": "at",
        "OUTRASFONTES": "outras",
    }.get(codigo)

    def executado_temporal(ano_coluna):
        override_key = (codigo, ano_coluna, "executado")
        if override_key in overrides:
            return overrides[override_key]
        if fonte not in temporal["fontes_com_dados"]:
            par = anual.get((codigo, ano_coluna))
            return None if par is None else par[1]
        return temporal["pilares_por_fonte"][fonte].get(
            (codigo, ano_coluna), Decimal("0")
        )

    def par_anual(ano_coluna):
        previsto, executado = anual.get((codigo, ano_coluna), (None, None))
        temporal_executado = executado_temporal(ano_coluna)
        if temporal_executado is not None:
            executado = temporal_executado
        return previsto, executado

    pares_anuais = [par_anual(ano_coluna) for ano_coluna in ANOS]
    serie_previsto = [par[0] for par in pares_anuais]
    serie_executado = [par[1] for par in pares_anuais]
    acumulado_previsto, acumulado_executado = consolidado.get(
        codigo, (None, None)
    )
    if ano is None:
        previsto, executado = acumulado_previsto, acumulado_executado
    else:
        previsto, executado = pares_anuais[ANOS.index(ano)]
    saldo = None if previsto is None or executado is None else previsto - executado
    pct = pct_inteiro(executado, previsto)
    rotulo_previsto = "Projetado" if codigo in PILARES_PPI else "Captado"
    denominador = "projetados" if codigo in PILARES_PPI else "captados"

    cards = [
        _card_pilar("previsto", rotulo_previsto, previsto, previsto, denominador, False),
        _card_pilar("executado", "Executado", executado, previsto, denominador),
        _card_pilar("saldo", "Saldo a executar", saldo, previsto, "restantes", False),
        {**_card_pilar("percentual", "% Executado", executado, previsto, denominador),
         "executado": None},
    ]
    for card in cards:
        card["valores_em_reais"] = True
    tabela = []
    for indice, ano_coluna in enumerate(ANOS):
        pv, ex = pares_anuais[indice]
        saldo_ano = None if pv is None or ex is None else pv - ex
        pp = pct_inteiro(ex, pv)
        tabela.append({
            "rotulo": f"Ano {indice + 1}: {ano_coluna}",
            "previsto": pv,
            "executado": ex,
            "saldo": saldo_ano,
            "pct": pp,
            "faixa": "neutra" if pp is None else faixa(percentual(ex, pv)),
            "total": False,
            "destaque": ano is not None and ano == ano_coluna,
        })
    total_pct = pct_inteiro(acumulado_executado, acumulado_previsto)
    tabela.append({
        "rotulo": "Total",
        "previsto": acumulado_previsto,
        "executado": acumulado_executado,
        "saldo": None if acumulado_previsto is None or acumulado_executado is None
        else acumulado_previsto - acumulado_executado,
        "pct": total_pct,
        "faixa": "neutra" if total_pct is None else faixa(
            percentual(acumulado_executado, acumulado_previsto)
        ),
        "total": True,
        "destaque": False,
    })
    projetos = ProjetoFinanceiro.objects.filter(
        acompanhamento=acomp, pilar=pilar
    ).count()
    bloco = {
        "pilar": pilar,
        "codigo": codigo,
        "rotulo": ROTULOS_PAINEL.get(codigo, pilar.nome),
        "ano": ano,
        "base": BASE_FINANCEIRO,
        "unidade": "R$ mi",
        "rotulo_periodo": _rotulo_periodo(ano),
        "rotulo_previsto": rotulo_previsto,
        "denominador": denominador,
        "previsto": previsto,
        "executado": executado,
        "saldo": saldo,
        "pct": pct,
        "faixa": "neutra" if pct is None else faixa(percentual(executado, previsto)),
        "cards": cards,
        "serie_previsto": serie_previsto,
        "serie_executado": serie_executado,
        "grafico": {
            "chave": "pilar",
            "serie_previsto": serie_previsto,
            "serie_executado": serie_executado,
            "acumulado_previsto": acumulado_previsto,
            "acumulado_executado": acumulado_executado,
            "nome_previsto": rotulo_previsto,
            "nome_executado": "Executado",
            "rodape_pct": pct,
            "rodape_faixa": "neutra" if pct is None else faixa(
                percentual(executado, previsto)
            ),
            "valores_em_reais": True,
        },
        "rodape_pct": pct,
        "rodape_faixa": "neutra" if pct is None else faixa(
            percentual(executado, previsto)
        ),
        "tabela": tabela,
        "projetos": projetos,
        "unidade_projetos": "projetos",
        "valores_em_reais": True,
    }
    return bloco


def _painel_pilar_fisico(pilar, ano, acomp, *, unidade=None):
    kpis = list(
        KpiAcompanhamento.objects.filter(acompanhamento=acomp, pilar=pilar)
        .select_related("pilar").prefetch_related("overrides").order_by("sequencia", "codigo")
    )
    unidade_explicita = unidade is not None
    unidade = unidade if unidade_explicita else _unidade_majoritaria(kpis)
    sub = [kpi for kpi in kpis if kpi.unidade == unidade]
    indicadores_resumo = sub if unidade_explicita else kpis

    def soma(referencia, indice):
        return _somar(_campos_kpi(kpi, referencia)[indice] for kpi in sub)

    def saldo(referencia):
        return _somar(saldo_fisico(*_campos_kpi(kpi, referencia)) for kpi in sub)

    def resumo(referencia):
        return resumo_fisico(_campos_kpi(kpi, referencia) for kpi in indicadores_resumo)

    serie_previsto = [soma(a, 0) for a in ANOS]
    serie_executado = [soma(a, 1) for a in ANOS]
    previsto, executado = soma(ano, 0), soma(ano, 1)
    executado_limitado = _somar(min(ex, pv) if ex is not None and pv is not None else None
                               for pv, ex in (_campos_kpi(kpi, ano) for kpi in sub))
    saldo_periodo = saldo(ano)
    resumo_periodo = resumo(ano)
    pct_periodo = percentual_fisico(executado_limitado, previsto)
    pct_periodo = pct_inteiro(pct_periodo, 100) if pct_periodo is not None else None
    cards = [
        _card_pilar("previsto", "Meta", previsto, previsto, "projetados", False),
        _card_pilar("executado", "Executado", executado, previsto, "projetados"),
        _card_pilar("saldo", "Saldo a executar", saldo_periodo, previsto, "restantes", False),
        {**_card_pilar("percentual", "% Executado", executado, previsto, "projetados"),
         "executado": None},
    ]
    for card in cards:
        if card["chave"] in ("executado", "percentual"):
            card.update(pct=pct_periodo, faixa=faixa(pct_periodo), barra=pct_periodo or 0)
    tabela = []
    for referencia in [*ANOS, None]:
        pv, ex = soma(referencia, 0), soma(referencia, 1)
        pct_anual = percentual_fisico(ex, pv) if referencia is not None else percentual_fisico(
            _somar(min(e, p) if e is not None and p is not None else None for p, e in
                   (_campos_kpi(kpi, None) for kpi in sub)), pv)
        pct_anual = pct_inteiro(pct_anual, 100) if pct_anual is not None else None
        tabela.append({
            "rotulo": "Total" if referencia is None else f"Ano {ANOS.index(referencia) + 1}: {referencia}",
            "ano": referencia, "previsto": pv, "executado": ex,
            "saldo": saldo(referencia) if referencia is None else saldo_fisico(pv, ex),
            "pct": pct_anual, "faixa": faixa(pct_anual),
            "total": referencia is None,
            "destaque": ano is not None and ano == referencia,
        })
    return {
        "pilar": pilar, "codigo": pilar.codigo,
        "rotulo": ROTULOS_PAINEL.get(pilar.codigo, pilar.nome),
        "ano": ano, "base": BASE_FISICO, "unidade": "metas",
        "unidade_indicador": unidade, "rotulo_periodo": _rotulo_periodo(ano),
        "rotulo_previsto": "Meta", "denominador": "projetados",
        "previsto": previsto, "executado": executado, "saldo": saldo_periodo,
        "pct": pct_periodo, "faixa": faixa(pct_periodo),
        "executado_limitado": executado_limitado, "status_counts": resumo_periodo,
        "cards": cards, "serie_previsto": serie_previsto, "serie_executado": serie_executado,
        "grafico": {
            "chave": "pilar", "serie_previsto": serie_previsto, "serie_executado": serie_executado,
            "acumulado_previsto": soma(None, 0), "acumulado_executado": soma(None, 1),
            "nome_previsto": "Meta", "nome_executado": "Executado",
            "rodape_pct": pct_periodo, "rodape_faixa": faixa(pct_periodo),
        },
        "rodape_pct": pct_periodo, "rodape_faixa": faixa(pct_periodo),
        "tabela": tabela, "tabela_gerencial_fisica": _tabela_gerencial_fisica(kpis, ano),
        "projetos": ProjetoFinanceiro.objects.filter(acompanhamento=acomp, pilar=pilar).count(),
        "unidade_projetos": "projetos",
    }


def painel_pilar_acompanhamento(pilar, ano, base, acomp, anos=None):
    """DTO do pilar usando o acompanhamento importado selecionado."""
    base = BASES_CANONICAS.get(base)
    if base not in (BASE_FINANCEIRO, BASE_FISICO):
        raise ValueError(f"base inválida: {base!r}")
    if ano is not None and ano not in ANOS:
        raise ValueError(f"ano inválido: {ano!r}")
    if base == BASE_FINANCEIRO:
        return _painel_pilar_financeiro(pilar, ano, acomp)
    return _painel_pilar_fisico(pilar, tuple(anos) if anos else ano, acomp)


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
    Override manual vence o importado no ano correspondente. No acumulado,
    os ajustes anuais de meta/execução corrigem o total importado pela diferença
    para o valor original; um ajuste explícito de `ano=0` tem prioridade.
    Um intervalo anual exige dados de todos os anos selecionados, sem
    converter lacunas em zero. Projeções nunca compõem o executado.
    """
    if isinstance(referencia, tuple):
        pares = [_campos_kpi(kpi, ano) for ano in referencia]
        return tuple(sum(valores, Decimal(0)) if all(v is not None for v in valores) else None
                     for valores in zip(*pares))
    if referencia is None:
        previsto, executado = kpi.meta_total, kpi.acumulado
        ajustes_anuais = [o for o in kpi.overrides.all() if o.ano in ANOS]
        for campo, prefixo in (("previsto", "meta"), ("executado", "executado")):
            ajustes = [o for o in ajustes_anuais if o.campo == campo]
            if not ajustes:
                continue
            total = previsto if campo == "previsto" else executado
            if total is None:
                indice = 0 if campo == "previsto" else 1
                total = _somar(_campos_kpi(kpi, ano)[indice] for ano in ANOS)
            else:
                total += sum((o.valor - (getattr(kpi, f"{prefixo}_{o.ano}", None)
                                         or Decimal(0)) for o in ajustes), Decimal(0))
            if campo == "previsto":
                previsto = total
            else:
                executado = total
    else:
        previsto = getattr(kpi, f"meta_{referencia}")
        executado = getattr(kpi, f"executado_{referencia}", None)
    for override in kpi.overrides.all():
        if override.ano != (referencia or 0):
            continue
        if override.campo == "previsto":
            previsto = override.valor
        elif override.campo == "executado":
            executado = override.valor
    return previsto, executado


def _tabela_gerencial_fisica(kpis, ano):
    """Indicadores individuais dos KPIs já limitados ao escopo do painel."""
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
            linha = _linha(
                f"{kpi.nome} ({kpi.unidade})", previsto, executado,
                codigo=kpi.codigo, pilar=kpi.pilar)
            percentual_meta = percentual_fisico(executado, previsto)
            linha["pct"] = pct_inteiro(percentual_meta, 100) if percentual_meta is not None else None
            linha["saldo"] = saldo_fisico(previsto, executado)
            linha["faixa"] = faixa(percentual_meta)
            linha["valores_percentuais"] = (
                codigo in ("AT", "OUTRASFONTES") and kpi.unidade == "Percentual")
            linha["codigo_pilar"] = codigo
            linha["barra"] = min(max(linha["pct"] or 0, 0), 100)
            linhas.append(linha)
        primeiro = por_pilar[codigo][0].pilar
        titulo = ROTULOS_PAINEL.get(codigo, primeiro.nome)
        grupos.append({"codigo": codigo, "titulo": titulo, "bloco": titulo, "linhas": linhas})

    return {"grupos": grupos}


def _projecao_kpi(kpi, ano):
    for ajuste in kpi.overrides.all():
        if ajuste.ano == ano and ajuste.campo == "projetado":
            return ajuste.valor
    return getattr(kpi, f"projecao_{ano}", None)


def _tabela_anual_fisica(kpis):
    linhas = []
    for kpi in kpis:
        anos = []
        for ano in ANOS:
            meta, executado = _campos_kpi(kpi, ano)
            anos.append({"ano": ano, "meta": meta, "executado": executado,
                         "saldo": saldo_fisico(meta, executado), "projetado": _projecao_kpi(kpi, ano)})
        linhas.append({"rotulo": kpi.nome, "codigo": kpi.codigo,
                       "pilar": ROTULOS_PAINEL.get(kpi.pilar.codigo, kpi.pilar.nome),
                       "unidade": kpi.unidade, "valores_percentuais": kpi.pilar.codigo == "OUTRASFONTES",
                       "anos": anos})
    return {"linhas": linhas, "anos": ANOS}


def _painel_fisico(ano, acomp, pilares_selecionados=None):
    consulta = KpiAcompanhamento.objects.filter(acompanhamento=acomp)
    if pilares_selecionados is not None:
        consulta = consulta.filter(pilar__codigo__in=pilares_selecionados)
    kpis = list(
        consulta
        .select_related("pilar").prefetch_related("overrides").order_by("sequencia", "codigo")
    )
    grupos = _tabela_gerencial_fisica(kpis, ano)["grupos"]

    def bloco_kpis(codigos):
        """KPIs do bloco restritos à unidade majoritária (soma válida)."""
        do_bloco = [k for k in kpis if k.pilar.codigo in codigos]
        unidade = _unidade_majoritaria(do_bloco)
        return [k for k in do_bloco if k.unidade == unidade]

    def soma(sub, referencia, indice):
        return _somar([_campos_kpi(k, referencia)[indice] for k in sub])

    def serie_kpis(sub, indice):
        return _serie_anos(lambda a: soma(sub, a, indice))

    cards = []
    graficos = {}
    series = []
    for chave, codigos, nome_previsto, titulo_card, denominador in (
        ("ppi", PILARES_PPI, "Meta", "Recursos PPI executados", "projetados"),
        ("at", ("AT",), "Meta", "Captação AT executada", "captados"),
        ("outras", ("OUTRASFONTES",), "Meta", "Outras fontes executadas", "captados"),
    ):
        sub = bloco_kpis(codigos)
        previsto = soma(sub, ano, 0)
        executado = _somar(
            min(max(ex, Decimal(0)), max(pv, Decimal(0))) if pv is not None and ex is not None else None
            for pv, ex in (_campos_kpi(kpi, ano) for kpi in sub))
        valores_percentuais = (
            chave == "outras" and _unidade_majoritaria(sub) == "Percentual")
        card = _card(chave, titulo_card, executado, previsto,
                     "previstos" if valores_percentuais else denominador)
        card["valores_percentuais"] = valores_percentuais
        indicadores = [kpi for kpi in kpis if kpi.pilar.codigo in codigos]
        resumo = resumo_fisico(_campos_kpi(kpi, ano) for kpi in indicadores)
        card["resumo_indicadores"] = False
        card["execucao_limitada"] = True
        card["unidade"] = "empresas" if chave == "at" else "metas"
        card["status_counts"] = resumo
        cards.append(card)
        graficos[chave] = _bloco_grafico(
            chave, serie_kpis(sub, 0), serie_kpis(sub, 1),
            nome_previsto, "Executado", previsto, executado,
            soma(sub, None, 0), soma(sub, None, 1))
        graficos[chave]["rodape_pct"] = card["pct"]
        graficos[chave]["rodape_faixa"] = card["faixa"]
        series.append({
            "nome": {"ppi": "PPI executado",
                     "at": "Captação AT executada",
                     "outras": "Outras fontes executadas"}[chave],
             "valores": _serie_anos(lambda a: soma(sub, a, 1)),
        })

    # O consolidado soma execuções limitadas à meta, na mesma unidade.
    # As contagens de farol também incluem os indicadores percentuais.
    sub_total = bloco_kpis({kpi.pilar.codigo for kpi in kpis})
    executado_total = _somar(
        min(max(ex, Decimal(0)), max(pv, Decimal(0))) if pv is not None and ex is not None else None
        for pv, ex in (_campos_kpi(kpi, ano) for kpi in sub_total))
    cards.append(_card(
        "total", "Execução consolidada",
        executado_total, soma(sub_total, ano, 0), "previstos"))
    cards[-1]["valores_percentuais"] = _unidade_majoritaria(sub_total) == "Percentual"
    cards[-1]["status_counts"] = resumo_fisico(_campos_kpi(kpi, ano) for kpi in kpis)
    cards[-1]["execucao_limitada"] = True

    dto = _dto(
        ano if not isinstance(ano, tuple) else None, BASE_FISICO, cards, graficos, grupos, series,
        soma(sub_total, None, 1) if ano is None else None)
    dto["tabela_anual_fisica"] = _tabela_anual_fisica(kpis)
    dto["status_fisico"] = cards[-1]["status_counts"]
    return dto


# ----------------------------------------------------------------- interface

def resumo_financeiro_ciclo(acomp, pilares_selecionados=None):
    """Consolidado importado, incluindo fontes sem TAB. 1.

    Compartilha os cálculos e overrides da visão geral sem exigir PPI para
    apresentar os dados disponíveis de AT e outras fontes.
    """
    if acomp is None:
        raise ValueError("acompanhamento obrigatório")
    return _visao_financeiro_geral(acomp, pilares_selecionados)


def painel_acompanhamento(ano, base, acomp, pilares_selecionados=None, anos=None):
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
        return _painel_financeiro(ano, acomp, pilares_selecionados)
    if anos:
        if any(a not in ANOS for a in anos):
            raise ValueError("Intervalo anual inválido.")
        ano = tuple(anos)
    return _painel_fisico(ano, acomp, pilares_selecionados)
