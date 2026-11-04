"""Gera o REFAT v3 com a aba de Infraestrutura a partir do v2."""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accountability.refat_infra import gerar_refat_infra


class Command(BaseCommand):
    help = (
        "Cria o FINANCEIRO GERAL - REFAT - v3 - INFRA.xlsx com as tabelas "
        "tbl_ProjetosINFRA e tbl_VisaoINFRA, preservando o v2."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--origem",
            help="Caminho do REFAT v2 (padrão: mockup/exemplos_arquivos).",
        )
        parser.add_argument(
            "--destino",
            help="Caminho do novo v3 (padrão: mockup/exemplos_arquivos).",
        )
        parser.add_argument(
            "--forcar",
            action="store_true",
            help="Sobrescreve o destino se ele já existir.",
        )

    def handle(self, *args, **options):
        raiz = Path(settings.BASE_DIR)
        padrao = raiz / "mockup" / "exemplos_arquivos"
        origem = Path(options["origem"]) if options["origem"] else (
            padrao / "FINANCEIRO GERAL - REFAT - v2.xlsx")
        destino = Path(options["destino"]) if options["destino"] else (
            padrao / "FINANCEIRO GERAL - REFAT - v3 - INFRA.xlsx")
        try:
            resultado = gerar_refat_infra(
                origem, destino, forcar=options["forcar"])
        except (FileNotFoundError, FileExistsError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            f"Arquivo gerado: {resultado['destino']}"))
        self.stdout.write(
            f"SHA256 v2: {resultado['sha256_antes']}\n"
            f"SHA256 v3: {resultado['sha256_depois']}")
