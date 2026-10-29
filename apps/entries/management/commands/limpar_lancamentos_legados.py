"""Limpeza pontual e verificável do catálogo de lançamentos desativado."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction

from apps.audit.models import AuditLog
from apps.audit.services import registrar_auditoria
from apps.entries.models import Lancamento
from apps.indicators.models import Indicador


def serializar(valor):
    return json.dumps(valor, cls=DjangoJSONEncoder, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def fingerprints():
    return {model._meta.db_table: hashlib.sha256(serializar(list(model.objects.order_by("pk").values())).encode()).hexdigest()
            for label in ("accountability", "projects", "planning") for model in apps.get_app_config(label).get_models()}


class Command(BaseCommand):
    help = "Inventaria lançamentos legados; --executar exige contagem confirmada e grava backup antes da exclusão."

    def add_arguments(self, parser):
        parser.add_argument("--executar", action="store_true")
        parser.add_argument("--confirmar-quantidade", type=int)
        parser.add_argument("--diretorio", default=".worktrees/operation-backups")

    def handle(self, *args, **options):
        count = Lancamento.objects.count()
        if not options["executar"]:
            self.stdout.write(f"{count} lançamentos legados. Nenhum registro alterado.")
            return
        if options["confirmar_quantidade"] != count:
            raise CommandError("A contagem mudou ou não foi confirmada. Execute o inventário novamente.")
        directory = Path(options["diretorio"]).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        with transaction.atomic():
            rows = list(Lancamento.objects.select_for_update().order_by("pk").values())
            if len(rows) != count:
                raise CommandError("Inventário alterado durante a limpeza.")
            before = fingerprints()
            audit_count = AuditLog.objects.count()
            document = dict(lancamentos=rows, indicadores=list(Indicador.objects.order_by("pk").values()),
                            fingerprints=before, auditorias_preservadas=audit_count)
            payload = serializar(document).encode("utf-8")
            digest = hashlib.sha256(payload).hexdigest()
            path = directory / (datetime.now(timezone.utc).strftime("local-%Y%m%dT%H%M%S-") + digest[:12] + ".json")
            path.write_bytes(payload)
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise CommandError("Backup não pôde ser verificado; limpeza cancelada.")
            Lancamento.objects.filter(pk__in=[row["id"] for row in rows]).delete()
            if before != fingerprints() or AuditLog.objects.count() != audit_count:
                raise CommandError("Validação de integridade falhou; exclusão revertida.")
            registrar_auditoria(None, "LIMPAR_LANCAMENTOS_LEGADOS", "Lancamento", valor_anterior=count, valor_novo=0,
                justificativa=f"Retrofit autorizado. Backup {path.name}; SHA256 {digest}. Dados importados e auditorias preservados.", origem="Management command")
        self.stdout.write(self.style.SUCCESS(f"{count} lançamentos removidos. Backup verificado: {path}. Importações e auditorias preservadas."))
