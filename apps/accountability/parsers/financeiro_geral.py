"""Parser de ``FINANCEIRO GERAL.xlsx`` — mapas tabulares TAB. 1 a TAB. 9 (SDD §4).

Leitura posicional validada: os títulos ``TAB. n`` são localizados na aba,
o cabeçalho de colunas é conferido antes de ler e rótulos de pilar
desconhecidos viram erro citando a célula. Totais de reconciliação
(TAB. 3/5/8) nunca são somados aos blocos por pilar: são linhas próprias
com ``origem`` distinta. ``TAB. 7`` é opcional e, quando ausente, só avisa.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from openpyxl.utils import get_column_letter

from apps.accountability.parsers.comum import (
    abrir_workbook,
    eh_erro_formula,
    normalizar,
    novo_payload,
    para_decimal,
    para_dinheiro,
    texto_limpo,
)

_TITULO_BLOCO = re.compile(r"^tab\.\s*(\d+(?:\.\d+)?)\D")

# Rótulos de pilar aceitos (SDD §4), comparados sem espaços.
_ROTULO_PILAR = {
    "afcct/pd&i": "PDI",
    "afcct/pdi": "PDI",  # variante usada nos títulos TAB. 2/3 (sem "&")
    "fcrh": "FORMACAO",
    "acs": "STARTUPS",
    "infraestrutura": "INFRA",
    "associacaotecnologica": "AT",
    "outrasfontes": "OUTRASFONTES",
}

_CABECALHO_ESPERADO = {
    "TAB. 1": "ação",
    "TAB. 1.1": "ação",
    "TAB. 9": "pilar",
    "TAB. 2": "projeto",
    "TAB. 4": "projeto",
    "TAB. 6": "projeto",
}

_PILAR_BLOCO_PROJETO = {
    "TAB. 2": "PDI",
    "TAB. 4": "FORMACAO",
    "TAB. 6": "STARTUPS",
}

_BLOCOS_OBRIGATORIOS = (
    "TAB. 1", "TAB. 1.1", "TAB. 2", "TAB. 3",
    "TAB. 4", "TAB. 5", "TAB. 6", "TAB. 8", "TAB. 9",
)

# Campo do dict -> (coluna, tipo de leitura).
_COLUNAS_RESUMO_TAB1 = {
    "recurso_ou_meta": ("D", "dinheiro"),
    "realizado": ("E", "dinheiro"),
    "projetado": ("F", "dinheiro"),
    "realizado_mais_projetado": ("G", "dinheiro"),
    "diferenca": ("H", "dinheiro"),
    "percentual": ("I", "percentual"),
    "farol": ("J", "texto"),
}
_COLUNAS_RESUMO_TAB11 = {
    "recurso_ou_meta": ("N", "dinheiro"),
    "realizado_mais_projetado": ("T", "dinheiro"),
    "diferenca": ("U", "dinheiro"),
    "percentual": ("V", "percentual"),
    "farol": ("W", "texto"),
}
# Colunas anuais de TAB. 1.1: (coluna, ano, campo). "S" ("projetado total")
# nunca vira ano — alimenta a linha consolidada (ano=None) do pilar.
_ANUAIS_TAB11 = (
    ("O", 2024, "realizado"),
    ("P", 2025, "realizado"),
    ("Q", 2026, "realizado"),
    ("R", 2026, "projetado"),
)
_COLUNAS_RESUMO_RECONCILIACAO = {
    "recurso_ou_meta": ("D", "dinheiro"),
    "realizado": ("E", "dinheiro"),
    "projetado": ("F", "dinheiro"),
    "realizado_mais_projetado": ("G", "dinheiro"),
    "diferenca": ("H", "dinheiro"),
}
_COLUNAS_RESUMO_TAB9 = {
    "recurso_ou_meta": ("D", "dinheiro"),
    "captado_anos_1_2": ("E", "dinheiro"),
    "captado_ano3_ytd": ("F", "dinheiro"),
    "captado": ("G", "dinheiro"),
    "realizado": ("H", "dinheiro"),
    "percentual_meta": ("I", "percentual"),
    "percentual_captado": ("J", "percentual"),
}
_COLUNAS_PROJETO_TAB24 = {
    "sequencia": ("B", "inteiro"),
    "nome": ("C", "texto"),
    "status": ("D", "texto"),
    "inicio": ("E", "data"),
    "fim": ("F", "data"),
    "orcado": ("G", "dinheiro"),
    "realizado": ("H", "dinheiro"),
    "projetado_2026": ("I", "dinheiro"),
    "projetado_2027": ("J", "dinheiro"),
    "realizado_mais_projetado": ("K", "dinheiro"),
    "diferenca": ("L", "dinheiro"),
    "percentual": ("M", "percentual"),
}
_COLUNAS_PROJETO_TAB6 = {
    "sequencia": ("B", "inteiro"),
    "nome": ("C", "texto"),
    "status": ("D", "texto"),
    "fim": ("E", "data"),
    "orcado": ("F", "dinheiro"),
    "realizado": ("G", "dinheiro"),
    "projetado_2026": ("H", "dinheiro"),
    "projetado_2027": ("I", "dinheiro"),
    "realizado_mais_projetado": ("J", "dinheiro"),
    "diferenca": ("K", "dinheiro"),
    "percentual": ("L", "percentual"),
}

_CAMPOS_RESUMO = (
    "recurso_ou_meta", "captado_anos_1_2", "captado_ano3_ytd", "captado",
    "realizado", "projetado", "realizado_mais_projetado", "diferenca",
    "percentual", "percentual_meta", "percentual_captado", "farol",
)
_CAMPOS_PROJETO = (
    "sequencia", "nome", "status", "inicio", "fim", "orcado", "realizado",
    "projetado_2026", "projetado_2027", "realizado_mais_projetado",
    "diferenca", "percentual",
)


def parse_financeiro_geral(caminho: Path | str) -> dict:
    """Lê ``FINANCEIRO GERAL.xlsx`` e devolve o payload padrão de ingestão.

    O payload tem o mesmo shape de ``comum.PAYLOAD_VAZIO``; o parser é puro e
    não toca no banco. Falha de leitura do arquivo propaga
    ``comum.ArquivoInvalidoError``.
    """
    payload = novo_payload()
    wb = abrir_workbook(caminho)
    try:
        if len(wb.sheetnames) != 1 or not normalizar(wb.sheetnames[0]).startswith("financeiro"):
            payload["erros"].append(
                "A aba \"FINANCEIRO \" não foi encontrada"
                f" (abas lidas: {', '.join(repr(a) for a in wb.sheetnames)})."
                " Verifique se é o template correto da EMBRAPII."
            )
            return payload
        aba = wb.sheetnames[0]
        ws = wb[aba]
        celulas, max_linha = _ler_celulas(ws)
    finally:
        wb.close()

    titulos = _titulos_de_bloco(celulas)
    for origem in _BLOCOS_OBRIGATORIOS:
        if origem not in titulos:
            payload["erros"].append(
                f"A aba \"{aba}\" não contém o bloco {origem}."
                " Verifique se é o template correto da EMBRAPII."
            )
    if "TAB. 7" not in titulos:
        payload["avisos"].append("TAB. 7 não encontrada; ignorada.")

    for origem, (linha_titulo, celula_titulo) in sorted(
            titulos.items(), key=lambda item: item[1][0]):
        limite = _limite_do_bloco(origem, titulos, max_linha)
        if origem in ("TAB. 1", "TAB. 1.1", "TAB. 9"):
            _ler_bloco_tabular(
                payload, celulas, origem, linha_titulo, limite, aba)
        elif origem in ("TAB. 3", "TAB. 5", "TAB. 8"):
            _ler_bloco_reconciliacao(
                payload, celulas, origem, linha_titulo, celula_titulo, limite, aba)
        elif origem in ("TAB. 2", "TAB. 4", "TAB. 6"):
            _ler_bloco_projetos(
                payload, celulas, origem, linha_titulo, limite, aba)

    if "TAB. 1.1" in titulos and not any(
            r["ano"] is not None for r in payload["resumos"]):
        payload["avisos"].append(
            "TAB. 1.1 sem valores anuais por pilar; a visão anual exibirá —")
    return payload


# ---------------------------------------------------------------- leitura base

def _ler_celulas(ws) -> tuple[dict[str, Any], int]:
    """Células não vazias por coordenada (``"C5"``) e a última linha usada."""
    celulas: dict[str, Any] = {}
    max_linha = 0
    for linha in ws.iter_rows():
        for celula in linha:
            if celula.value is not None:
                celulas[celula.coordinate] = celula.value
                max_linha = max(max_linha, celula.row)
    return celulas, max_linha


def _coord(coluna: str, linha: int) -> str:
    return f"{coluna}{linha}"


def _titulos_de_bloco(celulas: dict[str, Any]) -> dict[str, tuple[int, str]]:
    """Primeira ocorrência de cada ``TAB. n`` como (linha, coordenada)."""
    achados: dict[str, tuple[int, str]] = {}
    for coordenada in sorted(celulas, key=_chave_de_coordenada):
        match = _TITULO_BLOCO.match(normalizar(celulas[coordenada]))
        if not match:
            continue
        origem = f"TAB. {match.group(1)}"
        if origem not in achados:
            _, linha = _separar_coordenada(coordenada)
            achados[origem] = (linha, coordenada)
    return achados


def _chave_de_coordenada(coordenada: str) -> tuple[int, int]:
    coluna, linha = _separar_coordenada(coordenada)
    return (linha, _numero_de_coluna(coluna))


def _separar_coordenada(coordenada: str) -> tuple[str, int]:
    match = re.fullmatch(r"([A-Z]+)(\d+)", coordenada)
    if match is None:
        raise ValueError(f"Coordenada inválida: {coordenada}")
    return match.group(1), int(match.group(2))


def _numero_de_coluna(coluna: str) -> int:
    numero = 0
    for caractere in coluna:
        numero = numero * 26 + (ord(caractere) - ord("A") + 1)
    return numero


def _limite_do_bloco(
    origem: str,
    titulos: dict[str, tuple[int, str]],
    max_linha: int,
) -> int:
    """Última linha do bloco: a linha anterior ao próximo título (ou o fim)."""
    linha_titulo = titulos[origem][0]
    posteriores = [
        linha for outra, (linha, _) in titulos.items()
        if outra != origem and linha > linha_titulo
    ]
    return (min(posteriores) - 1) if posteriores else max_linha


def _linha_vazia(
    celulas: dict[str, Any], linha: int, primeira: str, ultima: str
) -> bool:
    """``True`` quando nenhuma célula do intervalo de colunas tem valor."""
    return not any(
        _coord(get_column_letter(col), linha) in celulas
        for col in range(_numero_de_coluna(primeira), _numero_de_coluna(ultima) + 1)
    )


def _valor(
    celulas: dict[str, Any],
    coordenada: str,
    tipo: str,
    aba: str,
    erros: list[str],
) -> Any:
    """Converte uma célula pelo tipo do campo; vazio ⇒ ``None``.

    Texto não numérico em campo monetário/percentual vira erro citando aba,
    linha e coluna (SDD §7); marcadores ``-`` contam como vazio.
    """
    bruto = celulas.get(coordenada)
    if bruto is None:
        return None
    if tipo == "texto":
        return texto_limpo(bruto)
    if tipo == "data":
        return _para_data(bruto)
    if tipo == "inteiro":
        numero = para_decimal(bruto)
        return int(numero) if numero is not None else None
    if isinstance(bruto, str) and texto_limpo(bruto) in ("-", "–", "—"):
        return None
    numero = para_dinheiro(bruto) if tipo == "dinheiro" else para_decimal(bruto)
    if numero is None:
        problema = "erro de fórmula" if eh_erro_formula(bruto) else "valor não numérico"
        erros.append(
            f"Aba \"{aba}\", célula {coordenada}: {problema} "
            f"\"{texto_limpo(bruto)}\".")
    return numero


def _para_data(bruto: object) -> date | None:
    if isinstance(bruto, datetime):
        return bruto.date()
    if isinstance(bruto, date):
        return bruto
    return None


def _codigo_pilar(rotulo: object) -> str | None:
    return _ROTULO_PILAR.get(normalizar(rotulo).replace(" ", ""))


def _montar(
    campos: tuple[str, ...],
    origem: str,
    pilar: str | None,
    valores: dict[str, Any],
    ano: int | None = None,
) -> dict:
    linha = {campo: None for campo in campos}
    linha.update({"origem": origem, "pilar": pilar, "ano": ano})
    linha.update(valores)
    return linha


# --------------------------------------------------------------- blocos TAB. 1

def _ler_bloco_tabular(
    payload: dict,
    celulas: dict[str, Any],
    origem: str,
    linha_titulo: int,
    limite: int,
    aba: str,
) -> None:
    """TAB. 1 / TAB. 1.1 / TAB. 9: pilar na primeira coluna do bloco."""
    coluna_pilar = {"TAB. 1": "C", "TAB. 1.1": "M", "TAB. 9": "C"}[origem]
    colunas = {
        "TAB. 1": ("C", "J", _COLUNAS_RESUMO_TAB1),
        "TAB. 1.1": ("M", "W", _COLUNAS_RESUMO_TAB11),
        "TAB. 9": ("C", "J", _COLUNAS_RESUMO_TAB9),
    }[origem]
    primeira, ultima, mapa = colunas

    cabecalho = _proxima_linha_preenchida(celulas, coluna_pilar, linha_titulo, limite)
    if cabecalho is None:
        payload["erros"].append(
            f"Aba \"{aba}\": cabeçalho esperado "
            f"'{_CABECALHO_ESPERADO[origem]}' para {origem} não encontrado.")
        return
    esperado = _CABECALHO_ESPERADO[origem]
    if normalizar(celulas[_coord(coluna_pilar, cabecalho)]) != normalizar(esperado):
        payload["erros"].append(
            f"Aba \"{aba}\": cabeçalho esperado '{esperado}' para {origem} "
            f"na linha {cabecalho}.")
        return

    for linha in range(cabecalho + 2, limite + 1):
        if _linha_vazia(celulas, linha, primeira, ultima):
            continue
        celula_pilar = _coord(coluna_pilar, linha)
        if normalizar(celulas.get(celula_pilar)).startswith("total"):
            break
        pilar = _resolver_pilar(payload, celulas, celula_pilar, origem, aba)
        if origem == "TAB. 1.1":
            _emitir_tab11(payload, celulas, origem, pilar, linha, mapa, aba)
            continue
        valores = {
            campo: _valor(celulas, _coord(col, linha), tipo, aba, payload["erros"])
            for campo, (col, tipo) in mapa.items()
        }
        payload["resumos"].append(_montar(_CAMPOS_RESUMO, origem, pilar, valores))


def _emitir_tab11(
    payload: dict,
    celulas: dict[str, Any],
    origem: str,
    pilar: str | None,
    linha: int,
    mapa: dict[str, tuple[str, str]],
    aba: str,
) -> None:
    """TAB. 1.1 só gera linhas quando há valor em ``O:S`` no pilar.

    Linhas ``ano`` vêm só de O/P/Q/R; ``S`` ("projetado total") alimenta uma
    linha consolidada por pilar (``ano=None``) com N/T/U/V/W (SDD §4).
    """
    valores = {
        campo: _valor(celulas, _coord(col, linha), tipo, aba, payload["erros"])
        for campo, (col, tipo) in mapa.items()
    }
    anuais: dict[int, dict[str, Any]] = {}
    for col, ano, campo in _ANUAIS_TAB11:
        valor = _valor(celulas, _coord(col, linha), "dinheiro", aba, payload["erros"])
        if valor is not None:
            anuais.setdefault(ano, {})[campo] = valor
    projetado_total = _valor(
        celulas, _coord("S", linha), "dinheiro", aba, payload["erros"])
    if not anuais and projetado_total is None:
        return  # O:S vazios: nenhuma linha; o aviso global cobre a aba
    payload["resumos"].append(_montar(_CAMPOS_RESUMO, origem, pilar, {
        "recurso_ou_meta": valores["recurso_ou_meta"],
        "projetado": projetado_total,
        "realizado_mais_projetado": valores["realizado_mais_projetado"],
        "diferenca": valores["diferenca"],
        "percentual": valores["percentual"],
        "farol": valores["farol"],
    }))
    for ano, campos in sorted(anuais.items()):
        payload["resumos"].append(_montar(_CAMPOS_RESUMO, origem, pilar, campos, ano))


# ------------------------------------------------------------- TAB. 3/5/8

def _ler_bloco_reconciliacao(
    payload: dict,
    celulas: dict[str, Any],
    origem: str,
    linha_titulo: int,
    celula_titulo: str,
    limite: int,
    aba: str,
) -> None:
    """Blocos de reconciliação: pilar vem do rótulo à direita do título."""
    coluna_rotulo, linha_rotulo = None, linha_titulo
    for coordenada in sorted(celulas, key=_chave_de_coordenada):
        coluna, linha = _separar_coordenada(coordenada)
        if linha == linha_titulo and _numero_de_coluna(coluna) > _numero_de_coluna(
                _separar_coordenada(celula_titulo)[0]):
            coluna_rotulo = coluna
    if coluna_rotulo is not None:
        pilar = _resolver_pilar(
            payload, celulas, _coord(coluna_rotulo, linha_rotulo), origem, aba)
    else:
        pilar = _resolver_pilar(payload, celulas, celula_titulo, origem, aba)

    for linha in range(linha_titulo + 1, limite + 1):
        if _linha_vazia(celulas, linha, "C", "H"):
            continue
        if normalizar(celulas.get(_coord("C", linha))).startswith("total"):
            break
        if _coord("C", linha) not in celulas:
            continue
        valores = {
            campo: _valor(celulas, _coord(col, linha), tipo, aba, payload["erros"])
            for campo, (col, tipo) in _COLUNAS_RESUMO_RECONCILIACAO.items()
        }
        payload["resumos"].append(_montar(_CAMPOS_RESUMO, origem, pilar, valores))


# ------------------------------------------------------------------ projetos

def _ler_bloco_projetos(
    payload: dict,
    celulas: dict[str, Any],
    origem: str,
    linha_titulo: int,
    limite: int,
    aba: str,
) -> None:
    mapa = _COLUNAS_PROJETO_TAB6 if origem == "TAB. 6" else _COLUNAS_PROJETO_TAB24
    ultima = "L" if origem == "TAB. 6" else "M"
    cabecalho = _proxima_linha_preenchida(celulas, "C", linha_titulo, limite)
    if cabecalho is None:
        payload["erros"].append(
            f"Aba \"{aba}\": cabeçalho esperado 'projeto' para {origem} não encontrado.")
        return
    esperado = _CABECALHO_ESPERADO[origem]
    if normalizar(celulas[_coord("C", cabecalho)]) != normalizar(esperado):
        payload["erros"].append(
            f"Aba \"{aba}\": cabeçalho esperado '{esperado}' para {origem} "
            f"na linha {cabecalho}.")
        return

    pilar = _PILAR_BLOCO_PROJETO[origem]
    for linha in range(cabecalho + 2, limite + 1):
        if _linha_vazia(celulas, linha, "B", ultima):
            continue
        celula_nome = _coord("C", linha)
        if normalizar(celulas.get(celula_nome)).startswith("total"):
            break
        if celula_nome not in celulas or not texto_limpo(celulas[celula_nome]):
            payload["erros"].append(
                f"Aba \"{aba}\", célula {celula_nome}: nome do projeto vazio "
                f"em {origem}.")
            continue
        valores = {
            campo: _valor(celulas, _coord(col, linha), tipo, aba, payload["erros"])
            for campo, (col, tipo) in mapa.items()
        }
        payload["projetos"].append(_montar(_CAMPOS_PROJETO, origem, pilar, valores))


# ------------------------------------------------------------------ utilitários

def _proxima_linha_preenchida(
    celulas: dict[str, Any], coluna: str, inicio: int, limite: int
) -> int | None:
    for linha in range(inicio + 1, limite + 1):
        if _coord(coluna, linha) in celulas:
            return linha
    return None


def _resolver_pilar(
    payload: dict,
    celulas: dict[str, Any],
    coordenada: str,
    origem: str,
    aba: str,
) -> str | None:
    rotulo = celulas.get(coordenada)
    codigo = _codigo_pilar(rotulo)
    if codigo is None:
        payload["erros"].append(
            f"Aba \"{aba}\", célula {coordenada}: rótulo de pilar desconhecido "
            f"\"{texto_limpo(rotulo)}\" em {origem}.")
        return None
    return codigo
