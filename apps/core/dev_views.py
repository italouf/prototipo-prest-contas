"""Páginas internas de desenvolvimento (somente DEBUG)."""
from django.conf import settings
from django.http import Http404
from django.shortcuts import render


def design_system(request):
    if not settings.DEBUG:
        raise Http404("Página disponível apenas em DEBUG.")
    return render(request, "dev/design_system.html")
