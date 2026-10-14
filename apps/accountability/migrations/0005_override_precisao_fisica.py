from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accountability", "0004_projetofinanceiro_codigo_projeto_embrapii")]
    operations = [
        migrations.AlterField(
            model_name="overrideacompanhamento", name="valor",
            field=models.DecimalField("Valor", max_digits=18, decimal_places=6),
        ),
    ]
