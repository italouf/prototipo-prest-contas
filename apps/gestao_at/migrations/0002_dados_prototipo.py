from django.db import migrations

def carregar(apps, schema_editor):
    from apps.gestao_at.seed import carregar_prototipo
    carregar_prototipo(apps, schema_editor.connection.alias, completar_formacao=True)

class Migration(migrations.Migration):
    dependencies = [
        ("gestao_at", "0001_initial"),
        ("talentos", "0002_colaborador_ativo_colaborador_formacoes_and_more"),
    ]
    # A reversão preserva cadastros e alterações feitos durante a prototipagem.
    operations = [migrations.RunPython(carregar, migrations.RunPython.noop)]
