import unicodedata

from django.db import migrations


PRODUTOS = (
    ("GRUPOS_TRABALHO", "Grupos de trabalho - Relatórios e apresentações"),
    ("WHITE_PAPER", "White paper"),
    ("TENDENCIA_TECNOLOGICA", "Relatório de Tendência tecnológica"),
    ("TENDENCIA_MERCADO", "Relatório de tendência de mercado"),
    ("BOLETIM_TECNICO", "Boletim Técnico"),
    ("DIVULGACAO_PROSPECCAO", "Materiais de Divulgação e prospecção - Público amplo"),
    ("MACROTREND_TELECOM", "Macrotrend Telecom"),
    ("FINANCIAMENTO_FOMENTO", "Boletim de oportunidades de financiamento & fomento"),
    ("PI", "Propriedade Intelectual (PI)"),
)


def cadastrar(apps, schema_editor):
    db = schema_editor.connection.alias
    Centro = apps.get_model("accountability", "CentroCompetencia")
    Produto = apps.get_model("projects", "ProdutoAT")
    for centro in Centro.objects.using(db).all():
        for ordem, (codigo, nome) in enumerate(PRODUTOS):
            normalizado = " ".join(unicodedata.normalize("NFKC", nome).casefold().split())
            Produto.objects.using(db).get_or_create(centro_id=centro.pk, codigo_padrao=codigo,
                defaults={"nome": nome, "nome_normalizado": normalizado, "ordem": ordem})


class Migration(migrations.Migration):
    dependencies = [("projects", "0003_produtoat_materialprodutoat_and_more")]
    operations = [migrations.RunPython(cadastrar, migrations.RunPython.noop)]
