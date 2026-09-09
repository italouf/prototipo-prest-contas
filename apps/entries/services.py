"""Serviços de lançamento (RF-050 a RF-058 / RN-010, RN-011)."""
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.audit.services import registrar_auditoria
from apps.core.permissions import pode_lancar, usuario_pode_pilar
from apps.indicators.models import Indicador
from .models import Lancamento


def salvar_ou_enviar(periodo, pilar, usuario, dados, enviar=False):
    """Grava ou atualiza os lançamentos do pilar no período.

    dados: {"<indicador_id>": {"valor": str, "comentario": str}}
    """
    _validar_acesso(periodo, pilar, usuario)
    indicadores = Indicador.objects.filter(pilar=pilar, ativo=True)
    existentes = {lc.indicador_id: lc for lc in Lancamento.objects.filter(periodo=periodo, indicador__in=indicadores)}
    alterados = 0

    with transaction.atomic():
        for ind in indicadores:
            info = dados.get(str(ind.pk)) or {}
            valor = (info.get("valor") or "").strip()
            comentario = (info.get("comentario") or "").strip()
            if not valor and not comentario:
                continue
            lc = existentes.get(ind.pk)
            if lc and not lc.comentario_revisao:
                lc.comentario_revisao = ""
            valor_numerico, valor_texto = _parse_valor(ind, valor)
            novo = lc is None
            if lc is None:
                lc = Lancamento(periodo=periodo, indicador=ind, usuario_criacao=usuario)
            valor_anterior = lc.valor_numerico if lc.valor_numerico is not None else lc.valor_texto or ""
            lc.valor_numerico = valor_numerico
            lc.valor_texto = valor_texto
            lc.comentario = comentario
            lc.status = "ENVIADO" if enviar else "RASCUNHO"
            lc.save()
            alterados += 1
            registrar_auditoria(
                usuario,
                "CRIAR_LANCAMENTO" if novo else "ALTERAR_LANCAMENTO",
                "Lancamento",
                registro_id=lc.pk,
                campo="valor",
                valor_anterior=valor_anterior,
                valor_novo=str(valor_numerico if valor_numerico is not None else valor_texto),
            )
            if enviar:
                registrar_auditoria(
                    usuario, "ENVIAR_LANCAMENTO", "Lancamento",
                    registro_id=lc.pk, campo="status", valor_novo="ENVIADO",
                )
    return alterados


def aprovar(lc, usuario):
    if lc.status != "ENVIADO":
        raise ValidationError("Apenas lançamentos enviados podem ser aprovados.")
    lc.status = "APROVADO"
    lc.usuario_aprovacao = usuario
    lc.comentario_revisao = ""
    lc.save()
    registrar_auditoria(
        usuario, "APROVAR_LANCAMENTO", "Lancamento",
        registro_id=lc.pk, campo="status", valor_anterior="ENVIADO", valor_novo="APROVADO",
    )
    return lc


def devolver(lc, usuario, justificativa):
    if lc.status != "ENVIADO":
        raise ValidationError("Apenas lançamentos enviados podem ser devolvidos.")
    if not justificativa or not justificativa.strip():
        raise ValidationError("A devolução exige um comentário (RF-054).")
    lc.status = "DEVOLVIDO"
    lc.usuario_aprovacao = usuario
    lc.comentario_revisao = justificativa.strip()
    lc.save()
    registrar_auditoria(
        usuario, "DEVOLVER_LANCAMENTO", "Lancamento",
        registro_id=lc.pk, campo="status", valor_anterior="ENVIADO", valor_novo="DEVOLVIDO",
        justificativa=justificativa.strip(),
    )
    return lc


def _validar_acesso(periodo, pilar, usuario):
    if not pode_lancar(usuario):
        raise ValidationError("Seu perfil não permite lançamentos.")
    if not periodo.permite_edicao:
        raise ValidationError("O período está fechado e não pode ser alterado (RN-010).")
    if not usuario_pode_pilar(usuario, pilar):
        raise ValidationError("Você não tem acesso a este pilar (RF-058).")


def _parse_valor(indicador, valor):
    """Interpreta o valor conforme o tipo do indicador (RF-052)."""
    if indicador.tipo == "TXT":
        return None, valor
    if not valor:
        return None, ""
    texto = valor
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif texto.count(".") > 1:
        texto = texto.replace(".", "")
    try:
        numero = Decimal(texto)
    except InvalidOperation:
        raise ValidationError(f"Valor numérico inválido no indicador {indicador.codigo}.")
    if indicador.tipo == "PER" and numero > 100:
        raise ValidationError(f"Percentual acima de 100 no indicador {indicador.codigo}.")
    return numero, ""
