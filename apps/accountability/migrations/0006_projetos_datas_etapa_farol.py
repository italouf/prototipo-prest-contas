from decimal import Decimal
import unicodedata

from django.db import migrations, models


def preencher_indicadores(apps, schema_editor):
    Projeto = apps.get_model("accountability", "ProjetoFinanceiro")
    alterados = []
    for projeto in Projeto.objects.using(schema_editor.connection.alias).all().iterator():
        status = unicodedata.normalize("NFKD", projeto.status or "").encode("ascii", "ignore").decode().lower()
        projeto.etapa = "Encerrados" if "encerrad" in status else "Em andamento" if "andamento" in status else "Futuros projetos"
        if projeto.realizado is None or projeto.orcado is None or projeto.orcado <= 0:
            projeto.farol = "Sem lançamento"
        else:
            pct = projeto.realizado / projeto.orcado * Decimal(100)
            projeto.farol = "Meta atingida" if pct >= 90 else "Execução parcial" if pct >= 50 else "Execução crítica"
        alterados.append(projeto)
    Projeto.objects.using(schema_editor.connection.alias).bulk_update(alterados, ["etapa", "farol"], batch_size=500)


class Migration(migrations.Migration):
    dependencies = [("accountability", "0005_override_precisao_fisica")]
    operations = [
        migrations.AlterField(model_name="projetofinanceiro", name="inicio", field=models.DateField("Assinatura da síntese", null=True, blank=True)),
        migrations.AlterField(model_name="projetofinanceiro", name="fim", field=models.DateField("Final previsto na síntese", null=True, blank=True)),
        migrations.AddField(model_name="projetofinanceiro", name="data_kickoff", field=models.DateField("Data do kick-off", null=True, blank=True)),
        migrations.AddField(model_name="projetofinanceiro", name="fim_previsto_real", field=models.DateField("Final previsto real", null=True, blank=True)),
        migrations.AddField(model_name="projetofinanceiro", name="etapa", field=models.CharField("Etapa do projeto", max_length=40, blank=True, db_default="")),
        migrations.AddField(model_name="projetofinanceiro", name="farol", field=models.CharField("Farol financeiro", max_length=20, blank=True, db_default="")),
        migrations.RunPython(preencher_indicadores, migrations.RunPython.noop),
    ]
