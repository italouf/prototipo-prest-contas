import unicodedata

from django.db import migrations


def vincular(apps, schema_editor):
    db = schema_editor.connection.alias
    Projeto = apps.get_model("projects", "Projeto")
    Referencia = apps.get_model("projects", "ReferenciaImportacaoProjeto")
    Financeiro = apps.get_model("accountability", "ProjetoFinanceiro")
    for registro in Financeiro.objects.using(db).select_related("acompanhamento").order_by("pk"):
        if registro.projeto_id:
            continue
        normalizado = " ".join(unicodedata.normalize("NFKC", registro.nome).casefold().split())
        projeto, _ = Projeto.objects.using(db).get_or_create(
            centro_id=registro.acompanhamento.centro_id, pilar_id=registro.pilar_id,
            nome_normalizado=normalizado,
            defaults={"nome": registro.nome, "codigo_embrapii": registro.codigo_projeto_embrapii or ""},
        )
        referencia, _ = Referencia.objects.using(db).get_or_create(
            centro_id=registro.acompanhamento.centro_id, pilar_id=registro.pilar_id,
            origem=registro.origem, nome_normalizado=normalizado,
            defaults={"projeto_id": projeto.pk, "nome_origem": registro.nome},
        )
        Financeiro.objects.using(db).filter(pk=registro.pk).update(projeto_id=referencia.projeto_id)


class Migration(migrations.Migration):
    dependencies = [("projects", "0001_initial"), ("accountability", "0007_projetofinanceiro_projeto")]
    operations = [migrations.RunPython(vincular, migrations.RunPython.noop)]
