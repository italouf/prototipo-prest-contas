"""Serviço de auditoria (RF-100 a RF-106)."""
from .models import AuditLog


def registrar_auditoria(
    usuario,
    acao,
    entidade,
    registro_id="",
    campo="",
    valor_anterior="",
    valor_novo="",
    justificativa="",
):
    """Cria um registro de auditoria de forma centralizada (RN-011)."""
    return AuditLog.objects.create(
        usuario=usuario if usuario and getattr(usuario, "is_authenticated", False) else None,
        acao=acao,
        entidade=entidade,
        registro_id=str(registro_id or ""),
        campo=campo,
        valor_anterior=str(valor_anterior or ""),
        valor_novo=str(valor_novo or ""),
        justificativa=justificativa,
    )
