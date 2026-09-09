"""Consolida o Excel financeiro mestre (dry-run por padrão).

Uso:
    python manage.py processar_excel_mestre --arquivo planilha.xlsx --periodo "2026-04" [--aplicar]
"""
import json
import os
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.finance.excel_mestre import aplicar_consolidado, consolidar_excel
from apps.periods.models import Periodo


class Command(BaseCommand):
    help = "Consolida o Excel financeiro mestre por (pilar, tipo_recurso) com filtro de mês."

    def add_arguments(self, parser):
        parser.add_argument("--arquivo", required=True, help="Caminho do arquivo .xlsx")
        parser.add_argument("--periodo", required=True, help='Mês de referência no formato "YYYY-MM"')
        parser.add_argument("--aplicar", action="store_true", help="Persiste no banco (padrão: dry-run)")

    def handle(self, *args, **opcoes):
        caminho = opcoes["arquivo"]
        periodo_txt = opcoes["periodo"]
        try:
            ano, mes = periodo_txt.split("-")
            competencia = date(int(ano), int(mes), 1)
        except (ValueError, AttributeError):
            raise CommandError(f"Período '{periodo_txt}' inválido. Use o formato YYYY-MM (ex.: 2026-04).")
        if not os.path.exists(caminho):
            raise CommandError(f"Arquivo '{caminho}' não encontrado.")
        try:
            resultado = consolidar_excel(caminho, periodo_txt)
        except ValueError as exc:
            raise CommandError(str(exc))
        except Exception as exc:
            raise CommandError(f"Não foi possível ler o Excel '{caminho}': {exc}")
        for aviso in resultado["avisos"]:
            self.stderr.write(f"Aviso: {aviso}")
        linhas = [
            {
                "competencia": l["competencia"],
                "pilar": l["pilar"],
                "tipo_recurso": l["tipo_recurso"],
                "valor_captado": float(l["valor_captado"]) if isinstance(l["valor_captado"], Decimal) else l["valor_captado"],
                "valor_executado": float(l["valor_executado"]) if isinstance(l["valor_executado"], Decimal) else l["valor_executado"],
                "observacao": l["observacao"],
            }
            for l in resultado["linhas"]
        ]
        if not opcoes["aplicar"]:
            self.stdout.write(json.dumps(linhas, ensure_ascii=False, indent=2))
            return
        periodo = Periodo.objects.filter(competencia=competencia).first()
        if periodo is None:
            raise CommandError(
                f"Período {periodo_txt} não existe. Cadastre o período com competência {competencia.isoformat()} antes de aplicar."
            )
        try:
            _, log = aplicar_consolidado(resultado["linhas"], periodo, usuario=None, arquivo_nome=os.path.basename(caminho))
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages))
        self.stderr.write(log)
        self.stdout.write(json.dumps(linhas, ensure_ascii=False, indent=2))
