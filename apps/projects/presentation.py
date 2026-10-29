from django.db.models import Count, Max, Prefetch, Q

from .models import BookPrograma, MaterialProjeto, Projeto


def carteira(centro, pilar):
    return Projeto.objects.filter(centro=centro, pilar=pilar, ativo=True).prefetch_related(
        Prefetch("materiais", queryset=MaterialProjeto.objects.filter(ativo=True)),
    )


def quadro_entregaveis(contexto):
    """Não depende das datas dos KPIs: a carteira é permanente por centro/pilar."""
    acomp = contexto.get("acompanhamento")
    if not acomp:
        return {"projetos": [], "book": None, "sem_centro": True}
    return {
        "projetos": resumo_projetos(acomp.centro, contexto["painel_pilar"]["pilar"]),
        "book": BookPrograma.objects.filter(centro=acomp.centro, ativo=True).first(),
        "sem_centro": False,
    }


def resumo_projetos(centro, pilar, incluir_arquivados=False):
    qs = Projeto.objects.filter(centro=centro, pilar=pilar)
    if not incluir_arquivados:
        qs = qs.filter(ativo=True)
    return qs.annotate(total_materiais=Count("materiais", filter=Q(materiais__ativo=True)),
                       ultima_inclusao=Max("materiais__criado_em", filter=Q(materiais__ativo=True))).order_by("nome", "pk")
