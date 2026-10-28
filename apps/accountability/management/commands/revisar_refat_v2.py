from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accountability.refat_workbook import revisar_planilha


class Command(BaseCommand):
    help = "Atualiza datas, status, etapas e farol do REFAT v2 preservando valores e fórmulas."

    def add_arguments(self, parser):
        parser.add_argument("--arquivo", type=Path, default=settings.BASE_DIR / "mockup/exemplos_arquivos/FINANCEIRO GERAL - REFAT - v2.xlsx")

    def handle(self, *args, **options):
        try:
            resultado = revisar_planilha(options["arquivo"], settings.BASE_DIR / ".worktrees/refat-integridade")
        except PermissionError as exc:
            raise CommandError("O arquivo está aberto em outro processo. Feche-o e execute novamente; a revisão validada está em .worktrees/refat-integridade.") from exc
        self.stdout.write(self.style.SUCCESS(f"REFAT v2: {resultado['projetos']} projetos conferidos; " + ("arquivo atualizado." if resultado["alterado"] else "arquivo já atualizado.")))
