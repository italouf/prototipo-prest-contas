"""Gera o REFAT v3 com a aba de Infraestrutura sem alterar o v2.

A gravação é feita no nível OOXML: as partes existentes são copiadas byte a
byte e apenas o worksheet/tabelas novos, o ``workbook.xml``, seus
relacionamentos e ``[Content_Types].xml`` são acrescentados. Um ``save`` do
openpyxl apagaria os resultados cacheados das fórmulas das abas atuais.
"""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from xml.sax.saxutils import escape, quoteattr
from zipfile import ZIP_DEFLATED, ZipFile

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from .infra import (
    CATEGORIAS_INFRA,
    NOME_TABELA_PROJETOS_INFRA,
    NOME_TABELA_VISAO_INFRA,
    ORIGEM_VISAO_INFRA,
)
from .parsers.financeiro_geral import parse_financeiro_geral

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
TABLE_REL = f"{REL}/table"

PROJETOS_HEADERS = (
    "ITEM", "CÓDIGO", "PROJETO", "CATEGORIA", "STATUS", "INÍCIO",
    "FINAL PREVISTO", "ORÇADO", "REALIZADO", "PROJETADO 2026",
    "PROJETADO 2027", "REALIZADO + PROJETADO", "DIFERENÇA ORÇADO",
    "% REALIZADO", "FAROL", "ETAPA",
)
VISAO_HEADERS = (
    "Coluna1", "RECURSO INFRA", "REALIZADO", "PROJETADO TOTAL",
    "REALIZADO + PROJETADO", "DIFERENÇA",
)
STATUS_RANGE = "_Opcoes_Projetos!$A$2:$A$10"
CATEGORIA_RANGE = "$Y$2:$Y$7"
PROJETOS_REF = "A1:P12"
VISAO_REF = "R1:W2"
ABA_INFRA = "db_infra"


def _celula(ref, valor=None, *, estilo=None, formula=None, tipo=None):
    atributos = f' r="{ref}"'
    if estilo is not None:
        atributos += f' s="{estilo}"'
    if formula is not None:
        if tipo == "str":
            atributos += ' t="str"'
        cache = "" if valor is None else str(valor)
        return f"<c{atributos}><f>{escape(formula)}</f><v>{escape(cache)}</v></c>"
    if valor is None:
        return f"<c{atributos}/>"
    if isinstance(valor, str):
        return f'<c{atributos} t="inlineStr"><is><t>{escape(valor)}</t></is></c>'
    return f"<c{atributos}><v>{valor}</v></c>"


def _adicionar(linhas, linha, ref, valor=None, *, estilo=None, formula=None, tipo=None):
    linhas.setdefault(linha, []).append(
        _celula(ref, valor, estilo=estilo, formula=formula, tipo=tipo))


def _formulas_linha(linhas, linha, estilos):
    _adicionar(linhas, linha, f"L{linha}", estilo=estilos["money"],
               formula=f'IF($C{linha}="","",SUM(I{linha}:K{linha}))', tipo="str")
    _adicionar(linhas, linha, f"M{linha}", estilo=estilos["money"],
               formula=f'IF($C{linha}="","",L{linha}-H{linha})', tipo="str")
    _adicionar(linhas, linha, f"N{linha}", estilo=estilos["percent"],
               formula=f'IF(OR($C{linha}="",N($H{linha})=0),"",I{linha}/H{linha})',
               tipo="str")
    _adicionar(
        linhas, linha, f"O{linha}", estilo=estilos["general"],
        formula=(
            f'IF($C{linha}="","",IF(OR(ISBLANK(I{linha}),ISBLANK(H{linha}),'
            f'H{linha}<=0),"Sem lançamento",IF(I{linha}/H{linha}>=0.9,'
            f'"Meta atingida",IF(I{linha}/H{linha}>=0.5,"Execução parcial",'
            f'"Execução crítica"))))'),
        tipo="str")
    _adicionar(
        linhas, linha, f"P{linha}", estilo=estilos["general"],
        formula=(
            f'IF($C{linha}="","",IF(ISNUMBER(SEARCH("encerrad",E{linha})),'
            f'"Encerrados",IF(ISNUMBER(SEARCH("andamento",E{linha})),'
            f'"Em andamento","Futuros projetos")))'),
        tipo="str")


def _worksheet_xml(estilos):
    linhas = {}

    # Cabeçalhos dos dois objetos e da lista de categorias.
    for coluna, titulo in enumerate(PROJETOS_HEADERS, start=1):
        _adicionar(linhas, 1, f"{get_column_letter(coluna)}1", titulo,
                   estilo=estilos["header"])
    for coluna, titulo in enumerate(VISAO_HEADERS, start=18):
        _adicionar(linhas, 1, f"{get_column_letter(coluna)}1", titulo,
                   estilo=estilos["header"])
    _adicionar(linhas, 1, "Y1", "Categorias", estilo=estilos["header"])

    for linha in range(2, 12):
        for coluna, estilo in (
            (1, estilos["general"]), (2, estilos["text"]), (3, estilos["text"]),
            (4, estilos["text"]), (5, estilos["text"]), (6, estilos["date"]),
            (7, estilos["date"]), (8, estilos["money"]), (9, estilos["money"]),
            (10, estilos["money"]), (11, estilos["money"]),
        ):
            _adicionar(linhas, linha, f"{get_column_letter(coluna)}{linha}",
                       estilo=estilo)
        _formulas_linha(linhas, linha, estilos)

    for indice, categoria in enumerate(CATEGORIAS_INFRA, start=2):
        _adicionar(linhas, indice, f"Y{indice}", categoria, estilo=estilos["text"])

    # Resumo oficial de Infraestrutura.
    _adicionar(linhas, 2, "R2", "RECURSO INFRA", estilo=estilos["text"])
    _adicionar(linhas, 2, "S2", 10000000, estilo=estilos["money"])
    _adicionar(linhas, 2, "T2", 7299414.35, estilo=estilos["money"])
    _adicionar(linhas, 2, "U2", estilo=estilos["money"])
    _adicionar(linhas, 2, "V2", estilo=estilos["money"])
    _adicionar(linhas, 2, "W2", 2700585.65, estilo=estilos["money"],
               formula='IF(U2="",S2-T2,S2-V2)')

    # Linha total da tabela de projetos.
    _adicionar(linhas, 12, "C12", "TOTAL", estilo=estilos["header"])
    for coluna in ("H", "I", "J", "K", "L", "M"):
        _adicionar(linhas, 12, f"{coluna}12", 0, estilo=estilos["money"],
                   formula=f"SUM({coluna}2:{coluna}11)")
    _adicionar(linhas, 12, "N12", estilo=estilos["percent"],
               formula='IF(N(H12)=0,"",I12/H12)', tipo="str")
    _adicionar(
        linhas, 12, "O12", "Sem lançamento", estilo=estilos["general"],
        formula=(
            'IF(OR(ISBLANK(I12),ISBLANK(H12),H12<=0),"Sem lançamento",'
            'IF(I12/H12>=0.9,"Meta atingida",IF(I12/H12>=0.5,'
            '"Execução parcial","Execução crítica")))'),
        tipo="str")

    sheet_data = "".join(
        f'<row r="{numero}">{"".join(celulas)}</row>'
        for numero, celulas in sorted(linhas.items()))

    colunas = (
        '<cols>'
        '<col min="1" max="16" width="18" customWidth="1"/>'
        '<col min="17" max="17" width="2"/>'
        '<col min="18" max="23" width="18" customWidth="1"/>'
        '<col min="24" max="24" width="2"/>'
        '<col min="25" max="25" width="24" customWidth="1" hidden="1"/>'
        '</cols>'
    )
    validacoes = (
        '<dataValidations count="2">'
        '<dataValidation type="list" allowBlank="1" showErrorMessage="1" '
        'errorTitle="Status do projeto" error="Selecione uma opção da lista." '
        f'sqref="E2:E11"><formula1>{STATUS_RANGE}</formula1></dataValidation>'
        '<dataValidation type="list" allowBlank="1" showErrorMessage="1" '
        'errorTitle="Categoria" error="Selecione uma categoria válida." '
        f'sqref="D2:D11"><formula1>{CATEGORIA_RANGE}</formula1></dataValidation>'
        '</dataValidations>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="{NS}" xmlns:r="{REL}">'
        f'<dimension ref="A1:Y12"/>'
        '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
        '<sheetFormatPr defaultRowHeight="15"/>'
        f'{colunas}<sheetData>{sheet_data}</sheetData>{validacoes}'
        '<tableParts count="2"><tablePart r:id="rId1"/><tablePart r:id="rId2"/></tableParts>'
        '</worksheet>'
    )


def _tabela_xml(table_id, nome, ref, cabecalhos):
    colunas = "".join(
        f'<tableColumn id="{indice}" name={quoteattr(cabecalho)}/>'
        for indice, cabecalho in enumerate(cabecalhos, start=1))
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<table xmlns="{NS}" id="{table_id}" name={quoteattr(nome)} '
        f'displayName={quoteattr(nome)} ref="{ref}" totalsRowShown="0">'
        f'<tableColumns count="{len(cabecalhos)}">{colunas}</tableColumns>'
        '<tableStyleInfo name="TableStyleMedium2" showFirstColumn="0" '
        'showLastColumn="0" showRowStripes="1" showColumnStripes="0"/>'
        '</table>'
    )


def _sheet_rels_xml(tabela1, tabela2):
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="{TABLE_REL}" Target="../tables/{tabela1}"/>'
        f'<Relationship Id="rId2" Type="{TABLE_REL}" Target="../tables/{tabela2}"/>'
        '</Relationships>'
    )


def _estilos(caminho):
    wb = load_workbook(caminho, data_only=True)
    try:
        ws = wb["db_afcct_pdi"]
        return {
            "header": ws["A1"].style_id,
            "text": ws["B2"].style_id,
            "date": ws["D2"].style_id,
            "money": ws["F2"].style_id,
            "percent": ws["L2"].style_id,
            "general": ws["O2"].style_id,
        }
    finally:
        wb.close()


def _proximo_numero(parts, padrao):
    numeros = [int(m) for nome in parts for m in re.findall(padrao, nome)]
    return max(numeros, default=0) + 1


def gerar_refat_infra(origem: Path | str, destino: Path | str, *, forcar=False) -> dict:
    """Cria o v3 a partir do v2; o arquivo de origem nunca é alterado."""
    origem = Path(origem)
    destino = Path(destino)
    if destino.exists() and not forcar:
        raise FileExistsError(f"O destino já existe: {destino}")
    original = origem.read_bytes()
    assinatura = sha256(original).hexdigest()
    antes = parse_financeiro_geral(BytesIO(original))
    if antes["erros"]:
        raise ValueError("O arquivo de origem não passou na validação: "
                         + " | ".join(antes["erros"]))
    estilos = _estilos(origem)

    with ZipFile(origem) as pacote:
        partes = {info.filename: pacote.read(info.filename) for info in pacote.infolist()}

    workbook = partes["xl/workbook.xml"].decode("utf-8")
    rels = partes["xl/_rels/workbook.xml.rels"].decode("utf-8")
    content_types = partes["[Content_Types].xml"].decode("utf-8")

    sheet_id = max(int(m) for m in re.findall(r'sheetId="(\d+)"', workbook)) + 1
    sheet_numero = _proximo_numero(partes, r"xl/worksheets/sheet(\d+)\.xml$")
    table_id = max(int(m) for nome, valor in partes.items()
                   if nome.startswith("xl/tables/table")
                   for m in re.findall(r'\bid="(\d+)"', valor.decode("utf-8"))) + 1
    rel_id = max(int(m) for m in re.findall(r'Id="rId(\d+)"', rels)) + 1
    sheet_path = f"xl/worksheets/sheet{sheet_numero}.xml"
    tabela1 = f"table{table_id}.xml"
    tabela2 = f"table{table_id + 1}.xml"
    tabela1_path = f"xl/tables/{tabela1}"
    tabela2_path = f"xl/tables/{tabela2}"

    workbook = workbook.replace(
        "</sheets>",
        f'<sheet name="{ABA_INFRA}" sheetId="{sheet_id}" r:id="rId{rel_id}"/></sheets>',
    )
    workbook = re.sub(
        r"<calcPr\b[^>]*/>",
        '<calcPr calcMode="auto" fullCalcOnLoad="1" forceFullCalc="1"/>',
        workbook,
    )
    rels = rels.replace(
        "</Relationships>",
        f'<Relationship Id="rId{rel_id}" Type="{REL}/worksheet" '
        f'Target="worksheets/sheet{sheet_numero}.xml"/></Relationships>',
    )
    content_types = content_types.replace(
        "</Types>",
        f'<Override PartName="/{sheet_path}" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        f'<Override PartName="/{tabela1_path}" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.table+xml"/>'
        f'<Override PartName="/{tabela2_path}" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.table+xml"/>'
        "</Types>",
    )
    partes["xl/workbook.xml"] = workbook.encode("utf-8")
    partes["xl/_rels/workbook.xml.rels"] = rels.encode("utf-8")
    partes["[Content_Types].xml"] = content_types.encode("utf-8")
    partes[sheet_path] = _worksheet_xml(estilos).encode("utf-8")
    partes[f"xl/worksheets/_rels/sheet{sheet_numero}.xml.rels"] = _sheet_rels_xml(
        tabela1, tabela2).encode("utf-8")
    partes[tabela1_path] = _tabela_xml(
        table_id, NOME_TABELA_PROJETOS_INFRA, PROJETOS_REF, PROJETOS_HEADERS).encode("utf-8")
    partes[tabela2_path] = _tabela_xml(
        table_id + 1, NOME_TABELA_VISAO_INFRA, VISAO_REF, VISAO_HEADERS).encode("utf-8")

    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = NamedTemporaryFile(
        suffix=".xlsx", dir=destino.parent, delete=False)
    temporario.close()
    caminho_temporario = Path(temporario.name)
    try:
        with ZipFile(caminho_temporario, "w", compression=ZIP_DEFLATED) as pacote:
            for nome, dados in partes.items():
                pacote.writestr(nome, dados)
        depois = parse_financeiro_geral(caminho_temporario)
        if depois["erros"]:
            raise ValueError("O v3 gerado não passou na validação: "
                             + " | ".join(depois["erros"]))
        resumos_existentes = [r for r in depois["resumos"]
                              if r["origem"] != ORIGEM_VISAO_INFRA]
        if resumos_existentes != antes["resumos"]:
            raise ValueError("O v3 alteraria os resumos financeiros existentes.")
        if depois["projetos"] != antes["projetos"]:
            raise ValueError("O v3 alteraria os projetos financeiros existentes.")
        infra = next((r for r in depois["resumos"]
                      if r["origem"] == ORIGEM_VISAO_INFRA), None)
        if infra is None:
            raise ValueError("O v3 não criou o resumo de Infraestrutura.")
        caminho_temporario.replace(destino)
    finally:
        if caminho_temporario.exists():
            caminho_temporario.unlink()

    return {
        "alterado": True,
        "sha256_antes": assinatura,
        "sha256_depois": sha256(destino.read_bytes()).hexdigest(),
        "destino": str(destino),
        "tabelas": [NOME_TABELA_PROJETOS_INFRA, NOME_TABELA_VISAO_INFRA],
    }
