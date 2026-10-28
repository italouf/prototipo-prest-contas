"""Grade de edição do ciclo e dos anos do Geral e dos pilares."""
from apps.planning.services import ANOS, PILARES_PPI, ROTULOS_PAINEL
from .models import KpiAcompanhamento, ResumoFinanceiro


def valor_original(base, ano, campo, pilar=None, kpi=None, resumos=None):
    if base == "fisico":
        if campo == "previsto":
            return kpi.meta_total if ano == 0 else getattr(kpi, f"meta_{ano}")
        if campo == "executado":
            return kpi.acumulado if ano == 0 else getattr(kpi, f"executado_{ano}", None)
        return getattr(kpi, f"projecao_{ano}", None)
    origem = ("TAB. 1" if pilar.codigo in PILARES_PPI else "TAB. 9") if ano == 0 else "TAB. 1.1"
    linha = (resumos or {}).get((origem, pilar.codigo, ano or None))
    if linha is None:
        return None
    atributo = "realizado" if campo == "executado" else "projetado"
    if campo in ("meta_captacao", "captado_anos_1_2", "captado_ano3_ytd"):
        atributo = "recurso_ou_meta" if campo == "meta_captacao" else campo
    if campo == "meta_anual":
        atributo = "recurso_ou_meta"
    if campo == "previsto" and ano == 0:
        atributo = "recurso_ou_meta" if pilar.codigo in PILARES_PPI else "captado"
    return getattr(linha, atributo)


def grade_dashboard(acomp, base, codigos):
    anos = [0, *ANOS]
    ajustes = list(acomp.overrides.filter(base=base).select_related("pilar", "kpi"))
    por_chave = {(a.kpi.codigo if a.kpi else a.pilar.codigo, a.ano, a.campo): a.valor for a in ajustes}
    blocos = []
    if base == "financeiro":
        resumos = {(r.origem, r.pilar.codigo, r.ano): r for r in ResumoFinanceiro.objects.filter(acompanhamento=acomp).select_related("pilar")}
        from apps.pillars.models import Pilar
        itens = Pilar.objects.filter(codigo__in=codigos, ativo=True).order_by("ordem")
    else:
        resumos = {}
        itens = KpiAcompanhamento.objects.filter(acompanhamento=acomp, pilar__codigo__in=codigos).select_related("pilar").order_by("sequencia")
    for item in itens:
        codigo = item.codigo
        percentual = base == "fisico" and item.pilar.codigo in ("AT", "OUTRASFONTES") and item.unidade == "Percentual"
        linhas = []
        campos = [("previsto", "Recurso / captado" if base == "financeiro" else "Meta"), ("executado", "Realizado"), ("projetado", "Projeção")]
        if base == "financeiro" and codigo in PILARES_PPI:
            campos.insert(1, ("meta_anual", "Meta anual"))
        if base == "financeiro" and codigo in ("AT", "OUTRASFONTES"):
            campos.extend((("meta_captacao", "Meta de captação e execução"), ("captado_anos_1_2", "Captado anos 1 e 2"), ("captado_ano3_ytd", "Captado ano 3 · YTD")))
        for campo, rotulo in campos:
            celulas = []
            for ano in anos:
                editavel = not (campo == "projetado" and (base == "fisico" and ano not in (2026, 2027)))
                if base == "financeiro":
                    editavel = not ((campo == "previsto" and ano != 0) or (campo == "projetado" and ano in (2024, 2025)))
                    if campo == "meta_anual":
                        editavel = ano in (2024, 2025, 2026)
                    if campo in ("meta_captacao", "captado_anos_1_2", "captado_ano3_ytd"):
                        editavel = ano == 0
                valor = por_chave.get((codigo, ano, campo), valor_original(base, ano, campo,
                    pilar=item if base == "financeiro" else None, kpi=item if base == "fisico" else None, resumos=resumos))
                if percentual and valor is not None:
                    valor *= 100
                celulas.append({"ano": ano, "valor": valor, "editavel": editavel,
                    "nome": f"v__{ano}__{base}__{codigo}__{campo}"})
            linhas.append({"rotulo": rotulo, "campo": campo, "celulas": celulas})
        blocos.append({"titulo": ROTULOS_PAINEL.get(codigo, codigo) if base == "financeiro" else item.nome,
                       "unidade": "R$" if base == "financeiro" else "%" if percentual else item.unidade,
                       "step": "0.01" if base == "financeiro" else "0.0001" if percentual else "0.000001" if item.unidade == "Percentual" else "1",
                       "linhas": linhas})
    return blocos
