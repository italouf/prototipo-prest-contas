"""Motor de exportação .xlsx Lossless sobre templates EMBRAPII v3.1.

Preserva 100% de:
- <sheetProtection> (incluindo hashes SHA-512, saltValue, spinCount)
- Todas as fórmulas nativas (<f>)
- Todos os blocos <extLst> / <x14:dataValidations>, <dataValidations>,
  <tableParts>, <drawing>, <comments> em células mescladas e estilos originais.
"""
from collections import OrderedDict
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
import posixpath
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from django.conf import settings
from openpyxl.utils.cell import column_index_from_string

from .models import CicloSemestral
from .xlsx_schema import SHEET_EXPORT_SPECS, SUMMARY_SPECS

TEMPLATES_DIR = Path(settings.BASE_DIR) / "templates_embrapii" / "v3_1"

TEMPLATE_MAP = {
    "FIN": (
        TEMPLATES_DIR / "fin_v3_1.xlsx",
        "Acompanhamento_Financeiro_Semestral_v3_1_{abrev}_{ano}_S{sem}.xlsx",
    ),
    "FCRH": (
        TEMPLATES_DIR / "fcrh_v3_1.xlsx",
        "Acompanhamento_Tecnico_FCRH_Semestral_v3_1_{abrev}_{ano}_S{sem}.xlsx",
    ),
    "ACS": (
        TEMPLATES_DIR / "acs_v3_1.xlsx",
        "Acompanhamento_Tecnico_ACS_Semestral_v3_1_{abrev}_{ano}_S{sem}.xlsx",
    ),
    "AFCCT": (
        TEMPLATES_DIR / "afcct_v3_1.xlsx",
        "Acompanhamento_Tecnico_AFCCT_Semestral_v3_1_{abrev}_{ano}_S{sem}.xlsx",
    ),
    "AT": (
        TEMPLATES_DIR / "at_v3_1.xlsx",
        "Acompanhamento_Tecnico_AT_Semestral_v3_1_{abrev}_{ano}_S{sem}.xlsx",
    ),
}

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

SHEET_DATA_RE = re.compile(r"(<sheetData\b[^>]*>)(.*?)(</sheetData>)", re.S)
ROW_RE = re.compile(r'(<row\b[^>]*\br="(\d+)"[^>]*>)(.*?)(</row>)', re.S)
CELL_RE = re.compile(
    r'<c\b([^>]*?)\br="([A-Z]+)(\d+)"([^>]*?)(?:/>|>(.*?)</c>)', re.S
)
FORMULA_TAG_RE = re.compile(r"<f\b", re.S)
FORMULA_FULL_RE = re.compile(r"<f\b[^>]*>.*?</f>|<f\b[^>]*/>", re.S)
CELL_REF_ATTR_RE = re.compile(r'\br="([A-Z]+\d+)"')
STYLE_ATTR_RE = re.compile(r'\bs="(\d+)"')
TYPE_ATTR_RE = re.compile(r'\s*\bt="[^"]*"')
INVALID_XML_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _read_locked_styles(styles_bytes: bytes) -> set[str]:
    """Retorna índices de cellXfs bloqueados (locked != 0)."""
    root = ET.fromstring(styles_bytes)
    cell_xfs = root.find(f"{{{NS_MAIN}}}cellXfs")
    locked = set()
    if cell_xfs is None:
        return locked
    for idx, xf in enumerate(cell_xfs.findall(f"{{{NS_MAIN}}}xf")):
        prot = xf.find(f"{{{NS_MAIN}}}protection")
        if prot is None or prot.attrib.get("locked") not in ("0", "false"):
            locked.add(str(idx))
    return locked


def _map_sheet_paths(partes: Dict[str, bytes]) -> Dict[str, str]:
    """Mapeia nome exato da aba -> caminho XML dentro do pacote ZIP."""
    wb = ET.fromstring(partes["xl/workbook.xml"])
    rels = ET.fromstring(partes["xl/_rels/workbook.xml.rels"])
    rel_map = {}
    for r in rels:
        target = r.attrib["Target"]
        if target.startswith("/"):
            rel_map[r.attrib["Id"]] = target.lstrip("/")
        else:
            rel_map[r.attrib["Id"]] = posixpath.normpath("xl/" + target)
    sheet_map = {}
    sheets_el = wb.find(f"{{{NS_MAIN}}}sheets")
    if sheets_el is not None:
        for s in sheets_el:
            rid = s.attrib.get(f"{{{NS_REL}}}id")
            if rid and rid in rel_map:
                sheet_map[s.attrib["name"]] = rel_map[rid]
    return sheet_map


def _clean_xml_text(texto: str) -> str:
    return INVALID_XML_CHARS_RE.sub("", texto)


def _excel_serial(d: date) -> int:
    return (d - date(1899, 12, 30)).days


def _build_cell_xml(ref: str, attrs_before: str, attrs_after: str, value: Any) -> str:
    attrs_raw = f"{attrs_before} {attrs_after}".strip()
    attrs_clean = TYPE_ATTR_RE.sub("", attrs_raw).strip()
    attrs_prefix = f" {attrs_clean}" if attrs_clean else ""

    if value is None or value == "":
        return f'<c r="{ref}"{attrs_prefix}/>'

    if isinstance(value, bool):
        return f'<c r="{ref}"{attrs_prefix} t="b"><v>{1 if value else 0}</v></c>'

    if isinstance(value, datetime):
        value = value.date()

    if isinstance(value, date):
        return f'<c r="{ref}"{attrs_prefix}><v>{_excel_serial(value)}</v></c>'

    if isinstance(value, Decimal):
        num_str = format(value, "f")
        if "." in num_str:
            num_str = num_str.rstrip("0").rstrip(".") or "0"
        return f'<c r="{ref}"{attrs_prefix}><v>{num_str}</v></c>'

    if isinstance(value, (int, float)):
        return f'<c r="{ref}"{attrs_prefix}><v>{value}</v></c>'

    escaped = escape(_clean_xml_text(str(value)))
    return (
        f'<c r="{ref}"{attrs_prefix} t="inlineStr">'
        f'<is><t xml:space="preserve">{escaped}</t></is></c>'
    )


def _patch_row_xml(
    row_open: str,
    row_num: int,
    row_inner: str,
    row_close: str,
    col_values: Dict[str, Any],
    locked_styles: set[str],
    default_unlocked_styles: Dict[str, str],
) -> str:
    cells_by_col: Dict[int, str] = {}
    attrs_by_col: Dict[int, Tuple[str, str]] = {}
    formula_cols: set[int] = set()
    locked_cols: set[int] = set()

    for m in CELL_RE.finditer(row_inner):
        before, col_str, _rnum, after, body = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        col_idx = column_index_from_string(col_str)
        raw_cell = m.group(0)
        cells_by_col[col_idx] = raw_cell
        attrs_by_col[col_idx] = (before, after)
        if body is not None and FORMULA_TAG_RE.search(body):
            formula_cols.add(col_idx)
        style_m = STYLE_ATTR_RE.search(f"{before} {after}")
        sid = style_m.group(1) if style_m else None
        if sid is None or sid in locked_styles:
            locked_cols.add(col_idx)

    for col_letter, val in col_values.items():
        if val is None or val == "":
            continue
        col_idx = column_index_from_string(col_letter)
        ref = f"{col_letter}{row_num}"
        if col_idx in cells_by_col:
            # Regra inviolável: nunca sobrescrever fórmula nem célula bloqueada
            if col_idx in formula_cols or col_idx in locked_cols:
                continue
            before, after = attrs_by_col[col_idx]
            cells_by_col[col_idx] = _build_cell_xml(ref, before, after, val)
        else:
            # Célula não existia no XML da linha; só escreve se estilo padrão da coluna for desbloqueado
            fallback_sid = default_unlocked_styles.get(col_letter)
            if fallback_sid is not None and fallback_sid not in locked_styles:
                cells_by_col[col_idx] = _build_cell_xml(ref, f's="{fallback_sid}"', "", val)

    ordered = "".join(cells_by_col[idx] for idx in sorted(cells_by_col))
    return f"{row_open}{ordered}{row_close}"


def _infer_unlocked_col_styles(sheet_data_xml: str, sample_row: int, locked_styles: set[str]) -> Dict[str, str]:
    """Lê estilos da primeira linha de dados para referência caso falte célula esparsa."""
    result = {}
    m = re.search(rf'<row\b[^>]*\br="{sample_row}"[^>]*>(.*?)</row>', sheet_data_xml, re.S)
    if not m:
        return result
    for cm in CELL_RE.finditer(m.group(1)):
        col_str = cm.group(2)
        sm = STYLE_ATTR_RE.search(f"{cm.group(1)} {cm.group(4)}")
        if sm and sm.group(1) not in locked_styles:
            result[col_str] = sm.group(1)
    return result


def _patch_sheet_xml(
    sheet_bytes: bytes,
    updates_by_row: Dict[int, Dict[str, Any]],
    locked_styles: set[str],
    sample_row: Optional[int] = None,
) -> bytes:
    if not updates_by_row:
        return sheet_bytes
    xml_text = sheet_bytes.decode("utf-8")
    sd_match = SHEET_DATA_RE.search(xml_text)
    if not sd_match:
        return sheet_bytes

    sd_open, sd_body, sd_close = sd_match.group(1), sd_match.group(2), sd_match.group(3)
    default_styles = (
        _infer_unlocked_col_styles(sd_body, sample_row, locked_styles)
        if sample_row is not None
        else {}
    )

    def _replace_row(match):
        rnum = int(match.group(2))
        if rnum not in updates_by_row:
            return match.group(0)
        return _patch_row_xml(
            match.group(1),
            rnum,
            match.group(3),
            match.group(4),
            updates_by_row[rnum],
            locked_styles,
            default_styles,
        )

    new_sd_body = ROW_RE.sub(_replace_row, sd_body)
    new_xml = (
        xml_text[: sd_match.start()]
        + sd_open
        + new_sd_body
        + sd_close
        + xml_text[sd_match.end() :]
    )
    return new_xml.encode("utf-8")


def _enable_full_calc(workbook_bytes: bytes) -> bytes:
    text = workbook_bytes.decode("utf-8")
    if "<calcPr " in text:
        def _upd(m):
            tag = m.group(0)
            if "fullCalcOnLoad=" in tag:
                tag = re.sub(r'fullCalcOnLoad="[^"]*"', 'fullCalcOnLoad="1"', tag)
            else:
                tag = tag.replace("<calcPr ", '<calcPr fullCalcOnLoad="1" ', 1)
            return tag
        text = re.sub(r"<calcPr\b[^>]*/>", _upd, text, count=1)
    return text.encode("utf-8")


def _coletar_registros_ciclo(ciclo: CicloSemestral, spec) -> List[Any]:
    qs = spec.model.objects.filter(competencia_mensal__ciclo=ciclo)
    if spec.is_comment_sheet:
        qs = qs.filter(arquivo=spec.arquivo, aba=spec.aba)
    return list(qs.order_by("competencia_mensal__competencia", "id"))


def exportar_planilha_embrapii(ciclo: CicloSemestral, arquivo_tag: str) -> Tuple[str, bytes]:
    """Gera uma das 5 planilhas EMBRAPII v3.1 preenchida de forma lossless."""
    if arquivo_tag not in TEMPLATE_MAP:
        raise ValueError(f"Arquivo EMBRAPII desconhecido: {arquivo_tag}")
    template_path, filename_pattern = TEMPLATE_MAP[arquivo_tag]
    with ZipFile(template_path, "r") as zf:
        infos = zf.infolist()
        partes = OrderedDict((info.filename, zf.read(info.filename)) for info in infos)

    locked_styles = _read_locked_styles(partes["xl/styles.xml"])
    sheet_paths = _map_sheet_paths(partes)

    # 1. Preencher Sumário (J21:J23 no FIN; J15:J17 nos técnicos)
    sum_spec = SUMMARY_SPECS[arquivo_tag]
    sum_path = sheet_paths[sum_spec["aba"]]
    sum_updates: Dict[int, Dict[str, Any]] = {}
    for cell_ref, attr_name in sum_spec["cells"].items():
        col_m = re.match(r"^([A-Z]+)(\d+)$", cell_ref)
        col_l, rnum = col_m.group(1), int(col_m.group(2))
        sum_updates.setdefault(rnum, {})[col_l] = getattr(ciclo, attr_name)
    partes[sum_path] = _patch_sheet_xml(partes[sum_path], sum_updates, locked_styles)

    # 2. Preencher todas as abas no escopo QuIIN para este arquivo
    for spec in SHEET_EXPORT_SPECS:
        if spec.arquivo != arquivo_tag:
            continue
        sheet_path = sheet_paths[spec.aba]
        registros = _coletar_registros_ciclo(ciclo, spec)
        if not registros:
            continue
        updates: Dict[int, Dict[str, Any]] = {}
        if spec.is_comment_sheet:
            # Célula mesclada B10:E14 — concatena comentários mensais cronologicamente em B10
            blocos = [
                f"[{r.competencia_mensal.competencia_mm_aaaa}] {r.comentario.strip()}"
                for r in registros
                if (r.comentario or "").strip()
            ]
            if blocos:
                updates[spec.row_start] = {"B": "\n\n".join(blocos)}
        else:
            capacidade = spec.row_end - spec.row_start + 1
            for idx, reg in enumerate(registros[:capacidade]):
                rnum = spec.row_start + idx
                row_dict = {}
                for col_letter, field_name in spec.columns:
                    row_dict[col_letter] = getattr(reg, field_name)
                updates[rnum] = row_dict
        partes[sheet_path] = _patch_sheet_xml(
            partes[sheet_path], updates, locked_styles, sample_row=spec.row_start
        )

    partes["xl/workbook.xml"] = _enable_full_calc(partes["xl/workbook.xml"])

    out_buf = BytesIO()
    with ZipFile(out_buf, "w", compression=ZIP_DEFLATED) as zout:
        for info in infos:
            out_info = ZipInfo(info.filename, date_time=info.date_time)
            out_info.compress_type = info.compress_type or ZIP_DEFLATED
            out_info.external_attr = info.external_attr
            zout.writestr(out_info, partes[info.filename])

    filename = filename_pattern.format(
        abrev=ciclo.abreviacao_cc or "QIN",
        ano=ciclo.ano,
        sem=ciclo.semestre,
    )
    return filename, out_buf.getvalue()


def exportar_pacote_semestral_zip(ciclo: CicloSemestral) -> Tuple[str, bytes]:
    """Gera pacote .zip contendo os 5 arquivos EMBRAPII v3.1 consolidados."""
    buf = BytesIO()
    with ZipFile(buf, "w", compression=ZIP_DEFLATED) as zf:
        for tag in ("FIN", "FCRH", "ACS", "AFCCT", "AT"):
            fname, fbytes = exportar_planilha_embrapii(ciclo, tag)
            zf.writestr(fname, fbytes)
    zip_name = f"EMBRAPII_{ciclo.abreviacao_cc or 'QIN'}_{ciclo.ano}_S{ciclo.semestre}_v3_1.zip"
    return zip_name, buf.getvalue()


def _extract_sheet_guards(xml_text: str):
    """Extrai tags críticas que devem ser 100% preservadas: sheetProtection, extLst e <f>."""
    protections = (
        re.findall(r"<sheetProtection\b[^>]*/>", xml_text, re.S)
        if "<sheetProtection" in xml_text
        else []
    )
    ext_lsts = (
        re.findall(r"<extLst\b.*?</extLst>", xml_text, re.S)
        if "<extLst" in xml_text
        else []
    )
    formulas = {}
    if "<f" in xml_text:
        pos = 0
        while True:
            idx = xml_text.find("<f", pos)
            if idx == -1:
                break
            nxt = xml_text[idx + 2 : idx + 3]
            if nxt not in (" ", ">", "/"):
                pos = idx + 2
                continue
            c_start = xml_text.rfind("<c ", 0, idx)
            last_c_close = xml_text.rfind("</c>", 0, idx)
            c_end = xml_text.find("</c>", idx)
            if c_start != -1 and c_end != -1 and c_start > last_c_close:
                cell_xml = xml_text[c_start : c_end + 4]
                rm = CELL_REF_ATTR_RE.search(cell_xml)
                fm = FORMULA_FULL_RE.search(cell_xml)
                if rm and fm:
                    formulas[rm.group(1)] = fm.group(0)
                pos = c_end + 4
            else:
                pos = idx + 2
    return protections, ext_lsts, formulas


def validar_integridade_xlsx(template_path: Path, output_bytes: bytes) -> Dict[str, Any]:
    """Compara template original x arquivo exportado garantindo preservação OOXML total."""
    with ZipFile(template_path, "r") as z_tpl, ZipFile(BytesIO(output_bytes), "r") as z_out:
        tpl_parts = {n: z_tpl.read(n) for n in z_tpl.namelist()}
        out_parts = {n: z_out.read(n) for n in z_out.namelist()}

    assert set(tpl_parts.keys()) == set(out_parts.keys()), "Conjunto de arquivos ZIP divergiu!"
    sheet_paths = _map_sheet_paths(tpl_parts)
    total_protections = 0
    total_ext_lsts = 0
    total_formulas = 0

    for sheet_name, spath in sheet_paths.items():
        tpl_xml = tpl_parts[spath].decode("utf-8")
        out_xml = out_parts[spath].decode("utf-8")
        p1, e1, f1 = _extract_sheet_guards(tpl_xml)
        p2, e2, f2 = _extract_sheet_guards(out_xml)
        assert p1 == p2, f"<sheetProtection> alterado na aba '{sheet_name}'!"
        assert e1 == e2, f"<extLst> alterado na aba '{sheet_name}'!"
        assert f1 == f2, (
            f"Fórmulas alteradas na aba '{sheet_name}'! "
            f"Diff keys={set(f1.keys()) ^ set(f2.keys())}"
        )
        total_protections += len(p2)
        total_ext_lsts += len(e2)
        total_formulas += len(f2)

    return {
        "sheets_checked": len(sheet_paths),
        "sheet_protections_preserved": total_protections,
        "ext_lst_blocks_preserved": total_ext_lsts,
        "formulas_preserved": total_formulas,
    }
