"""Persistência auditada, comum às telas de edição e ao Django Admin."""
import hashlib
import json

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.audit.services import registrar_auditoria
from apps.core.permissions import eh_gestor

from .models import ApresentacaoMensal, ConteudoApresentacao


def _atualizar_apresentacao(obj, usuario):
    if isinstance(obj, ConteudoApresentacao):
        ApresentacaoMensal.objects.filter(pk=obj.apresentacao_id).update(
            atualizado_em=timezone.now(), atualizado_por=usuario,
        )


def retrato(obj):
    if obj is None:
        return ""
    if isinstance(obj, ApresentacaoMensal):
        dados = {"competencia": obj.competencia.isoformat(), "acompanhamento": obj.acompanhamento_id, "titulo": obj.titulo}
    else:
        dados = {campo: getattr(obj, campo) for campo in (
            "apresentacao_id", "pilar_id", "tipo", "titulo", "texto", "ordem", "imagem_mime", "imagem_alt",
        )}
        dados["imagem_sha256"] = hashlib.sha256(bytes(obj.imagem)).hexdigest() if obj.imagem_mime else ""
    return json.dumps(dados, ensure_ascii=False, sort_keys=True)


@transaction.atomic
def salvar_editorial(obj, usuario):
    if not eh_gestor(usuario):
        raise PermissionDenied
    anterior = type(obj).objects.filter(pk=obj.pk).first() if obj.pk else None
    if isinstance(obj, ApresentacaoMensal):
        if anterior is None:
            obj.criado_por = usuario
        obj.atualizado_por = usuario
    obj.full_clean()
    obj.save()
    _atualizar_apresentacao(obj, usuario)
    registrar_auditoria(
        usuario, "EDITAR_APRESENTACAO" if anterior else "CRIAR_APRESENTACAO",
        type(obj).__name__, registro_id=obj.pk,
        valor_anterior=retrato(anterior), valor_novo=retrato(obj),
    )
    return obj


@transaction.atomic
def excluir_editorial(obj, usuario):
    if not eh_gestor(usuario):
        raise PermissionDenied
    registrar_auditoria(
        usuario, "EXCLUIR_APRESENTACAO", type(obj).__name__, registro_id=obj.pk,
        valor_anterior=retrato(obj),
    )
    _atualizar_apresentacao(obj, usuario)
    obj.delete()
