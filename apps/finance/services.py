"""Importação atômica de financeiro consolidado via CSV (RF-080 a RF-087)."""
import csv
import io
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.audit.services import registrar_auditoria
from apps.pillars.models import Pilar
from .models import FinanceiroConsolidado, ImportacaoFinanceira

COLUNAS = ["competencia", "pilar", "tipo_recurso", "valor_captado", "valor_executado", "observacao"]

VARIANTS_TIPO = {
    "EMBRAPII": "EMBRAPII",
    "EMBRAPI": "EMBRAPII",
    "EMBRAPPI": "EMBRAPII",
    "AT": "AT",
    "OUTRAS_FONTES": "OUTRAS_FONTES",
    "OUTRASFONTES": "OUTRAS_FONTES",
}


def importar_csv(arquivo, periodo, usuario):
    """Importa CSV de forma atômica. Retorna (status, log)."""
    if not periodo.permite_edicao:
        raise ValidationError("Importação bloqueada: o período está fechado (RN-010).")

    conteudo = _ler_arquivo(arquivo)
    leitor = csv.DictReader(io.StringIO(conteudo))
    if not leitor.fieldnames or [c.lower().strip() for c in leitor.fieldnames] != COLUNAS:
        return _falha(periodo, arquivo.name, usuario, f"Colunas obrigatórias: {', '.join(COLUNAS)} (RF-081).")

    linhas, erros = [], []
    for numero, linha in enumerate(leitor, start=2):
        competencia = (linha.get("competencia") or "").strip()
        pilar_cod = (linha.get("pilar") or "").strip()
        tipo = (linha.get("tipo_recurso") or "").strip().upper()
        captado = (linha.get("valor_captado") or "").strip()
        executado = (linha.get("valor_executado") or "").strip()

        if competencia != periodo.rotulo:
            erros.append(f"Linha {numero}: competência '{competencia}' não corresponde a {periodo.rotulo}.")
            continue
        pilar = Pilar.objects.filter(codigo__iexact=pilar_cod).first()
        if pilar is None:
            erros.append(f"Linha {numero}: pilar '{pilar_cod}' não encontrado.")
            continue
        if tipo not in VARIANTS_TIPO:
            erros.append(f"Linha {numero}: tipo de recurso '{tipo}' inválido.")
            continue
        try:
            vc = _decimal(captado)
            ve = _decimal(executado)
        except InvalidOperation:
            erros.append(f"Linha {numero}: valores numéricos inválidos.")
            continue
        if vc < 0 or ve < 0:
            erros.append(f"Linha {numero}: valores não podem ser negativos.")
            continue
        linhas.append(
            {
                "pilar": pilar,
                "tipo_recurso": VARIANTS_TIPO[tipo],
                "valor_captado": vc,
                "valor_executado": ve,
                "observacao": (linha.get("observacao") or "").strip(),
            }
        )

    chaves = {}
    for numero, linha in enumerate(linhas, start=2):
        chave = (linha["pilar"].codigo, linha["tipo_recurso"])
        if chave in chaves:
            erros.append(f"Linha {numero}: combinação pilar/tipo de recurso duplicada no arquivo.")
        chaves[chave] = True

    if erros:
        return _falha(periodo, arquivo.name, usuario, " | ".join(erros[:50]))

    with transaction.atomic():
        for linha in linhas:
            FinanceiroConsolidado.objects.update_or_create(
                periodo=periodo,
                pilar=linha["pilar"],
                tipo_recurso=linha["tipo_recurso"],
                defaults={
                    "valor_captado": linha["valor_captado"],
                    "valor_executado": linha["valor_executado"],
                    "observacao": linha["observacao"],
                },
            )
    ImportacaoFinanceira.objects.create(
        periodo=periodo,
        arquivo_nome=arquivo.name,
        status="SUCESSO",
        usuario=usuario,
        log=f"{len(linhas)} linha(s) importadas.",
    )
    registrar_auditoria(
        usuario, "IMPORTAR_FINANCEIRO", "FinanceiroConsolidado",
        registro_id=periodo.pk, campo="csv", valor_novo=f"{len(linhas)} linhas · {arquivo.name}",
    )
    return "SUCESSO", f"{len(linhas)} linha(s) importadas com sucesso."


def _ler_arquivo(arquivo):
    try:
        return arquivo.read().decode("utf-8-sig")
    except (UnicodeDecodeError, AttributeError):
        return arquivo.read().decode("latin-1")


def _decimal(valor):
    if not valor:
        return Decimal("0")
    texto = valor
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif texto.count(".") > 1:
        texto = texto.replace(".", "")
    return Decimal(texto)


def _falha(periodo, nome, usuario, log):
    ImportacaoFinanceira.objects.create(periodo=periodo, arquivo_nome=nome, status="ERRO", usuario=usuario, log=log)
    registrar_auditoria(
        usuario, "IMPORTAR_FINANCEIRO_ERRO", "ImportacaoFinanceira",
        registro_id=periodo.pk, campo="csv", valor_novo=log,
    )
    return "ERRO", log
