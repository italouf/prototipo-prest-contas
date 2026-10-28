"""Vocabulário e indicadores dos projetos financeiros do REFAT."""
from decimal import Decimal
import unicodedata


STATUS_PROJETOS = (
    "Encerrado", "Em andamento", "Em elaboração", "Futuros projetos",
    "Encerrado apenas no CIMATEC", "Encerrado formalmente EMBRAPII",
    "Em aprovação EMBRAPII", "Em aprovação interna (pré-projeto)",
)
ETAPAS_PROJETOS = ("Encerrados", "Em andamento", "Futuros projetos")


def etapa_do_status(status):
    texto = unicodedata.normalize("NFKD", status or "").encode("ascii", "ignore").decode().lower()
    if "encerrad" in texto:
        return ETAPAS_PROJETOS[0]
    if "andamento" in texto:
        return ETAPAS_PROJETOS[1]
    return ETAPAS_PROJETOS[2]


def farol_financeiro(realizado, orcado):
    if realizado is None or orcado is None or orcado <= 0:
        return "Sem lançamento"
    percentual = Decimal(str(realizado)) / Decimal(str(orcado)) * 100
    if percentual >= 90:
        return "Meta atingida"
    if percentual >= 50:
        return "Execução parcial"
    return "Execução crítica"
