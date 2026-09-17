"""Páginas internas de desenvolvimento (somente DEBUG)."""
from decimal import Decimal

from django.conf import settings
from django.http import Http404
from django.shortcuts import render


def design_system(request):
    if not settings.DEBUG:
        raise Http404("Página disponível apenas em DEBUG.")
    from apps.planning.charts import geometria_fonte

    return render(request, "dev/design_system.html", {
        "demo_card": {
            "chave": "ppi", "titulo": "Recursos PPI executados",
            "executado": Decimal(40), "previsto": Decimal(60),
            "denominador": "projetados", "pct": 67, "faixa": "parcial", "barra": 67,
        },
        "demo_bloco": {
            "nome_previsto": "Projetado", "nome_executado": "Executado",
            "serie_previsto": [15, 20, 20, 5, 60], "serie_executado": [10, 15, 15, 0, 40],
            "rodape_pct": 67, "rodape_faixa": "parcial",
        },
        "demo_geo_fonte": geometria_fonte([15, 20, 20, 5, 60], [10, 15, 15, 0, 40], None),
    })
