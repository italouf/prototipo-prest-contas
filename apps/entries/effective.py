"""Uma leitura oficial compartilhada pelos painéis e exportações, sem alterar o Excel."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date
from decimal import Decimal

from .models import BaseOperacional, IndicadorOperacional, LancamentoOperacional

_cache = ContextVar("operational_cache", default=None)
_suspenso = ContextVar("operational_suspended", default=False)
_limite = ContextVar("operational_date", default=None)


class OperationalValuesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cache_token, limite_token = _cache.set({}), _limite.set(None)
        try:
            return self.get_response(request)
        finally:
            _cache.reset(cache_token)
            _limite.reset(limite_token)


def invalidar():
    if _cache.get() is not None:
        _cache.get().clear()


@contextmanager
def suspender():
    token = _suspenso.set(True)
    try:
        yield
    finally:
        _suspenso.reset(token)


def limitar(periodo):
    _limite.set(periodo["fim"].replace(day=1) if periodo and not periodo["ciclo"] else None)
    invalidar()


def d(valor):
    return None if valor is None else Decimal(str(valor))


def estado(acomp):
    if not acomp or _suspenso.get():
        return None
    pk = getattr(acomp, "pk", acomp)
    chave = (pk, _limite.get())
    cache = _cache.get()
    if cache is not None and chave in cache:
        return cache[chave]
    base = BaseOperacional.objects.filter(acompanhamento_id=pk).first()
    result = Estado(base) if base else None
    if cache is not None:
        cache[chave] = result
    return result


class Estado:
    def __init__(self, base):
        self.base = base
        self.alvos = base.snapshot["alvos"]
        self.itens = {i.chave: i for i in IndicadorOperacional.objects.filter(acompanhamento_id=base.acompanhamento_id).select_related("pilar")}
        self.aprovados = list(LancamentoOperacional.objects.filter(
            indicador__acompanhamento_id=base.acompanhamento_id, status="APROVADO"
        ).select_related("indicador", "periodo").order_by("-periodo__competencia", "-versao"))

    def valor(self, chave, limite=None):
        limite = limite or _limite.get()
        for item in self.aprovados:
            if item.indicador.chave == chave and (limite is None or item.periodo.competencia <= limite):
                return item.valor
        if limite is not None and limite < self.base.competencia_corte:
            return None
        return d(self.alvos.get(chave, {}).get("valor"))

    def total(self, codigo, campo="realizado", limite=None):
        limite = limite or _limite.get()
        if limite is not None and limite < self.base.competencia_corte:
            if campo == "realizado" and limite.month == 12:
                anos = [d(self.base.snapshot["anuais"].get(f"{codigo}:{a}")) for a in range(2024, limite.year + 1)]
                return sum(anos, Decimal(0)) if anos and all(v is not None for v in anos) else None
            return None
        total = d(self.base.snapshot["totais"].get(codigo, {}).get(campo))
        if total is None:
            return None
        for chave, item in self.itens.items():
            if item.pilar.codigo != codigo or item.base != "financeiro" or item.alvo == "KPI" or item.campo != campo:
                continue
            valor = self.valor(chave, limite)
            inicial = d(self.alvos.get(chave, {}).get("valor"))
            if item.alvo == "PILAR":
                return valor
            if valor is not None and inicial is not None:
                total += valor - inicial
        return total

    def anual(self, codigo, ano):
        original = d(self.base.snapshot["anuais"].get(f"{codigo}:{ano}"))
        ids = {i.pk for i in self.itens.values() if i.pilar.codigo == codigo and i.alvo != "KPI" and i.campo == "realizado"}
        if not any(p.indicador_id in ids
                   and p.periodo.competencia.year == ano and (_limite.get() is None or p.periodo.competencia <= _limite.get()) for p in self.aprovados):
            return original
        fim = date(ano, 12, 1)
        if _limite.get() is not None and _limite.get() < fim:
            fim = _limite.get()
        if fim.year < ano:
            return None
        total = self.total(codigo, limite=fim)
        anterior = self.total(codigo, limite=date(ano - 1, 12, 1)) if ano > 2024 else Decimal(0)
        if total is not None and anterior is not None:
            return total - anterior
        inicial = d(self.base.snapshot["totais"].get(codigo, {}).get("realizado"))
        return original + total - inicial if original is not None and total is not None and inicial is not None and ano == self.base.competencia_corte.year else None

    def kpi(self, codigo, ano):
        chave = f"kpi:{codigo}"
        if chave not in self.alvos:
            return None
        if ano is None:
            return self.valor(chave)
        dados = self.alvos[chave].get("anos", {})
        if not any(p.indicador.chave == chave and p.periodo.competencia.year == ano and (_limite.get() is None or p.periodo.competencia <= _limite.get()) for p in self.aprovados):
            return d(dados.get(str(ano)))
        if ano > self.base.competencia_corte.year:
            anterior = self.valor(chave, date(ano - 1, 12, 1))
        else:
            anteriores = [d(dados.get(str(a))) for a in range(2024, ano)]
            anterior = sum(anteriores, Decimal(0)) if all(v is not None for v in anteriores) else None
        fim = min(date(ano, 12, 1), _limite.get()) if _limite.get() else date(ano, 12, 1)
        if fim.year < ano:
            return None
        total = self.valor(chave, fim)
        return total - anterior if total is not None and anterior is not None else None

    def ajustes_financeiros(self):
        ajustes = {}
        for codigo, totais in self.base.snapshot["totais"].items():
            ajustes[(codigo, 0, "executado")] = self.total(codigo)
            if codigo in ("AT", "OUTRASFONTES"):
                ajustes[(codigo, 0, "previsto")] = self.total(codigo, "captado")
                for campo in ("captado_anos_1_2", "captado_ano3_ytd"):
                    ajustes[(codigo, 0, campo)] = d(totais.get(campo))
                if self.base.competencia_corte.year == 2026:
                    fim = min(date(2026, 12, 1), _limite.get()) if _limite.get() else date(2026, 12, 1)
                    total = self.total(codigo, "captado", fim)
                    abertura, ano3 = d(totais.get("captado")), d(totais.get("captado_ano3_ytd"))
                    ajustes[(codigo, 0, "captado_ano3_ytd")] = ano3 + total - abertura if all(v is not None for v in (ano3, total, abertura)) else None
            for ano in range(2024, 2028):
                ajustes[(codigo, ano, "executado")] = self.anual(codigo, ano)
        return ajustes

    def projetos(self, registros):
        for r in registros:
            chave = f"projeto:{r.get('projeto_id')}:realizado"
            r["realizado"] = self.valor(chave)
            real = r["realizado"]
            proj = sum((r.get(c) or Decimal(0) for c in ("projetado_2026", "projetado_2027")), Decimal(0))
            r["realizado_mais_projetado"] = real + proj if real is not None else None
            r["diferenca"] = r["realizado_mais_projetado"] - r["orcado"] if r["realizado_mais_projetado"] is not None and r.get("orcado") is not None else None
            r["percentual"] = real / r["orcado"] if real is not None and r.get("orcado") else None

    def carteira_fontes(self, codigos):
        projetos = {}
        for chave, item in self.itens.items():
            if item.alvo != "FONTE" or item.pilar.codigo not in codigos:
                continue
            linha = projetos.setdefault(item.referencia, {"codigo": item.pilar.codigo, "nome": item.nome.rsplit(" · ", 1)[0]})
            linha[item.campo] = self.valor(chave)
        saldos = []
        for codigo in codigos:
            linha = {"codigo": codigo, "nome": "Saldo histórico não distribuído"}
            for campo in ("captado", "realizado"):
                valores = [p.get(campo) for p in projetos.values() if p["codigo"] == codigo]
                total = self.total(codigo, campo)
                linha[campo] = total - sum((v or Decimal(0) for v in valores), Decimal(0)) if total is not None else None
            saldos.append(linha)
        return [*projetos.values(), *saldos]
