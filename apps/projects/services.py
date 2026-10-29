"""Catálogo permanente; snapshots de importação nunca são donos dos materiais."""
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accountability.models import CentroCompetencia, ProjetoFinanceiro
from apps.audit.services import registrar_auditoria

from .identity import normalizar_nome
from .models import BookPrograma, Projeto, ReferenciaImportacaoProjeto


def resolver_projeto_importado(centro, pilar, origem, nome, codigo=""):
    normalizado = normalizar_nome(nome)
    referencia = ReferenciaImportacaoProjeto.objects.filter(
        centro=centro, pilar=pilar, origem=origem, nome_normalizado=normalizado,
    ).select_related("projeto").first()
    if referencia:
        return referencia.projeto
    projeto, _ = Projeto.objects.get_or_create(
        centro=centro, pilar=pilar, nome_normalizado=normalizado,
        defaults={"nome": nome, "codigo_embrapii": codigo or ""},
    )
    ReferenciaImportacaoProjeto.objects.create(
        centro=centro, pilar=pilar, origem=origem, nome_origem=nome,
        nome_normalizado=normalizado, projeto=projeto,
    )
    return projeto


def auditar(usuario, acao, registro, anterior=""):
    campos = ("nome", "codigo_embrapii", "titulo", "tipo", "url", "data_publicacao", "ativo")
    valores = {c: str(getattr(registro, c)) for c in campos if hasattr(registro, c)}
    registrar_auditoria(usuario, acao, registro.__class__.__name__, registro.pk,
                        valor_anterior=anterior, valor_novo=valores)


@transaction.atomic
def salvar_book(book, usuario):
    novo = book._state.adding
    CentroCompetencia.objects.select_for_update().get(pk=book.centro_id)
    for anterior in BookPrograma.objects.filter(centro=book.centro, ativo=True).exclude(pk=book.pk):
        anterior.ativo = False
        anterior.atualizado_por = usuario
        anterior.save()
        auditar(usuario, "ARQUIVAR_BOOK", anterior, "Vigente")
    book.ativo = True
    if novo:
        book.criado_por = usuario
    book.atualizado_por = usuario
    book.save()
    auditar(usuario, "CADASTRAR_BOOK" if novo else "REATIVAR_BOOK", book)


@transaction.atomic
def associar_referencia(referencia, destino, usuario):
    # Mesmo bloqueio usado pela importação: uma associação não pode ser
    # ultrapassada pela recriação simultânea dos snapshots daquele centro.
    CentroCompetencia.objects.select_for_update().get(pk=referencia.centro_id)
    referencia = ReferenciaImportacaoProjeto.objects.select_for_update().get(pk=referencia.pk)
    anterior = Projeto.objects.select_for_update().get(pk=referencia.projeto_id)
    destino = Projeto.objects.select_for_update().get(pk=destino.pk)
    if (destino.centro_id, destino.pilar_id) != (referencia.centro_id, referencia.pilar_id):
        raise ValidationError("A associação deve permanecer no mesmo centro e pilar.")
    if anterior.pk == destino.pk:
        return
    referencia.projeto = destino
    referencia.save(update_fields=["projeto"])
    # Atualiza apenas a identidade; os valores dos snapshots permanecem intactos.
    registros = ProjetoFinanceiro.objects.filter(
        acompanhamento__centro_id=referencia.centro_id, pilar_id=referencia.pilar_id,
        origem=referencia.origem, projeto=anterior,
    )
    ids = [r.pk for r in registros if normalizar_nome(r.nome) == referencia.nome_normalizado]
    ProjetoFinanceiro.objects.filter(pk__in=ids).update(projeto=destino)
    registrar_auditoria(usuario, "ASSOCIAR_PROJETO", "ReferenciaImportacaoProjeto", referencia.pk,
                        valor_anterior=anterior.pk, valor_novo=destino.pk)
