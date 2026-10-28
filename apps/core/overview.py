"""Contexto de apresentação e seleção de pilares do Dashboard Geral."""
from django.http import QueryDict
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from .templatetags.core_extras import numero_ptbr

from apps.planning.services import ANOS, PILARES_PPI, ROTULOS_PAINEL, faixa

CODIGOS = (*PILARES_PPI, "AT", "OUTRASFONTES")


def resolver_pilares(params):
    if "filtrar_pilares" not in params:
        return None
    return [codigo for codigo in CODIGOS if codigo in params.getlist("pilares")]


def subtotal_fontes(linhas):
    totais = {}
    for campo in ("recurso", "realizado", "projetado", "combinado"):
        valores = [linha[campo] for linha in linhas if linha[campo] is not None]
        totais[campo] = sum(valores, Decimal(0)) if valores else None
    recurso, realizado = totais["recurso"], totais["realizado"]
    pct = realizado / recurso * 100 if realizado is not None and recurso is not None and recurso > 0 else None
    return {
        **totais, "rotulo": "Subtotal AT e Outras fontes", "detalhe": "AT + outras fontes", "total": True,
        "diferenca": recurso - realizado if recurso is not None and realizado is not None else None,
        "pct": pct, "faixa": faixa(pct), "barra": min(max(pct or 0, 0), 100),
    }


def _somar_presentes(valores):
    presentes = [valor for valor in valores if valor is not None]
    return sum(presentes, Decimal(0)) if presentes else None


def _indicador_meta(rotulo, meta, valor, total=False):
    pct = valor / meta * 100 if valor is not None and meta is not None and meta > 0 else None
    return {
        "rotulo": rotulo, "recurso": meta, "realizado": valor, "total": total,
        "diferenca": meta - valor if meta is not None and valor is not None else None,
        "pct": pct, "pct_exibicao": pct.quantize(Decimal("0.01"), rounding=ROUND_DOWN) if pct is not None else None,
        "faixa": faixa(pct), "barra": min(max(pct or 0, 0), 100),
    }


def _resumo_financeiro(painel):
    originais = {card["chave"]: card for card in painel["cards"]}
    fontes = {fonte["codigo"]: fonte for fonte in painel.get("fontes", [])}
    cards = []
    ppi = originais["ppi"]
    especificacoes = [
        ("ppi", "Recurso PPI realizado", ppi["executado"], ppi["previsto"], "do PPI", "executado"),
    ]
    for codigo, chave in (("AT", "at"), ("OUTRASFONTES", "outras")):
        fonte = fontes.get(codigo, {})
        # O plano legado não possui metas de captação pactuadas.
        origem = originais[chave]
        realizado = fonte.get("realizado") if "fontes" in painel else origem["executado"]
        captado = fonte.get("captado") if "fontes" in painel else origem["previsto"]
        meta = fonte.get("meta")
        especificacoes.extend([
            (chave, "Realizado AT" if chave == "at" else "Outras fontes realizado", realizado, meta, "da meta", "executado"),
            (chave + "-captado", "Recurso captado AT" if chave == "at" else "Outras fontes captado", captado, meta, "da meta", "captado"),
        ])
    realizados = [especificacoes[i][2] for i in (0, 1, 3)]
    metas = [especificacoes[i][3] for i in (0, 1, 3)]
    especificacoes.append(("total", "Realizado consolidado", _somar_presentes(realizados),
                           _somar_presentes(metas), "previstos", "executado"))
    for chave, titulo, valor, meta, denominador, indicador in especificacoes:
        linha = _indicador_meta(titulo, meta, valor)
        cards.append({
            **linha, "chave": chave, "titulo_exibicao": titulo, "executado": valor,
            "previsto": meta, "denominador": denominador, "indicador": indicador,
            "valores_em_reais": ppi.get("valores_em_reais", False),
        })
    painel["cards_resumo"] = cards

    tabelas = []
    for campo, nome, percentual in (("captado", "Captação", "% captado total"),
                                     ("realizado", "Execução", "% executado")):
        linhas = [_indicador_meta(f["rotulo"], f["meta"], f[campo]) for f in fontes.values()]
        total = _indicador_meta("Consolidado",
            _somar_presentes(l["recurso"] for l in linhas),
            _somar_presentes(l["realizado"] for l in linhas), total=True)
        tabelas.append({
            "chave": campo, "titulo": nome + " · AT e outras fontes",
            "coluna_meta": "Meta de " + nome.lower(),
            "coluna_valor": "Recurso captado total" if campo == "captado" else "Recurso realizado",
            "coluna_diferenca": "Diferença " + nome.lower(),
            "coluna_pct": percentual, "coluna_farol": "Farol " + nome.lower(),
            "linhas": linhas, "total": total,
        })
    painel["tabelas_fontes"] = tabelas


def contexto_visao_geral(contexto, selecionados=None):
    painel = contexto["painel"]
    selecionados = list(CODIGOS) if selecionados is None else selecionados
    painel["pilares_selecionados"] = selecionados
    painel["cards_resumo"] = [painel["cards"][i] for i in (3, 0, 1, 2)]
    if contexto["base_param"] == "fin":
        _resumo_financeiro(painel)
        for card in painel["cards_resumo"]:
            valor = card["executado"]
            divisor = Decimal("1000000") if valor is not None and abs(valor) >= 1000000 else Decimal("1000") if valor is not None and abs(valor) >= 1000 else Decimal(1)
            if not card.get("valores_em_reais"):
                divisor = Decimal(1)
            card["valor_numero"] = numero_ptbr((valor / divisor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) if valor is not None else "—"
            card["valor_unidade"] = "milhões" if divisor == 1000000 or not card.get("valores_em_reais") else "mil" if divisor == 1000 else ""
            prev = card["previsto"]
            div_prev = Decimal("1000000") if card.get("valores_em_reais") and prev is not None and abs(prev) >= 1000000 else Decimal("1000") if card.get("valores_em_reais") and prev is not None and abs(prev) >= 1000 else Decimal(1)
            unidade_prev = " milhões" if div_prev == 1000000 or not card.get("valores_em_reais") else " mil" if div_prev == 1000 else ""
            if prev is not None:
                previsto_escalado = (prev / div_prev).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                card["previsto_fmt"] = "R$ " + numero_ptbr(previsto_escalado) + unidade_prev
            else:
                card["previsto_fmt"] = "—"
    for grupo in painel["tabela"]["grupos"]:
        for linha in grupo["linhas"]:
            linha["barra"] = min(max(linha.get("pct") or 0, 0), 100)
    for chave in ("tabela_tab1", "tabela_programa"):
        for linha in painel.get(chave, {}).get("linhas", []):
            linha["barra"] = min(max(linha.get("pct") or 0, 0), 100)
    if painel.get("tabela_programa"):
        tabela = painel["tabela_programa"]
        subtotal = dict(painel["tabela_tab1"]["total"], rotulo="Subtotal PPI", detalhe="")
        tabela["grupos"] = [{"codigo": "ppi", "titulo": "Recursos PPI", "linhas": [*painel["tabela_tab1"]["linhas"][:-1], subtotal]}]
        subtotal["pct_exibicao"] = subtotal["pct"].quantize(Decimal("0.01"), rounding=ROUND_DOWN) if subtotal["pct"] is not None else None
        tabela["resumo_ppi"] = subtotal
    tabela_anual = painel.get("tabela_tab11", {})
    tabela_anual["sem_dados_anuais"] = not any(
        linha[campo] is not None
        for linha in tabela_anual.get("linhas", []) if not linha["total"]
        for campo in ("meta_2024", "meta_2025", "meta_2026",
                      "realizado_2024", "realizado_2025", "realizado_2026",
                      "projetado_2026", "projetado_2027")
    )
    acompanhamento = contexto.get("acompanhamento")
    importacao = None
    if acompanhamento is not None:
        tipo_fonte = "FINANCEIRO_GERAL" if contexto["base_param"] == "fin" else "INDICADORES_PE"
        importacao = acompanhamento.importacoes.filter(
            status="SUCESSO", tipo_fonte=tipo_fonte).first()
        if importacao is None:
            importacao = acompanhamento.importacoes.filter(status="SUCESSO").first()
    if importacao:
        nome_arquivo = importacao.arquivo_nome.replace("\\", "/").rsplit("/", 1)[-1]
        contexto["fonte_dashboard"] = (
            {"FINANCEIRO_GERAL": "FINANCEIRO GERAL - REFAT.xlsx", "INDICADORES_PE": "Indicadores Gerais do Termo de Retificação do PE"}.get(importacao.tipo_fonte, importacao.get_tipo_fonte_display()) if nome_arquivo.lower().startswith("tmp") else nome_arquivo
        )
    else:
        contexto["fonte_dashboard"] = "Acompanhamento" if acompanhamento else "Plano anual"
    contexto["opcoes_pilares"] = [
        {"codigo": codigo, "rotulo": ROTULOS_PAINEL[codigo],
         "selecionado": codigo in selecionados}
        for codigo in CODIGOS
    ]
    contexto["todos_pilares"] = len(selecionados) == len(CODIGOS)
    contexto["quantidade_pilares"] = len(selecionados)
    ano = painel["ano"]
    contexto["inicio_periodo"] = f"01/{ano}" if ano else "Ciclo completo"
    contexto["fim_periodo"] = f"12/{ano}" if ano else "Ciclo completo"
    contexto["anos_dashboard"] = ANOS
    params = QueryDict(mutable=True)
    params["ano"] = contexto["ano_param"]
    params["filtrar_pilares"] = "1"
    params["mes_inicial"] = contexto.get("mes_inicial", "")
    params["mes_final"] = contexto.get("mes_final", "")
    params.setlist("pilares", selecionados)
    if acompanhamento is not None:
        params["acompanhamento"] = str(acompanhamento.pk)
    contexto["filtros_dashboard"] = params.urlencode()
    return contexto
