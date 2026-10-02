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

from .models import (
    Acompanhamento,
    KpiAcompanhamento,
    ProjetoFinanceiro,
    ResumoFinanceiro,
)
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
        if override.campo not in ("previsto", "executado"):
            continue
        par = list(anual.get((override.pilar.codigo, override.ano), (None, None)))
        par[0 if override.campo == "previsto" else 1] = override.valor
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


def _visao_financeiro_geral(acomp):
    """Valores do ciclo completo das TAB. 1, 1.1 e 9, sem inferir anos da TAB. 9."""
    resumos = ResumoFinanceiro.objects.filter(
        acompanhamento=acomp, origem__in=("TAB. 1", "TAB. 1.1", "TAB. 9"),
    ).select_related("pilar")
    por_chave = {(r.origem, r.pilar.codigo, r.ano): r for r in resumos}

    def resumo(origem, codigo, ano=None):
        return por_chave.get((origem, codigo, ano))

    def campo(linha, nome):
        return getattr(linha, nome) if linha is not None else None

    linhas_tab1 = []
    linhas_tab11 = []
    for codigo, rotulo in ROTULOS_TAB_PPI:
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
        if tab11 is None:
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
        meta = linha.recurso_ou_meta if linha is not None else None
        captado = linha.captado if linha is not None else None
        realizado = linha.realizado if linha is not None else None
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
    return {"tabela_tab1": {"linhas": linhas_tab1, "total": linhas_tab1[-1]},
            "tabela_tab11": {"linhas": linhas_tab11, "total": linhas_tab11[-1]}, "graficos_ciclo": graficos}


def _painel_financeiro(ano, acomp):
    consolidado, anual = _resumos_financeiros(acomp)
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
        dto.update(_visao_financeiro_geral(acomp))
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
_COLUNAS_PROJETOS_PDI = (
    ("nome", "PROJETO", "texto"),
    ("status", "STATUS", "texto"),
    ("inicio", "INICIO", "data"),
    ("fim", "FINAL", "data"),
    ("orcado", "ORÇADO SÍNTESE", "dinheiro"),
    ("realizado", "REALIZADO", "dinheiro"),
    ("projetado_2026", "PROJETADO 2026", "dinheiro"),
    ("projetado_2027", "PROJETADO 2027", "dinheiro"),
    ("realizado_mais_projetado", "REALIZADO + PROJETADO", "dinheiro"),
    ("diferenca", "DIFERENÇA ORÇADO", "dinheiro"),
    ("percentual", "% REALIZADO ORÇADO", "percentual"),
)


def _tabela_pdi(nome, colunas, registros):
    linhas = []
    for registro in registros:
        celulas = []
        for campo, _cabecalho, tipo in colunas:
            valor = registro.get(campo)
            if tipo == "percentual" and valor is not None:
                valor *= 100
            celulas.append({"tipo": tipo, "valor": valor})
        linhas.append({"celulas": celulas, "total": registro.get("total", False)})
    return {"nome": nome, "cabecalhos": [c[1] for c in colunas], "linhas": linhas}


def painel_pdi_financeiro(pilar, acomp):
    """Visão integral das tabelas PDI do snapshot, sem recortes por ano.

    TAB. 3 corresponde a tbl_VisaoPDI; a diferença é apresentada em módulo.
    TAB. 2 corresponde a tbl_ProjetosPDI. O PK preserva a ordem de inclusão
    das linhas, inclusive nos arquivos PDI sem coluna ITEM.
    """
    resumo = ResumoFinanceiro.objects.filter(
        acompanhamento=acomp, pilar=pilar, origem="TAB. 3", ano__isnull=True,
    ).values(*(c[0] for c in _COLUNAS_VISAO_PDI if c[0] != "rotulo")).first()
    projetos = list(ProjetoFinanceiro.objects.filter(
        acompanhamento=acomp, pilar=pilar, origem="TAB. 2",
    ).order_by("pk").values(*(c[0] for c in _COLUNAS_PROJETOS_PDI)))
    recurso = resumo.get("recurso_ou_meta") if resumo else None
    realizado = resumo.get("realizado") if resumo else None
    diferenca_importada = resumo.get("diferenca") if resumo else None
    diferenca = abs(diferenca_importada) if diferenca_importada is not None else None
    pct = pct_inteiro(realizado, recurso) if realizado is not None else None
    faixa_execucao = faixa(percentual(realizado, recurso)) if pct is not None else "neutra"
    cards = [
        _card_pilar("previsto", "RECURSO PPI AFCCT / PDI", recurso, recurso, "do PPI", False),
        _card_pilar("executado", "REALIZADO", realizado, recurso, "do PPI", realizado is not None),
        _card_pilar("saldo", "DIF.  REL. AO  PPI", diferenca, recurso, "do PPI", diferenca is not None),
    ]
    cards[0]["ocultar_progresso"] = True
    cards[2]["rotulo_percentual"] = "do recurso PPI"
    for card in cards:
        card.update(valores_em_reais=True, precisao_financeira=True)
    linhas_projetos = list(projetos)
    if projetos:
        total = {campo: _somar(p[campo] for p in projetos)
                 for campo, _cabecalho, tipo in _COLUNAS_PROJETOS_PDI if tipo == "dinheiro"}
        total.update(nome="TOTAL GERAL", total=True)
        linhas_projetos.append(total)
    return {
        "pilar": pilar, "codigo": "PDI", "rotulo": ROTULOS_PAINEL["PDI"],
        "ano": None, "base": BASE_FINANCEIRO, "unidade": "R$",
        "rotulo_periodo": "Acumulado do ciclo completo",
        "rotulo_previsto": "RECURSO PPI AFCCT / PDI", "denominador": "do PPI",
        "previsto": recurso, "executado": realizado, "saldo": diferenca,
        "pct": pct, "faixa": faixa_execucao, "cards": cards,
        "serie_previsto": [None] * len(ANOS), "serie_executado": [None] * len(ANOS),
        "tabela": [], "projetos": len(projetos), "unidade_projetos": "projetos",
        "valores_em_reais": True, "visao_pdi": True,
        "tabela_visao_pdi": _tabela_pdi(
            "tbl_VisaoPDI", _COLUNAS_VISAO_PDI,
            [{**resumo, "rotulo": "RECURSO PPI", "diferenca": diferenca}] if resumo else [],
        ),
        "tabela_projetos_pdi": _tabela_pdi(
            "tbl_ProjetosPDI", _COLUNAS_PROJETOS_PDI, linhas_projetos,
        ),
    }


def _painel_pilar_financeiro(pilar, ano, acomp):
    if pilar.codigo == "PDI":
        return painel_pdi_financeiro(pilar, acomp)
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


def _painel_pilar_fisico(pilar, ano, acomp):
    kpis = list(
        KpiAcompanhamento.objects.filter(
            acompanhamento=acomp, pilar=pilar
        ).prefetch_related("overrides").order_by("sequencia", "codigo")
    )
    unidade = _unidade_majoritaria(kpis)
    sub = [kpi for kpi in kpis if kpi.unidade == unidade]

    def soma(referencia, indice):
        return _somar([_campos_kpi(kpi, referencia)[indice] for kpi in sub])

    serie_previsto = [soma(ano_coluna, 0) for ano_coluna in ANOS]
    serie_executado = [soma(ano_coluna, 1) for ano_coluna in ANOS]
    acumulado_previsto, acumulado_executado = soma(None, 0), soma(None, 1)
    if ano is None:
        previsto, executado = acumulado_previsto, acumulado_executado
    else:
        previsto = serie_previsto[ANOS.index(ano)]
        executado = serie_executado[ANOS.index(ano)]
    saldo = None if previsto is None or executado is None else previsto - executado
    pct = pct_inteiro(executado, previsto)
    rotulo_previsto = "Meta"
    cards = [
        _card_pilar("previsto", rotulo_previsto, previsto, previsto, "projetados", False),
        _card_pilar("executado", "Executado", executado, previsto, "projetados"),
        _card_pilar("saldo", "Saldo a executar", saldo, previsto, "restantes", False),
        {**_card_pilar("percentual", "% Executado", executado, previsto, "projetados"),
         "executado": None},
    ]
    tabela = []
    for indice, ano_coluna in enumerate(ANOS):
        pv, ex = serie_previsto[indice], serie_executado[indice]
        pp = pct_inteiro(ex, pv)
        tabela.append({
            "rotulo": f"Ano {indice + 1}: {ano_coluna}",
            "previsto": pv,
            "executado": ex,
            "saldo": None if pv is None or ex is None else pv - ex,
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
    bloco = {
        "pilar": pilar,
        "codigo": pilar.codigo,
        "rotulo": ROTULOS_PAINEL.get(pilar.codigo, pilar.nome),
        "ano": ano,
        "base": BASE_FISICO,
        "unidade": "metas",
        "rotulo_periodo": _rotulo_periodo(ano),
        "rotulo_previsto": rotulo_previsto,
        "denominador": "projetados",
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
        },
        "rodape_pct": pct,
        "rodape_faixa": "neutra" if pct is None else faixa(
            percentual(executado, previsto)
        ),
        "tabela": tabela,
        "projetos": ProjetoFinanceiro.objects.filter(
            acompanhamento=acomp, pilar=pilar
        ).count(),
        "unidade_projetos": "projetos",
    }
    return bloco


def painel_pilar_acompanhamento(pilar, ano, base, acomp):
    """DTO do pilar usando o acompanhamento importado selecionado."""
    base = BASES_CANONICAS.get(base)
    if base not in (BASE_FINANCEIRO, BASE_FISICO):
        raise ValueError(f"base inválida: {base!r}")
    if ano is not None and ano not in ANOS:
        raise ValueError(f"ano inválido: {ano!r}")
    if base == BASE_FINANCEIRO:
        return _painel_pilar_financeiro(pilar, ano, acomp)
    return _painel_pilar_fisico(pilar, ano, acomp)


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
        previsto, executado = soma(sub, ano, 0), soma(sub, ano, 1)
        cards.append(_card(chave, titulo_card, executado, previsto, denominador))
        graficos[chave] = _bloco_grafico(
            chave, serie_kpis(sub, 0), serie_kpis(sub, 1),
            nome_previsto, "Executado", previsto, executado,
            soma(sub, None, 0), soma(sub, None, 1))
        series.append({
            "nome": {"ppi": "PPI executado",
                     "at": "Captação AT executada",
                     "outras": "Outras fontes executadas"}[chave],
             "valores": _serie_anos(lambda a: soma(sub, a, 1)),
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
