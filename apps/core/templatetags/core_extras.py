"""Filtros de template para formatação local (sem dependências externas)."""
from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


def _numero_brl(valor, decimais=2):
    """Formata número no padrão pt-BR: 75.000.000,00 (separador de milhar '.')."""
    texto = f"{valor:,.{decimais}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


@register.filter
def brl(valor):
    """Formata valores monetários como R$ 75.000.000,00."""
    if valor is None or valor == "":
        return "—"
    try:
        v = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return valor
    return "R$ " + _numero_brl(v, 2)


@register.filter
def numero_ptbr(valor):
    """Formata número com separador de milhar '.' (75.000)."""
    if valor is None:
        return "—"
    try:
        v = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return valor
    decimais = 0 if v == v.to_integral() else 2
    return _numero_brl(v, decimais)


@register.filter
def moeda_ptbr(valor):
    """Formata moeda completa: R$ 75.000.000,00."""
    if valor is None:
        return "—"
    try:
        v = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return valor
    return "R$ " + _numero_brl(v, 2)


@register.filter
def escala_ptbr(valor):
    """Formata moeda em escala executiva: R$ 75,0 mi · R$ 750 mil · R$ 1.250."""
    if valor is None:
        return "—"
    try:
        v = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return valor
    absoluto = abs(v)
    if absoluto >= Decimal("1000000"):
        numero = v / Decimal("1000000")
        texto = _numero_brl(numero, 1)
        if texto.endswith(",0"):
            texto = texto[:-2]
        return f"R$ {texto} mi"
    if absoluto >= Decimal("1000"):
        numero = int(v / Decimal("1000"))
        return f"R$ {numero} mil"
    return "R$ " + _numero_brl(v, 0)


@register.filter
def pct(valor):
    """Formata percentual como 50% (uma casa quando fracionário)."""
    if valor is None:
        return "—"
    try:
        v = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return valor
    texto = _numero_brl(v, 1)
    if texto.endswith(",0"):
        texto = texto[:-2]
    return texto + "%"


@register.filter
def nbr(valor):
    """Formata número com separador local (pt-BR)."""
    if valor is None:
        return "—"
    try:
        v = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return valor
    decimais = 0 if v == v.to_integral() else 2
    return _numero_brl(v, decimais)


@register.filter
def status_lancamento(status):
    nomes = {
        "RASCUNHO": "Rascunho",
        "ENVIADO": "Enviado",
        "APROVADO": "Aprovado",
        "DEVOLVIDO": "Devolvido",
    }
    return nomes.get(status, status)


@register.filter
def lancamento_info(lancamentos, ind_pk):
    """Resume o lançamento de um indicador para exibição em formulário."""
    lc = (lancamentos or {}).get(ind_pk)
    if lc is None:
        return {"valor": "", "comentario": "", "revisao": "", "status": ""}
    valor = str(lc.valor_numerico) if lc.valor_numerico is not None else lc.valor_texto
    return {
        "valor": valor,
        "comentario": lc.comentario,
        "revisao": lc.comentario_revisao,
        "status": lc.status,
    }


ACAO_AMIGAVEL = {
    "LOGIN": "Login realizado",
    "CRIAR_LANCAMENTO": "Lançamento criado",
    "ALTERAR_LANCAMENTO": "Lançamento alterado",
    "ENVIAR_LANCAMENTO": "Lançamento enviado",
    "APROVAR_LANCAMENTO": "Lançamento aprovado",
    "DEVOLVER_LANCAMENTO": "Lançamento devolvido",
    "ABRIR_PERIODO": "Período aberto",
    "FECHAR_PERIODO": "Período fechado",
    "REABRIR_PERIODO": "Período reaberto",
    "IMPORTAR_FINANCEIRO": "Financeiro importado",
    "IMPORTAR_FINANCEIRO_ERRO": "Importação rejeitada",
}


@register.filter
def acao_amigavel(acao):
    return ACAO_AMIGAVEL.get(acao, acao)


@register.filter
def acao_classe(acao):
    classes = {
        "APROVAR_LANCAMENTO": "acao-ok",
        "FECHAR_PERIODO": "acao-ok",
        "LOGIN": "acao-info",
        "ABRIR_PERIODO": "acao-info",
        "REABRIR_PERIODO": "acao-info",
        "ENVIAR_LANCAMENTO": "acao-info",
        "DEVOLVER_LANCAMENTO": "acao-warn",
        "IMPORTAR_FINANCEIRO_ERRO": "acao-warn",
        "CRIAR_LANCAMENTO": "acao-muted",
        "ALTERAR_LANCAMENTO": "acao-muted",
    }
    return classes.get(acao, "acao-muted")
