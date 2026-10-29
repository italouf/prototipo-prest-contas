from django.db.models import Prefetch

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
        "projetos": carteira(acomp.centro, contexto["painel_pilar"]["pilar"]),
        "book": BookPrograma.objects.filter(centro=acomp.centro, ativo=True).first(),
        "sem_centro": False,
    }
