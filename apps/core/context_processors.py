"""Contexto de navegação para o layout base (R1)."""
from django.db.models import Count

from apps.entries.models import Lancamento
from apps.periods.models import Periodo


def nav(request):
    if not request.user.is_authenticated:
        return {}
    from apps.core.permissions import (
        papel_do_usuario,
        pilares_visiveis,
        pode_aprovar,
        pode_gerenciar_periodos,
        pode_importar_financeiro,
        pode_lancar,
        pode_ver_auditoria,
    )

    pilares = pilares_visiveis(request.user)
    periodo_aberto = (
        Periodo.objects.filter(status__in=["ABERTO", "REABERTO"]).order_by("-competencia").first()
    )
    ultimo_periodo = Periodo.objects.order_by("-competencia").first()

    pendencias_nav = {}
    total_pendencias = 0
    if periodo_aberto is not None:
        if pode_aprovar(request.user):
            status_alvo = "ENVIADO"
        elif pode_lancar(request.user):
            status_alvo = "DEVOLVIDO"
        else:
            status_alvo = None
        if status_alvo:
            linhas = (
                Lancamento.objects.filter(
                    periodo=periodo_aberto, status=status_alvo, indicador__pilar__in=pilares
                )
                .values("indicador__pilar")
                .annotate(total=Count("pk"))
            )
            pendencias_nav = {item["indicador__pilar"]: item["total"] for item in linhas}
            total_pendencias = sum(pendencias_nav.values())

    return {
        "papel": papel_do_usuario(request.user),
        "pode_lancar": pode_lancar(request.user),
        "pode_aprovar": pode_aprovar(request.user),
        "pode_gerenciar_periodos": pode_gerenciar_periodos(request.user),
        "pode_importar_financeiro": pode_importar_financeiro(request.user),
        "pode_ver_auditoria": pode_ver_auditoria(request.user),
        "pilares_nav": pilares,
        "periodo_aberto_nav": periodo_aberto,
        "ultimo_periodo_nav": ultimo_periodo,
        "periodos_nav": Periodo.objects.order_by("-competencia"),
        "pendencias_nav": pendencias_nav,
        "total_pendencias": total_pendencias,
    }
