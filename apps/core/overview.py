"""Contexto de apresentação e seleção de pilares do Dashboard Geral."""
from django.http import QueryDict

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
    for grupo in painel["tabela"]["grupos"]:
        for linha in grupo["linhas"]:
            linha["barra"] = min(max(linha.get("pct") or 0, 0), 100)
    for linha in painel.get("tabela_tab1", {}).get("linhas", []):
        linha["barra"] = min(max(linha.get("pct") or 0, 0), 100)
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
            importacao.get_tipo_fonte_display() if nome_arquivo.lower().startswith("tmp") else nome_arquivo
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
    params.setlist("pilares", selecionados)
    if acompanhamento is not None:
        params["acompanhamento"] = str(acompanhamento.pk)
    contexto["filtros_dashboard"] = params.urlencode()
    return contexto
