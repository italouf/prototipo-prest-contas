"""Funil de oportunidades da Associação Tecnológica."""
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.shortcuts import render
from django.views import View

from apps.core.permissions import sem_permissao, usuario_pode_pilar
from apps.pillars.models import Pilar

from .models import Oportunidade

_FASES_FECHADAS = ("FECHAMENTO", "PERDIDO")


class FunilATView(LoginRequiredMixin, View):
    def get(self, request):
        pilar_at = Pilar.objects.filter(codigo="AT").first()
        if pilar_at is None or not usuario_pode_pilar(request.user, pilar_at):
            return sem_permissao(request)
        qs = Oportunidade.objects.select_related("empresa").all()
        grupos = []
        for valor, rotulo in Oportunidade.FASES:
            itens = [o for o in qs if o.fase == valor]
            total = sum((o.valor_previsto for o in itens), Decimal("0"))
            grupos.append({"fase": valor, "rotulo": rotulo, "oportunidades": itens, "total": total})
        pipeline_open = qs.exclude(fase__in=_FASES_FECHADAS).aggregate(t=Sum("valor_previsto"))["t"] or Decimal("0")
        renovacoes = qs.filter(tipo="RENOVACAO").exclude(fase__in=_FASES_FECHADAS)
        renovacoes_qtd = renovacoes.count()
        renovacoes_total = renovacoes.aggregate(t=Sum("valor_previsto"))["t"] or Decimal("0")
        return render(
            request,
            "crm_at/funil.html",
            {
                "grupos": grupos,
                "pipeline_open": pipeline_open,
                "renovacoes_qtd": renovacoes_qtd,
                "renovacoes_total": renovacoes_total,
            },
        )
