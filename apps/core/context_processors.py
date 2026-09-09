"""Contexto de navegação para o layout base."""
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
    periodo_aberto = Periodo.objects.filter(status__in=["ABERTO", "REABERTO"]).order_by("-competencia").first()
    ultimo_periodo = Periodo.objects.order_by("-competencia").first()
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
    }
