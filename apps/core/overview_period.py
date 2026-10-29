"""Intervalos mensais do Geral: snapshots anuais não são rateados por mês."""
from datetime import date

from django import forms

CICLO_INICIO = date(2024, 1, 1)
CICLO_FIM = date(2027, 6, 1)
MESES = ("", "jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


class PeriodoAnaliseForm(forms.Form):
    mes_inicial = forms.DateField(required=False, input_formats=["%Y-%m", "%m/%Y"], error_messages={"invalid": "Mês inicial inválido. Use MM/AAAA."})
    mes_final = forms.DateField(required=False, input_formats=["%Y-%m", "%m/%Y"], error_messages={"invalid": "Mês final inválido. Use MM/AAAA."})

    def clean(self):
        dados = super().clean()
        inicio = dados.get("mes_inicial") or CICLO_INICIO
        fim = dados.get("mes_final") or CICLO_FIM
        if inicio > fim:
            raise forms.ValidationError("O mês inicial deve ser anterior ou igual ao mês final.")
        return dados


def resolver_periodo(params, ano_param="todos"):
    valores = {nome: params.get(nome, "") for nome in ("mes_inicial", "mes_final")}
    explicito = any(nome in params for nome in valores)
    if not explicito and ano_param != "todos":
        valores = {"mes_inicial": f"{ano_param}-01", "mes_final": f"{ano_param}-12"}
    form = PeriodoAnaliseForm(valores)
    valido = form.is_valid()
    if valido:
        valores = {nome: form.cleaned_data[nome].strftime("%Y-%m") if form.cleaned_data[nome] else "" for nome in valores}
    inicio = form.cleaned_data.get("mes_inicial") or CICLO_INICIO
    fim = form.cleaned_data.get("mes_final") or CICLO_FIM
    ciclo = valido and inicio == CICLO_INICIO and fim == CICLO_FIM
    ano = inicio.year if valido and inicio.month == 1 and fim.year == inicio.year and (fim.month == 12 or fim == CICLO_FIM) else None
    anos = list(range(inicio.year, fim.year + 1)) if valido and inicio.month == 1 and (fim.month == 12 or fim == CICLO_FIM) and CICLO_INICIO <= inicio <= fim <= CICLO_FIM else []
    ano = ano if ano in anos else None
    meses = (fim.year - inicio.year) * 12 + fim.month - inicio.month + 1
    rotulo = ("Ciclo do termo · " if ciclo else "") + f"{MESES[inicio.month]}/{inicio.year} a {MESES[fim.month]}/{fim.year} ({meses} meses)"
    return {"inicio": inicio, "fim": fim, "ciclo": ciclo, "ano": ano, "valido": valido,
            "anos": anos, "mes_inicial": valores["mes_inicial"], "mes_final": valores["mes_final"], "rotulo": rotulo if valido else "Intervalo inválido",
            "erro": " ".join(m for mensagens in form.errors.values() for m in mensagens)}


def posicao_operacional(contexto, periodo):
    from apps.entries.effective import estado
    oficial = estado(contexto.get("acompanhamento"))
    disponivel = bool(oficial and periodo["valido"] and periodo["fim"] >= oficial.base.competencia_corte)
    if disponivel:
        contexto["nota_operacional"] = (
            f"Resultados homologados · base v{oficial.base.versao}, corte {oficial.base.competencia_corte:%m/%Y}. "
            + (f"Posição acumulada desde 2024 até {periodo['fim']:%m/%Y}; os acumulados mensais não são somados. "
               if not periodo["ciclo"] and (contexto["base_param"] == "fin" or not periodo["anos"]) else "")
            + "Detalhamentos anuais sem referência histórica permanecem indisponíveis."
        )
    return disponivel


def aplicar_periodo(contexto, periodo):
    painel = contexto["painel"]
    contexto["periodo_analise"] = periodo
    contexto["mes_inicial"] = periodo["mes_inicial"]
    contexto["mes_final"] = periodo["mes_final"]
    painel["rotulo_periodo"] = periodo["rotulo"]
    operacional = posicao_operacional(contexto, periodo)
    indisponivel = not periodo["valido"] or (not operacional and not periodo["ciclo"] and
        (contexto["base_param"] == "fin" or not periodo["anos"]))
    contexto["sem_dados_intervalo"] = indisponivel
    contexto["erro_periodo"] = periodo["erro"]
    if not indisponivel and not periodo["ciclo"] and contexto["base_param"] == "fis":
        for linha in painel.get("tabela_anual_fisica", {}).get("linhas", []):
            for celula in linha.get("anos", []):
                if celula["ano"] not in periodo["anos"]:
                    celula.update(meta=None, executado=None, saldo=None, projetado=None)
    if indisponivel:
        for card in painel["cards"]:
            card.update(executado=None, previsto=None, pct=None, faixa="neutra", barra=0)
            card.pop("status_counts", None)
        campos = ("previsto", "executado", "saldo", "pct", "recurso", "realizado", "projetado", "combinado", "diferenca",
                  "meta_2024", "meta_2025", "meta_2026", "realizado_2024", "realizado_2025", "realizado_2026", "projetado_2026", "projetado_2027", "projetado_total")
        for tabela in [painel.get(chave, {}) for chave in ("tabela_tab1", "tabela_tab11", "tabela_programa", "tabela_anual_fisica")]:
            for linha in tabela.get("linhas", []):
                for campo in campos:
                    if campo in linha:
                        linha[campo] = None
                linha.update(faixa="neutra", barra=0)
                for celula in linha.get("anos", []):
                    celula.update(meta=None, executado=None, saldo=None, projetado=None)
        for fonte in painel.get("fontes", []):
            fonte.update(meta=None, captado=None, realizado=None)
        for grupo in painel["tabela"]["grupos"]:
            for linha in grupo["linhas"]:
                linha.update(previsto=None, executado=None, saldo=None, pct=None, faixa="neutra", barra=0)
        painel["status_fisico"] = None
    return contexto
