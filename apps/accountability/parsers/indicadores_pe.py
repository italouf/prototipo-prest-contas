"""Parser de ``Indicadores Gerais do Termo de Retificação do PE.xlsx`` (SDD §5).

Lê a aba ``HEAD - INDICADORES`` (cabeçalho nas linhas 2–3, dados a partir da
linha 4) e devolve os 10 KPIs físicos ``PE-01..PE-10`` no payload padrão de
ingestão. Valores de KPI são contagens e frações — nunca moeda — e passam
todos por ``comum.para_decimal``, sem quantização: ``para_dinheiro``
destruiria frações como ``0.0029``. O parser é puro: lê o ``.xlsx`` com
``openpyxl`` e devolve um dicionário; nunca toca no banco.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from apps.accountability.parsers.comum import (
    abrir_workbook,
    eh_erro_formula,
    normalizar,
    novo_payload,
    para_decimal,
    texto_limpo,
)

_ESPACOS = re.compile(r"\s+")
_LINHA_DE_COORDENADA = re.compile(r"[A-Z]+(\d+)")
# Marcadores usados nas planilhas para "sem valor"; contam como vazio.
_MARCADORES_VAZIOS = ("-", "–", "—")

# Assinatura da aba (SDD §5): título normalizado contém "head - indicadores".
_ASSINATURA_ABA = "head - indicadores"
_NOME_ESPERADO_ABA = "HEAD - INDICADORES - EMBRAPII"

# Ação (coluna D) normalizada -> código do pilar interno (SDD §5).
ACOES_PILAR = {
    "pd&i": "PDI",
    "outras fontes": "OUTRASFONTES",
    "at": "AT",
    "acs": "STARTUPS",
    "fcrh": "FORMACAO",
    "infraestrutura": "INFRA",
}

# Célula B da linha de cabeçalho: "Nº"/"Número".
_ROTULOS_NUMERO = {"no", "numero"}

# Campo do dict -> (coluna, tipo de leitura) — SDD §5 (colunas B..Q).
_COLUNAS_KPI = {
    "nome": ("C", "texto"),
    "descricao": ("E", "texto"),
    "unidade": ("F", "texto"),
    "meta_2024": ("G", "numero"),
    "meta_2025": ("H", "numero"),
    "meta_2026": ("I", "numero"),
    "meta_2027": ("J", "numero"),
    "meta_total": ("K", "numero"),
    "executado_2024": ("L", "numero"),
    "executado_2025": ("M", "numero"),
    "acumulado": ("N", "numero"),
    "gap": ("O", "numero"),
    "projecao_2026": ("P", "numero"),
    "projecao_2027": ("Q", "numero"),
}

_CAMPOS_KPI = (
    "codigo", "sequencia", "nome", "pilar", "descricao", "unidade",
    "meta_2024", "meta_2025", "meta_2026", "meta_2027", "meta_total",
    "executado_2024", "executado_2025", "acumulado", "gap",
    "projecao_2026", "projecao_2027",
)


def parse_indicadores_pe(caminho: Path | str) -> dict:
    """Lê o ``Indicadores Gerais do Termo de Retificação do PE.xlsx``.

    Devolve o payload padrão de ``comum.PAYLOAD_VAZIO`` com a lista ``kpis``
    preenchida; o parser é puro e não toca no banco. Falha de leitura do
    arquivo propaga ``comum.ArquivoInvalidoError``.
    """
    payload = novo_payload()
    wb = abrir_workbook(caminho)
    try:
        aba = _encontrar_aba(wb, payload)
        if aba is None:
            return payload
        ws = wb[aba]
        celulas, max_linha = _ler_celulas(ws)
    finally:
        wb.close()

    cabecalho = _linha_de_cabecalho(celulas, max_linha)
    if cabecalho is None:
        payload["erros"].append(
            f'Aba "{aba}": cabeçalho esperado ("Nº"/"Número" em B e '
            '"INDICADORES" na mesma linha) não encontrado.'
            " Verifique se é o template correto da EMBRAPII.")
        return payload

    for linha in range(cabecalho + 2, max_linha + 1):
        if _coord("B", linha) not in celulas and _coord("C", linha) not in celulas:
            break  # dados terminam quando B/C estão vazios (SDD §5)
        _ler_kpi(payload, celulas, linha, aba)
    return payload


# ---------------------------------------------------------------- leitura base

def _encontrar_aba(wb, payload: dict) -> str | None:
    """Primeira aba cujo título normalizado contém ``head - indicadores``."""
    for nome in wb.sheetnames:
        if _ASSINATURA_ABA in normalizar(nome):
            return nome
    payload["erros"].append(
        f'A aba "{_NOME_ESPERADO_ABA}" não foi encontrada'
        f' (abas lidas: {", ".join(repr(a) for a in wb.sheetnames)}).'
        " Verifique se é o template correto da EMBRAPII.")
    return None


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


def _linha_de_cabecalho(celulas: dict[str, Any], max_linha: int) -> int | None:
    """Linha com ``B`` = "Nº"/"Número" e uma célula ``INDICADORES`` (SDD §5)."""
    for linha in range(1, max_linha + 1):
        if normalizar(celulas.get(_coord("B", linha))) not in _ROTULOS_NUMERO:
            continue
        if any(_linha_da_coordenada(c) == linha and normalizar(v) == "indicadores"
               for c, v in celulas.items()):
            return linha
    return None


def _linha_da_coordenada(coordenada: str) -> int:
    match = _LINHA_DE_COORDENADA.fullmatch(coordenada)
    if match is None:
        raise ValueError(f"Coordenada inválida: {coordenada}")
    return int(match.group(1))


def _texto(valor: object) -> str:
    """Texto com espaços internos colapsados (``'Número \\nabsoluto'`` → ``'Número absoluto'``)."""
    if valor is None:
        return ""
    return _ESPACOS.sub(" ", str(valor)).strip()


def _valor(
    celulas: dict[str, Any],
    coordenada: str,
    tipo: str,
    aba: str,
    erros: list[str],
) -> Any:
    """Converte uma célula pelo tipo do campo; vazio ⇒ ``None``.

    Campos numéricos passam por ``para_decimal`` sem quantização (KPI é
    contagem/fração, nunca moeda); texto não numérico vira erro citando aba,
    linha e coluna (SDD §7). Marcadores ``-`` contam como vazio.
    """
    bruto = celulas.get(coordenada)
    if bruto is None:
        return None
    if tipo == "texto":
        return _texto(bruto)
    if isinstance(bruto, str) and (
            not texto_limpo(bruto) or texto_limpo(bruto) in _MARCADORES_VAZIOS):
        return None
    numero = para_decimal(bruto)
    if numero is None:
        problema = "erro de fórmula" if eh_erro_formula(bruto) else "valor não numérico"
        erros.append(
            f'Aba "{aba}", célula {coordenada}: {problema} '
            f'"{texto_limpo(bruto)}".')
    return numero


# --------------------------------------------------------------------- linhas

def _ler_kpi(
    payload: dict, celulas: dict[str, Any], linha: int, aba: str
) -> None:
    """Lê uma linha de KPI (colunas B..Q) e anexa ao payload."""
    celula_numero = _coord("B", linha)
    numero = _valor(celulas, celula_numero, "numero", aba, payload["erros"])
    if numero is None:
        if celula_numero not in celulas:  # erro de conteúdo já citou a célula
            payload["erros"].append(
                f'Aba "{aba}", célula {celula_numero}: número do KPI vazio.')
        return

    valores = {
        campo: _valor(celulas, _coord(col, linha), tipo, aba, payload["erros"])
        for campo, (col, tipo) in _COLUNAS_KPI.items()
    }
    valores["sequencia"] = int(numero)
    valores["codigo"] = f"PE-{int(numero):02d}"
    valores["pilar"] = _resolver_pilar(payload, celulas, linha, aba)
    kpi = {campo: None for campo in _CAMPOS_KPI}
    kpi.update(valores)
    payload["kpis"].append(kpi)


def _resolver_pilar(
    payload: dict, celulas: dict[str, Any], linha: int, aba: str
) -> str | None:
    """Ação (coluna D) → código de pilar; fora de ``ACOES_PILAR`` ⇒ erro."""
    valor = celulas.get(_coord("D", linha))
    codigo = ACOES_PILAR.get(normalizar(valor))
    if codigo is None:
        payload["erros"].append(
            f"Indicadores: ação '{texto_limpo(valor)}' (linha {linha})"
            " sem pilar correspondente.")
    return codigo
