"""Parsers dos arquivos de prestação de contas (SDD 2026-09-29).

Módulo comum com a "linha de senhas" compartilhada pelos parsers de
``FINANCEIRO GERAL.xlsx``, ``Indicadores Gerais do PE.xlsx`` e
``Acompanhamento Financeiro (v2).xlsx``: normalização de rótulos, decisão de
tipo numérico e o shape do payload devolvido por todo parser.

Os parsers são puros: leem o ``.xlsx`` com ``openpyxl`` (``read_only``,
``data_only``) e devolvem um dicionário; nunca tocam no banco.
"""

from __future__ import annotations

import copy
import math
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import openpyxl

_ESPACOS = re.compile(r"\s+")
# Marcadores usados nas planilhas para "sem valor"; contam como vazio.
_SEM_VALOR = {"-", "–", "—"}


class ArquivoInvalidoError(Exception):
    """Arquivo ilegível pelo openpyxl (extensão/zip/ole inválido)."""


PAYLOAD_VAZIO: dict = {
    "metadados": {"centro": None, "periodo_referencia": None, "termo": None},
    "resumos": [],
    "projetos": [],
    "kpis": [],
    "despesas": [],
    "avisos": [],
    "erros": [],
}


def novo_payload() -> dict:
    """Devolve uma cópia profunda de ``PAYLOAD_VAZIO`` (estado isolado)."""
    return copy.deepcopy(PAYLOAD_VAZIO)


def normalizar(texto: object) -> str:
    """Normaliza rótulo: minúsculas, sem acento, espaços colapsados.

    ``normalizar("  AFCCT / PD&I ") == "afcct / pd&i"``.
    """
    if texto is None:
        return ""
    bruto = str(texto).strip()
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", bruto) if not unicodedata.combining(c)
    )
    return _ESPACOS.sub(" ", sem_acento).strip().lower()


def eh_erro_formula(valor: object) -> bool:
    """``True`` para strings iniciadas por ``#`` (``#REF!``, ``#VALUE!``…)."""
    return isinstance(valor, str) and valor.strip().startswith("#")


def para_decimal(valor: object) -> Decimal | None:
    """Converte ``valor`` em ``Decimal`` sem casas fixas; vazio ⇒ ``None``.

    - ``bool`` ⇒ ``None`` (nunca ``1``/``0`` implícitos);
    - ``int``/``float`` ⇒ ``Decimal(str(v))``; ``float`` não finito ⇒ ``None``;
    - texto em formato BR (``"1.234,56"``) ou internacional;
    - erros de fórmula (``#REF!``, ``#VALUE!``…) e marcadores ``-`` ⇒ ``None``.
    """
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, int):
        return Decimal(str(valor))
    if isinstance(valor, float):
        if not math.isfinite(valor):
            return None
        return Decimal(str(valor))
    if isinstance(valor, str):
        texto = re.sub(r"[\s\u00a0\u202f]", "", valor)
        if not texto or texto in _SEM_VALOR or eh_erro_formula(texto):
            return None
        if "," in texto:  # formato BR: milhar "." e decimal ","
            texto = texto.replace(".", "").replace(",", ".")
        elif texto.count(".") > 1:  # só milhar: "1.234.567"
            texto = texto.replace(".", "")
        try:
            return Decimal(texto)
        except InvalidOperation:
            return None
    return None


def para_dinheiro(valor: object) -> Decimal | None:
    """Como ``para_decimal``, mas com 2 casas (centavos), semântica de moeda.

    O Excel grava resultados de fórmula como float (ex.: ``7749636.720000001``);
    a quantização devolve o valor em centavos (``7749636.72``) sem inventar
    precisão — vazio continua ``None``.
    """
    numero = para_decimal(valor)
    if numero is None:
        return None
    return numero.quantize(Decimal("0.01"))


def abrir_workbook(caminho: Path | str):
    """Abre o ``.xlsx`` em modo somente leitura, com valores calculados.

    Raises:
        ArquivoInvalidoError: o openpyxl não conseguiu ler o arquivo.
    """
    try:
        return openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001 — zip/ole/xml inválido vira erro único
        raise ArquivoInvalidoError(
            f"Não foi possível ler '{Path(caminho).name}': {exc}"
        ) from exc


def texto_limpo(valor: Any) -> str:
    """Texto aparado para campos ``CharField`` (``None`` ⇒ ``""``)."""
    if valor is None:
        return ""
    return str(valor).strip()
