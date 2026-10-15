"""Serviços de lançamento (RF-050 a RF-058 / RN-010, RN-011)."""
from decimal import Decimal, InvalidOperation
import re

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.audit.services import registrar_auditoria
from apps.core.permissions import pode_aprovar, pode_lancar, usuario_pode_pilar
from apps.indicators.models import Indicador
from .models import Lancamento


def salvar_ou_enviar(periodo, pilar, usuario, dados, enviar=False):
    """Grava ou atualiza os lançamentos do pilar no período.

    dados: {"<indicador_id>": {"valor": str, "comentario": str}}
    """
    _validar_acesso(periodo, pilar, usuario)
    indicadores = Indicador.objects.filter(pilar=pilar, ativo=True)
    alterados = 0

    with transaction.atomic():
        # Serializa as escritas do período e revalida seu fechamento.
        periodo = type(periodo).objects.select_for_update().get(pk=periodo.pk)
        _validar_acesso(periodo, pilar, usuario)
        existentes = {lc.indicador_id: lc for lc in Lancamento.objects.select_for_update().filter(periodo=periodo, indicador__in=indicadores)}
        for ind in indicadores:
            if str(ind.pk) not in dados:
                continue
            info = dados.get(str(ind.pk)) or {}
            valor = (info.get("valor") or "").strip()
            comentario = (info.get("comentario") or "").strip()
            lc = existentes.get(ind.pk)
            if lc and lc.status in ("ENVIADO", "APROVADO"):
                continue
            if not valor and not comentario and lc is None:
                continue
            if enviar and not valor:
                raise ValidationError(f"Informe o valor antes de enviar {ind.codigo}.")
            if lc and not lc.comentario_revisao:
                lc.comentario_revisao = ""
            valor_numerico, valor_texto = _parse_valor(ind, valor)
            novo = lc is None
            if lc is None:
                lc = Lancamento(periodo=periodo, indicador=ind, usuario_criacao=usuario)
            valor_anterior = lc.valor_numerico if lc.valor_numerico is not None else lc.valor_texto or ""
            comentario_anterior = lc.comentario
            if not novo and not enviar and lc.valor_numerico == valor_numerico and lc.valor_texto == valor_texto and lc.comentario == comentario:
                continue
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
                lc.comentario_revisao = ""
                lc.save(update_fields=["comentario_revisao"])
                registrar_auditoria(
                    usuario, "ENVIAR_LANCAMENTO", "Lancamento",
                    registro_id=lc.pk, campo="status", valor_novo="ENVIADO",
                )
            if comentario_anterior != comentario:
                registrar_auditoria(usuario, "ALTERAR_LANCAMENTO", "Lancamento", lc.pk, "comentario", comentario_anterior, comentario)
    return alterados


@transaction.atomic
def aprovar(lc, usuario):
    if not pode_aprovar(usuario):
        raise ValidationError("Seu perfil não permite aprovações.")
    lc = Lancamento.objects.select_for_update().get(pk=lc.pk)
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


@transaction.atomic
def devolver(lc, usuario, justificativa):
    if not pode_aprovar(usuario):
        raise ValidationError("Seu perfil não permite devoluções.")
    lc = Lancamento.objects.select_for_update().get(pk=lc.pk)
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


@transaction.atomic
def mover_lancamento(lc, usuario, destino, justificativa=""):
    """Movimenta um lançamento no kanban (drag-and-drop).

    Transições permitidas:
    - RASCUNHO/DEVOLVIDO -> ENVIADO (requer pode_lancar, pilar e período editável)
    - ENVIADO -> APROVADO (requer pode_aprovar)
    - ENVIADO -> DEVOLVIDO (requer pode_aprovar + justificativa)
    """
    destino = (destino or "").strip().upper()
    lc = Lancamento.objects.select_for_update().select_related("indicador__pilar", "periodo").get(pk=lc.pk)
    if destino not in ("ENVIADO", "APROVADO", "DEVOLVIDO"):
        raise ValidationError("Destino inválido para movimentação.")
    if destino == "ENVIADO":
        if lc.status not in ("RASCUNHO", "DEVOLVIDO"):
            raise ValidationError("Apenas rascunhos ou devolvidos podem ser enviados.")
        _validar_acesso(lc.periodo, lc.indicador.pilar, usuario)
        if (lc.indicador.tipo == "TXT" and not lc.valor_texto.strip()) or (lc.indicador.tipo != "TXT" and lc.valor_numerico is None):
            raise ValidationError("Informe o valor antes de enviar o lançamento.")
        status_anterior = lc.status
        lc.status = "ENVIADO"
        lc.comentario_revisao = ""
        lc.save(update_fields=["status", "comentario_revisao", "atualizado_em"])
        registrar_auditoria(
            usuario, "ENVIAR_LANCAMENTO", "Lancamento",
            registro_id=lc.pk, campo="status", valor_anterior=status_anterior, valor_novo="ENVIADO",
        )
        return lc
    if destino == "APROVADO":
        return aprovar(lc, usuario)
    return devolver(lc, usuario, justificativa)


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
    elif re.fullmatch(r"[1-9]\d{0,2}(?:\.\d{3})+", texto):
        texto = texto.replace(".", "")
    try:
        numero = Decimal(texto)
    except InvalidOperation:
        raise ValidationError(f"Valor numérico inválido no indicador {indicador.codigo}.")
    if not numero.is_finite() or numero < 0:
        raise ValidationError(f"Informe um valor finito e não negativo no indicador {indicador.codigo}.")
    if numero > Decimal("9999999999999999.99"):
        raise ValidationError(f"Valor acima do limite no indicador {indicador.codigo}.")
    if numero != numero.quantize(Decimal("0.01")):
        raise ValidationError(f"Use até duas casas decimais no indicador {indicador.codigo}.")
    if indicador.tipo == "QTD" and numero != numero.to_integral_value():
        raise ValidationError(f"Informe uma quantidade inteira no indicador {indicador.codigo}.")
    if indicador.tipo == "PER" and numero > 100:
        raise ValidationError(f"Percentual acima de 100 no indicador {indicador.codigo}.")
    return numero, ""
