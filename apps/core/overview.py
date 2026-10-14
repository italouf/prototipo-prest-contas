"""Contexto de apresentação e seleção de pilares do Dashboard Geral."""
from django.http import QueryDict
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from .templatetags.core_extras import numero_curto, _numero_brl

from apps.planning.services import ANOS, PILARES_PPI, ROTULOS_PAINEL

CODIGOS = (*PILARES_PPI, "AT", "OUTRASFONTES")


def resolver_pilares(params):
    if "filtrar_pilares" not in params:
        return None
    return [codigo for codigo in CODIGOS if codigo in params.getlist("pilares")]


def contexto_visao_geral(contexto, selecionados=None):
    painel = contexto["painel"]
    selecionados = list(CODIGOS) if selecionados is None else selecionados
    painel["pilares_selecionados"] = selecionados
    painel["cards_resumo"] = [painel["cards"][i] for i in (3, 0, 1, 2)]
    if contexto["base_param"] == "fin":
        for card in painel["cards"]:
            valor = card["executado"]
            divisor = Decimal("1000000") if valor is not None and abs(valor) >= 1000000 else Decimal("1000") if valor is not None and abs(valor) >= 1000 else Decimal(1)
            if not card.get("valores_em_reais"):
                divisor = Decimal(1)
            card["valor_numero"] = _numero_brl((valor / divisor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), 2) if valor is not None else "—"
            card["valor_unidade"] = "mi" if divisor == 1000000 or not card.get("valores_em_reais") else "mil" if divisor == 1000 else ""
            prev = card["previsto"]
            div_prev = Decimal("1000000") if card.get("valores_em_reais") and prev is not None and abs(prev) >= 1000000 else Decimal("1000") if card.get("valores_em_reais") and prev is not None and abs(prev) >= 1000 else Decimal(1)
            unidade_prev = " mi" if div_prev == 1000000 or not card.get("valores_em_reais") else " mil" if div_prev == 1000 else ""
            card["previsto_fmt"] = "R$ " + _numero_brl((prev / div_prev).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), 2) + unidade_prev if prev is not None else "—"
    for grupo in painel["tabela"]["grupos"]:
        for linha in grupo["linhas"]:
            linha["barra"] = min(max(linha.get("pct") or 0, 0), 100)
    for chave in ("tabela_tab1", "tabela_programa"):
        for linha in painel.get(chave, {}).get("linhas", []):
            linha["barra"] = min(max(linha.get("pct") or 0, 0), 100)
    if painel.get("tabela_programa"):
        tabela = painel["tabela_programa"]
        subtotal = dict(painel["tabela_tab1"]["total"], rotulo="Subtotal PPI", detalhe="recurso EMBRAPII")
        tabela["grupos"] = [{"codigo": "ppi", "titulo": "Recursos PPI", "linhas": [*painel["tabela_tab1"]["linhas"][:-1], subtotal]}]
        for codigo, rotulo in (("at", "AT"), ("outras", "Outras fontes")):
            linhas = [dict(linha, detalhe="base = valor captado", rotulo="Associação Tecnológica (AT)" if codigo == "at" else "Outras fontes")
                      for linha in tabela["linhas"] if linha["rotulo"] == rotulo]
            if linhas:
                tabela["grupos"].append({"codigo": codigo, "titulo": "Associação Tecnológica (AT)" if codigo == "at" else "Outras fontes", "linhas": linhas})
        total = tabela["total"]
        total.update(rotulo="Consolidado", detalhe="PPI + AT + outras fontes")
        total["pct_exibicao"] = total["pct"].quantize(Decimal("0.01"), rounding=ROUND_DOWN) if total["pct"] is not None else None
    tabela_anual = painel.get("tabela_tab11", {})
    tabela_anual["sem_dados_anuais"] = not any(
        linha[campo] is not None
        for linha in tabela_anual.get("linhas", []) if not linha["total"]
        for campo in ("realizado_2024", "realizado_2025", "realizado_2026",
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
