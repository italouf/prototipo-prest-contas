from django.db import transaction
from django.db.models import Count, Max, Prefetch, Q

from apps.accountability.models import CentroCompetencia

from .at_catalog import PRODUTOS_AT
from .identity import normalizar_nome
from .models import MaterialProdutoAT, ProdutoAT


def inicializar_produtos_at(centro, using="default"):
    """Não recria produtos renomeados/arquivados nem substitui sua ordem."""
    with transaction.atomic(using=using):
        CentroCompetencia.objects.using(using).select_for_update().get(pk=centro.pk)
        for ordem, (codigo, nome) in enumerate(PRODUTOS_AT):
            ProdutoAT.objects.using(using).get_or_create(centro_id=centro.pk, codigo_padrao=codigo,
                defaults={"nome": nome, "nome_normalizado": normalizar_nome(nome), "ordem": ordem})


def carteira_at(centro):
    return ProdutoAT.objects.filter(centro=centro, ativo=True).prefetch_related(
        Prefetch("materiais", queryset=MaterialProdutoAT.objects.filter(ativo=True)))


def quadro_at(contexto):
    acomp = contexto.get("acompanhamento")
    return {"produtos": resumo_produtos_at(acomp.centro) if acomp else [], "sem_centro": acomp is None}


def resumo_produtos_at(centro, incluir_arquivados=False):
    qs = ProdutoAT.objects.filter(centro=centro)
    if not incluir_arquivados:
        qs = qs.filter(ativo=True)
    return qs.annotate(total_materiais=Count("materiais", filter=Q(materiais__ativo=True)),
                       ultima_inclusao=Max("materiais__criado_em", filter=Q(materiais__ativo=True))).order_by("ordem", "nome", "pk")
