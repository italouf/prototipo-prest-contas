"""Utilitários compartilhados do portal."""
from apps.periods.models import Periodo


def periodo_selecionado(request):
    """Retorna (periodo, periodos) a partir do filtro ?periodo=YYYY-MM-DD.

    Sem filtro, prefere o período aberto/reaberto mais recente (operação);
    na ausência de período aberto, usa o mais recente.
    """
    periodos = Periodo.objects.all()
    competencia = request.GET.get("periodo", "")
    periodo = None
    if competencia:
        periodo = periodos.filter(competencia=competencia).first()
    if periodo is None:
        periodo = (
            periodos.filter(status__in=["ABERTO", "REABERTO"]).order_by("-competencia").first()
        )
    if periodo is None:
        periodo = periodos.order_by("-competencia").first()
    return periodo, periodos
