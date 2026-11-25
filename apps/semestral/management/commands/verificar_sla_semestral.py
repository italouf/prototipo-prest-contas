"""Comando de gerenciamento para disparar alertas mensais e verificar SLA/ITS1."""
from datetime import date, datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.semestral.sla import disparar_alertas_mensais, verificar_sla_e_emitir_its1


class Command(BaseCommand):
    help = "Executa verificação de prazos SLA da Prestação Semestral e emite advertências ITS1."

    def add_arguments(self, parser):
        parser.add_argument(
            "--enviar-alertas",
            action="store_true",
            help="Dispara alertas mensais para competências pendentes.",
        )
        parser.add_argument(
            "--competencia",
            type=str,
            default="",
            help="Competência alvo no formato YYYY-MM para alertas mensais.",
        )
        parser.add_argument(
            "--referencia",
            type=str,
            default="",
            help="Data/hora ISO de referência para verificação de prazo (ex: 2026-02-10T12:00:00).",
        )
        parser.add_argument(
            "--simular-atraso-dias",
            type=int,
            default=0,
            help="Avança o relógio de verificação em N dias para testar emissão de ITS1.",
        )
        parser.add_argument(
            "--base-url",
            type=str,
            default="",
            help="URL base do portal para compor links diretos absolutos nos e-mails.",
        )

    def handle(self, *args, **options):
        base_url = options["base_url"]
        if options["enviar_alertas"]:
            comp_date = None
            if options["competencia"]:
                ano, mes = [int(p) for p in options["competencia"].split("-")]
                comp_date = date(ano, mes, 1)
            res_alertas = disparar_alertas_mensais(
                competencia_date=comp_date, base_url=base_url
            )
            self.stdout.write(
                self.style.SUCCESS(f"Alertas mensais enviados: {res_alertas['enviados']}")
            )

        agora = timezone.now()
        if options["referencia"]:
            dt = datetime.fromisoformat(options["referencia"])
            agora = timezone.make_aware(dt) if timezone.is_naive(dt) else dt
        if options["simular_atraso_dias"]:
            agora = agora + timedelta(days=options["simular_atraso_dias"])

        res_its1 = verificar_sla_e_emitir_its1(agora=agora, base_url=base_url)
        self.stdout.write(
            self.style.SUCCESS(
                f"Verificação SLA concluída — Advertências ITS1 emitidas: {res_its1['emitidas']}"
            )
        )
