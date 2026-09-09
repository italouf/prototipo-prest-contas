"""Transições de estado do período (RF-040 a RF-045 / RN-010, RN-011)."""
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.audit.services import registrar_auditoria


def abrir_periodo(periodo, usuario):
    if periodo.status not in ("PLANEJADO", "FECHADO"):
        raise ValidationError("Apenas períodos planejados podem ser abertos.")
    if periodo.status == "FECHADO":
        raise ValidationError("Período fechado deve ser reaberto com justificativa.")
    periodo.status = "ABERTO"
    periodo.aberto_por = usuario
    periodo.save()
    registrar_auditoria(
        usuario, "ABRIR_PERIODO", "Periodo", registro_id=periodo.pk,
        campo="status", valor_anterior="PLANEJADO", valor_novo="ABERTO",
    )
    return periodo


def fechar_periodo(periodo, usuario):
    if periodo.status not in ("ABERTO", "REABERTO"):
        raise ValidationError("Apenas períodos abertos ou reabertos podem ser fechados.")
    periodo.snapshot_json = _gerar_snapshot(periodo)
    periodo.snapshot_gerado_em = timezone.now()
    periodo.status = "FECHADO"
    periodo.fechado_por = usuario
    periodo.save()
    registrar_auditoria(
        usuario, "FECHAR_PERIODO", "Periodo", registro_id=periodo.pk,
        campo="status", valor_anterior="ABERTO/REABERTO", valor_novo="FECHADO",
        justificativa="Fechamento mensal",
    )
    return periodo


def reabrir_periodo(periodo, usuario, justificativa):
    if periodo.status != "FECHADO":
        raise ValidationError("Apenas períodos fechados podem ser reabertos.")
    if not justificativa or not justificativa.strip():
        raise ValidationError("A reabertura exige justificativa (RF-045).")
    periodo.status = "REABERTO"
    periodo.reaberto_por = usuario
    periodo.justificativa_reabertura = justificativa.strip()
    periodo.save()
    registrar_auditoria(
        usuario, "REABRIR_PERIODO", "Periodo", registro_id=periodo.pk,
        campo="status", valor_anterior="FECHADO", valor_novo="REABERTO",
        justificativa=justificativa.strip(),
    )
    return periodo


def _gerar_snapshot(periodo):
    """Snapshot lógico do período (RN-010): lançamentos e financeiro consolidado."""
    lancamentos = []
    for lc in periodo.lancamentos.select_related("indicador", "indicador__pilar", "usuario_criacao", "usuario_aprovacao"):
        lancamentos.append(
            {
                "indicador": lc.indicador.codigo,
                "pilar": lc.indicador.pilar.codigo,
                "valor_numerico": str(lc.valor_numerico) if lc.valor_numerico is not None else None,
                "valor_texto": lc.valor_texto,
                "comentario": lc.comentario,
                "status": lc.status,
                "criado_por": lc.usuario_criacao.username if lc.usuario_criacao else "",
                "aprovado_por": lc.usuario_aprovacao.username if lc.usuario_aprovacao else "",
                "criado_em": lc.criado_em.isoformat(),
            }
        )
    financeiro = [
        {
            "pilar": f.pilar.codigo,
            "tipo_recurso": f.tipo_recurso,
            "valor_captado": str(f.valor_captado),
            "valor_executado": str(f.valor_executado),
            "observacao": f.observacao,
        }
        for f in periodo.financeiro.select_related("pilar")
    ]
    return {
        "competencia": periodo.rotulo,
        "gerado_em": timezone.now().isoformat(),
        "lancamentos": lancamentos,
        "financeiro": financeiro,
    }
