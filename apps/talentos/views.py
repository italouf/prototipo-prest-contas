"""Organograma geral do Banco de Talentos."""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch, Q
from django.shortcuts import render
from django.utils import timezone
from django.views import View

from apps.pillars.models import Pilar

from .models import Alocacao, Colaborador, Competencia


class OrganogramaView(LoginRequiredMixin, View):
    def get(self, request):
        pilar_selecionado = request.GET.get("pilar", "") or ""
        competencia_selecionada = request.GET.get("competencia", "") or ""
        hoje = timezone.localdate()
        vigentes = Alocacao.objects.filter(
            Q(data_fim__isnull=True) | Q(data_fim__gte=hoje)
        ).order_by("-data_inicio")
        qs = Colaborador.objects.select_related("pilar_principal").prefetch_related(
            "competencias",
            Prefetch("alocacoes", queryset=vigentes, to_attr="alocacoes_vigentes"),
        )
        if pilar_selecionado:
            if Pilar.objects.filter(codigo=pilar_selecionado).exists():
                qs = qs.filter(pilar_principal__codigo=pilar_selecionado)
            else:
                qs = qs.none()
        if competencia_selecionada:
            try:
                competencia_id = int(competencia_selecionada)
            except (TypeError, ValueError):
                competencia_id = None
            if competencia_id is not None and Competencia.objects.filter(pk=competencia_id).exists():
                qs = qs.filter(competencias__pk=competencia_id)
        return render(
            request,
            "talentos/organograma.html",
            {
                "colaboradores": qs,
                "pilares": Pilar.objects.filter(ativo=True),
                "competencias": Competencia.objects.all(),
                "pilar_selecionado": pilar_selecionado,
                "competencia_selecionada": competencia_selecionada,
            },
        )
