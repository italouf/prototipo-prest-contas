from django.db import migrations


CONTATOS = {
    "BV": [("Joao Gianvecchio", "joao.gianvecchio@bv.com.br"), ("Peterson Nogueira", "peterson.nogueira@bv.com.br")],
    "Dobslit": [("Rogerio Ruivo", "rogerio@dobslit.com"), ("", "carlos@dobslit.com")],
    "Quantuloop": [("Claudio Lima", "claudio@quantuloop.com"), ("Evandro Rosa", "evandro@quantuloop.com")],
    "INNEX": [("Thiago Barbosa", "thiago@innex.co")],
    "CPQD": [("", "mobilon@cpqd.com.br"), ("", "rafaelcf@cpqd.com.br")],
    "HC In.lab": [("MARCIO BICZYK DO AMARAL", "marcio.biczyk@hc.fm.usp.br")],
    "Embeddo": [("Daniel", "daniel@embeddo.io"), ("Rafael Alves", "rafael@embeddo.io")],
    "ABCI": [("", "vreis@abci-edu.org"), ("", "boliveira@abci-edu.org")],
    "UFAL": [("Angela Stainki", "gr@reitoria.ufal.br")],
    "UEA": [("Ricardo Bulcão", "rbjunior@uea.edu.br"), ("Manoel Azevedo", "mazevedo@uea.edu.br"), ("", "agenciainovacao@uea.edu.br")],
    "Dynex": [("Anika Selimi", "anika@dynexmoonshots.com"), ("Daniela Herrmann", "daniela@dynexmoonshots.com")],
}


def cadastrar_contatos(apps, schema_editor):
    Associado = apps.get_model("gestao_at", "Associado")
    Contato = apps.get_model("gestao_at", "ContatoAssociado")
    alias = schema_editor.connection.alias
    for nome, contatos in CONTATOS.items():
        associado = Associado.objects.using(alias).filter(nome=nome).first()
        if associado is None:
            continue
        for nome_contato, email in contatos:
            Contato.objects.using(alias).get_or_create(
                associado=associado, email=email, defaults={"nome": nome_contato},
            )


class Migration(migrations.Migration):
    dependencies = [("gestao_at", "0003_contatos_associados")]
    operations = [migrations.RunPython(cadastrar_contatos, migrations.RunPython.noop)]
