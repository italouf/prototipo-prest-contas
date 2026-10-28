"""Servidor de validação da Visão Geral com banco temporário independente."""
import os
import logging
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

with TemporaryDirectory(prefix="quiin-overview-") as directory:
    os.environ["DATABASE_URL"] = "sqlite:///" + (Path(directory) / "test.sqlite3").as_posix()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ["DEBUG"] = "True"

    import django
    django.setup()
    from django.conf import settings
    # Hash rápido apenas neste servidor de teste e banco temporário.
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    logging.getLogger("django.server").setLevel(logging.WARNING)

    from django.core.management import call_command
    from apps.accounts.models import User
    from apps.accountability.models import Acompanhamento, ResumoFinanceiro
    from apps.accountability.services import ingestar
    from apps.accountability.refat_workbook import revisar_planilha
    from apps.core.permissions import adicionar_grupo
    from apps.pillars.models import Pilar

    call_command("migrate", interactive=False, verbosity=0)
    user = adicionar_grupo(User.objects.create_user(username="overview-e2e", password="overview-test-123"), "Master")
    for codigo in ("PDI", "FORMACAO", "STARTUPS", "INFRA", "AT", "OUTRASFONTES"):
        Pilar.objects.get_or_create(codigo=codigo, defaults={"nome": codigo})
    arquivo_revisado = Path(directory) / "refat-v2.xlsx"
    arquivo_revisado.write_bytes((root / "mockup/exemplos_arquivos/FINANCEIRO GERAL - REFAT - v2.xlsx").read_bytes())
    revisar_planilha(arquivo_revisado)
    ingestar("FINANCEIRO_GERAL", arquivo_revisado, "Overview E2E", "3T/2026", user)
    acomp = Acompanhamento.objects.get(centro__nome="Overview E2E")
    pdi = Pilar.objects.get(codigo="PDI")
    for ano, meta, realizado in ((2024, 1000000, 500000), (2025, 2000000, 1500000), (2026, 3000000, 2500000)):
        ResumoFinanceiro.objects.update_or_create(acompanhamento=acomp, origem="TAB. 1.1", pilar=pdi,
            ano=ano, defaults={"recurso_ou_meta": meta, "realizado": realizado,
                              "projetado": 1000000 if ano == 2026 else None})
    call_command("runserver", "127.0.0.1:8013", use_reloader=False)
