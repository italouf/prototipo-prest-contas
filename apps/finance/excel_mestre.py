"""Consolidação do Excel financeiro mestre (Portal QuIIN).

Lê as abas de conta-ação com openpyxl (somente leitura, sem escrever no
arquivo) e soma o valor executado por (pilar, tipo_recurso) filtrando o
mês de referência.

REGRA DURA: a aba 6.1 (Lei de TICs) é segregada como AT_LEI_TICS e
NUNCA soma no AT.
"""
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import openpyxl
from django.core.exceptions import ValidationError
from django.db import transaction
from openpyxl.utils.datetime import from_excel

from apps.audit.services import registrar_auditoria
from apps.pillars.models import Pilar
from .models import FinanceiroConsolidado, ImportacaoFinanceira

# REGRA DURA: Lei de TICs segregada; só agregaria AT_TOTAL = AT + AT_LEI_TICS
# se um dia virar True. Painéis/cards que filtram tipo_recurso="AT" ficam
# automaticamente corretos enquanto for False.
INCLUIR_LEI_TICS_NO_AT = False

LINHAS_CABECALHO = 30

FORMATOS_DATA_TEXTO = ("%d/%m/%Y", "%Y-%m-%d")


def normalizar(texto):
    """Minúsculas, sem acento e com espaços colapsados."""
    base = unicodedata.normalize("NFKD", str(texto or ""))
    base = "".join(c for c in base if not unicodedata.combining(c))
    return " ".join(base.lower().split())


def mapear_aba(nome_aba):
    """Mapeia o nome da aba para (pilar, tipo_recurso) ou None se fora do mapa."""
    n = normalizar(nome_aba)
    # 6.1 primeiro: nunca pode cair na regra genérica do AT.
    if re.search(r"(^|[^0-9])6\.1", n) or ("conta" in n and "at" in n and ("tics" in n or "tic" in n or "lei" in n)):
        return ("AT", "AT_LEI_TICS")
    if "afcct" in n:
        return ("PDI", "EMBRAPII")
    if "fcrh" in n:
        return ("FORMACAO", "EMBRAPII")
    if "acs" in n and "conta" in n and "venture" not in n and "equipe" not in n:
        return ("STARTUPS", "EMBRAPII")
    if "outras fontes" in n or "outrasfontes" in n:
        return ("OUTRASFONTES", "OUTRAS_FONTES")
    if "infraestrutura" in n and "ampliacao" not in n:
        return ("INFRA", "EMBRAPII")
    if re.search(r"(^|[^0-9])6\.", n) and "at" in n and "tics" not in n and "tic" not in n and "lei" not in n:
        return ("AT", "AT")
    return None


def _eh_data(valor_norm):
    return "data" in valor_norm and ("pagamento" in valor_norm or "pgto" in valor_norm or "pagto" in valor_norm)


def _eh_valor(valor_norm):
    return "valor" in valor_norm or "vlr" in valor_norm


def descobrir_colunas(ws, max_linhas=LINHAS_CABECALHO):
    """Descobre (linha_cabecalho, idx_data, idx_valor) varrendo as primeiras linhas.

    Retorna (nº da linha, índice da coluna de data, índice da coluna de valor,
    usou_data_generica) ou None se não houver cabeçalho válido.
    """
    linhas = list(ws.iter_rows(min_row=1, max_row=max_linhas, values_only=True))
    normais = [[normalizar(c) if c is not None else "" for c in (linha or [])] for linha in linhas]
    for numero, headers in enumerate(normais, start=1):
        idx_data = next((i for i, h in enumerate(headers) if h and _eh_data(h)), None)
        idx_valor = next((i for i, h in enumerate(headers) if h and _eh_valor(h)), None)
        if idx_data is not None and idx_valor is not None:
            return (numero, idx_data, idx_valor, False)
    # Contingência: abas 6/6.1/7 usam "Data" genérico sem "pagamento".
    for numero, headers in enumerate(normais, start=1):
        idx_data = next((i for i, h in enumerate(headers) if h and "data" in h), None)
        idx_valor = next((i for i, h in enumerate(headers) if h and _eh_valor(h)), None)
        if idx_data is not None and idx_valor is not None:
            return (numero, idx_data, idx_valor, True)
    return None


def parse_data(valor):
    """Converte célula em date ou None (datetime, serial do Excel, dd/mm/aaaa, aaaa-mm-dd)."""
    if valor is None:
        return None
    if isinstance(valor, bool):
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, (int, float)):
        try:
            return from_excel(valor).date()
        except (ValueError, OverflowError):
            return None
    texto = str(valor).strip()
    if not texto or texto.startswith("#"):
        return None
    for formato in FORMATOS_DATA_TEXTO:
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def para_decimal(valor):
    """Converte célula em Decimal ou None (aceita número e texto em formato BR)."""
    if valor is None:
        return None
    if isinstance(valor, bool):
        return None
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, (int, float)):
        try:
            return Decimal(str(valor))
        except InvalidOperation:
            return None
    texto = str(valor).strip().replace("R$", "").strip()
    if not texto or texto.startswith("#"):
        return None
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif texto.count(".") > 1:
        texto = texto.replace(".", "")
    try:
        return Decimal(texto)
    except InvalidOperation:
        return None


def consolidar_excel(caminho, periodo):
    """Consolida o Excel mestre filtrando o mês `periodo` (YYYY-MM).

    Retorna {"linhas": [...], "avisos": [...], "estatisticas": {...}}.
    Cada linha usa as chaves competencia, pilar, tipo_recurso,
    valor_captado, valor_executado, observacao (mesmo layout do CSV).
    Não toca o banco de dados.
    """
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", periodo or ""):
        raise ValueError(f"Período '{periodo}' inválido. Use o formato YYYY-MM.")
    totais, origens = {}, {}
    avisos = []
    stats = {
        "abas_reconhecidas": 0,
        "abas_ignoradas": 0,
        "linhas_somadas": 0,
        "linhas_ignoradas_vazias": 0,
        "linhas_ignoradas_erro": 0,
        "linhas_outro_mes": 0,
    }
    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    try:
        for nome_aba in wb.sheetnames:
            mapa = mapear_aba(nome_aba)
            if mapa is None:
                stats["abas_ignoradas"] += 1
                avisos.append(f"Aba '{nome_aba}' fora do mapa: ignorada.")
                continue
            pilar, tipo_recurso = mapa
            ws = wb[nome_aba]
            cabecalho = descobrir_colunas(ws)
            if cabecalho is None:
                stats["abas_ignoradas"] += 1
                avisos.append(f"Aba '{nome_aba}': cabeçalho de data/valor não encontrado, ignorada.")
                continue
            linha_cabecalho, idx_data, idx_valor, data_generica = cabecalho
            stats["abas_reconhecidas"] += 1
            if data_generica:
                avisos.append(f"Aba '{nome_aba}': cabeçalho de data genérico ('Data').")
            for linha in ws.iter_rows(min_row=linha_cabecalho + 1, values_only=True):
                if idx_data >= len(linha) or idx_valor >= len(linha):
                    continue
                cel_data, cel_valor = linha[idx_data], linha[idx_valor]
                if cel_data is None or (isinstance(cel_data, str) and not cel_data.strip()):
                    stats["linhas_ignoradas_vazias"] += 1
                    continue
                if cel_valor is None or (isinstance(cel_valor, str) and not cel_valor.strip()):
                    stats["linhas_ignoradas_vazias"] += 1
                    continue
                data = parse_data(cel_data)
                valor = para_decimal(cel_valor)
                if data is None or valor is None:
                    stats["linhas_ignoradas_erro"] += 1
                    continue
                if f"{data.year:04d}-{data.month:02d}" != periodo:
                    stats["linhas_outro_mes"] += 1
                    continue
                chave = (pilar, tipo_recurso)
                totais[chave] = totais.get(chave, Decimal("0")) + valor
                origens.setdefault(chave, set()).add(nome_aba)
                stats["linhas_somadas"] += 1
    finally:
        wb.close()
    linhas = []
    for (pilar, tipo), total in sorted(totais.items()):
        chave = (pilar, tipo)
        linhas.append(
            {
                "competencia": periodo,
                "pilar": pilar,
                "tipo_recurso": tipo,
                "valor_captado": Decimal("0"),
                "valor_executado": total,
                "observacao": f"Origem: {'; '.join(sorted(origens[chave]))} — consolidado automático",
            }
        )
    return {"linhas": linhas, "avisos": avisos, "estatisticas": stats}


def aplicar_consolidado(linhas, periodo, usuario=None, arquivo_nome="excel.xlsx"):
    """Persiste linhas consolidadas via update_or_create (mesma regra de importar_csv)."""
    if not periodo.permite_edicao:
        raise ValidationError("Importação bloqueada: o período está fechado (RN-010).")
    with transaction.atomic():
        for linha in linhas:
            pilar = Pilar.objects.filter(codigo__iexact=linha["pilar"]).first()
            if pilar is None:
                raise ValidationError(f"Pilar '{linha['pilar']}' não encontrado. Cadastre o pilar antes de aplicar.")
            FinanceiroConsolidado.objects.update_or_create(
                periodo=periodo,
                pilar=pilar,
                tipo_recurso=linha["tipo_recurso"],
                defaults={
                    "valor_captado": linha["valor_captado"],
                    "valor_executado": linha["valor_executado"],
                    "observacao": linha["observacao"],
                },
            )
    log = f"{len(linhas)} registro(s) consolidados de {arquivo_nome} para {periodo.rotulo}."
    ImportacaoFinanceira.objects.create(
        periodo=periodo,
        arquivo_nome=arquivo_nome,
        status="SUCESSO",
        usuario=usuario,
        log=log,
    )
    registrar_auditoria(
        usuario, "IMPORTAR_FINANCEIRO", "FinanceiroConsolidado",
        registro_id=periodo.pk, campo="excel", valor_novo=f"{len(linhas)} registros · {arquivo_nome}",
    )
    return "SUCESSO", log
