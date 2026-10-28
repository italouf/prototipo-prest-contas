"""Apresentação dos dashboards de pilares, sem somar unidades incompatíveis."""
from decimal import Decimal, ROUND_HALF_UP

from django.http import QueryDict

from apps.accountability.project_status import etapa_do_status
from apps.planning.physical import resumo_fisico
from apps.planning.services import faixa, pct_inteiro
from .templatetags.core_extras import _numero_brl, numero_curto, numero_ptbr


ZERO = Decimal(0)
NOMES = {"PDI": "PDI", "FORMACAO": "Formação FCRH", "STARTUPS": "ACS", "AT": "AT e Outras Fontes"}


def dinheiro(valor, compacto=False):
    if valor is None:
        return "—"
    escala = Decimal(1000000) if compacto and abs(valor) >= 1000000 else Decimal(1000) if compacto and abs(valor) >= 1000 else Decimal(1)
    sufixo = " milhões" if escala == 1000000 else " mil" if escala == 1000 else ""
    return "R$ " + numero_ptbr((valor / escala).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) + sufixo


def separar_unidade(valor):
    for unidade in ("milhões", "mil"):
        sufixo = " " + unidade
        if valor.endswith(sufixo):
            return valor[:-len(sufixo)], unidade
    return valor, ""


def taxa(realizado, meta):
    return realizado / meta * 100 if realizado is not None and meta is not None and meta > 0 else None


def taxa_texto(valor, casas=2):
    return _numero_brl(valor.quantize(Decimal(1).scaleb(-casas), rounding=ROUND_HALF_UP), casas) + "%" if valor is not None else "—"


def valor_fisico(valor, percentual=False):
    return numero_curto(valor * 100) + "%" if percentual and valor is not None else numero_curto(valor)


def progresso(valor, status=None):
    return {"pct": valor, "barra": min(max(valor or ZERO, ZERO), Decimal(100)), "faixa": status or faixa(valor)}


def _projetos(pp):
    grupos = {c: {"codigo": c, "titulo": t, "rotulo": r, "linhas": []} for c, t, r in (
        ("encerrado", "Encerrados", "Encerrado"), ("andamento", "Em andamento", "Em andamento"), ("futuros", "Futuros projetos", "Futuros projetos"))}
    registros = pp.get("registros_projetos", [])
    for registro in registros:
        linha = dict(registro)
        etapa = linha.get("etapa") or etapa_do_status(linha["status"])
        codigo = {"Encerrados": "encerrado", "Em andamento": "andamento", "Futuros projetos": "futuros"}.get(etapa)
        if codigo is None:
            codigo = {"Encerrados": "encerrado", "Em andamento": "andamento", "Futuros projetos": "futuros"}[etapa_do_status(linha["status"])]
        pct = taxa(linha["realizado"], linha["orcado"])
        linha.update(status_grupo=codigo, pct_rotulo=taxa_texto(pct, 1), **progresso(pct))
        grupos[codigo]["linhas"].append(linha)
    presentes = []
    for grupo in grupos.values():
        grupo["quantidade"] = len(grupo["linhas"])
        for campo in ("orcado", "realizado", "projetado_2026", "projetado_2027", "realizado_mais_projetado"):
            valores = [linha[campo] for linha in grupo["linhas"] if linha[campo] is not None]
            grupo[campo] = sum(valores, ZERO) if valores else None
        if grupo["linhas"]:
            presentes.append(grupo)
    total = {}
    for campo in ("orcado", "realizado", "projetado_2026", "projetado_2027", "realizado_mais_projetado", "diferenca"):
        valores = [r[campo] for r in registros if r[campo] is not None]
        total[campo] = sum(valores, ZERO) if valores else None
    pct = taxa(total["realizado"], total["orcado"])
    total.update(total=True, nome="Total geral" if pp["codigo"] == "PDI" else "Total geral · atual" if pp["codigo"] == "FORMACAO" else "Total",
                 pct_rotulo=taxa_texto(pct, 1), **progresso(pct))
    pp.update(grupos_projetos=presentes, total_projetos=total)



def grafico_carteira(grupos):
    campos = (("realizado", "Realizado"), ("projetado_2026", "Projetado 2026"), ("projetado_2027", "Projetado 2027"))
    teto = max((max(g["orcado"] or ZERO, sum((g[c] or ZERO for c, _ in campos), ZERO)) for g in grupos), default=ZERO)
    linhas = []
    for grupo in grupos:
        valores = [grupo[c] for c, _ in campos if grupo[c] is not None]
        combinado = sum(valores, ZERO) if valores else None
        linhas.append({
            "titulo": grupo["titulo"], "quantidade": grupo["quantidade"],
            "orcado": grupo["orcado"], "combinado": combinado,
            "largura_orcado": grupo["orcado"] / teto * 100 if teto and grupo["orcado"] is not None else ZERO,
            "segmentos": [
                {"chave": campo, "titulo": titulo, "valor": grupo[campo],
                 "largura": grupo[campo] / teto * 100 if teto and grupo[campo] is not None else ZERO}
                for campo, titulo in campos
            ],
        })
    return {"linhas": linhas, "sem_dados": not grupos, "teto": teto or None}

def _anual(pp, percentual=False):
    for linha in pp.get("tabela", []):
        if "ano" not in linha:
            linha["ano"] = int(linha["rotulo"][-4:]) if not linha["total"] and linha["rotulo"][-4:].isdigit() else None
        linha["rotulo"] = linha["rotulo"].replace(": ", " · ")
        linha.update(previsto_fmt=valor_fisico(linha["previsto"], percentual), executado_fmt=valor_fisico(linha["executado"], percentual), saldo_fmt=valor_fisico(linha["saldo"], percentual))
        linha.update(progresso(linha["pct"], linha["faixa"]))
    rows = [linha for linha in pp.get("tabela", []) if not linha["total"] and (not pp.get("anos_selecionados") or linha["ano"] in pp["anos_selecionados"])]
    pp["status_anos"] = {nome: sum(linha["faixa"] == nome for linha in rows) for nome in ("ok", "parcial", "critica", "neutra")}


def _limpar(pp, periodo, financeiro):
    indisponivel = not periodo["valido"] or not periodo["ciclo"] and (financeiro or not periodo["anos"])
    campos = ("previsto", "executado", "saldo", "executado_limitado", "pct", "captado", "realizado", "recurso_ou_meta", "orcado", "projetado", "projetado_2026", "projetado_2027", "realizado_mais_projetado", "diferenca", "percentual_meta", "percentual_captado", "captado_anos_1_2", "captado_ano3_ytd")
    if indisponivel:
        def limpar(valor):
            if isinstance(valor, dict):
                for chave, item in valor.items():
                    if chave in campos:
                        valor[chave] = None
                    elif chave == "faixa":
                        valor[chave] = "neutra"
                    elif chave in ("barra", "barra_percentual"):
                        valor[chave] = 0
                    elif chave == "valor" and valor.get("tipo") in ("dinheiro", "percentual", "data"):
                        valor[chave] = None
                    else:
                        limpar(item)
            elif isinstance(valor, list):
                for item in valor:
                    limpar(item)
        limpar(pp)
        pp["registros_projetos"] = []
        pp["status_counts"] = None
    elif not periodo["ciclo"]:
        for bloco in [pp, *pp.get("blocos_fisicos", [])]:
            bloco["anos_selecionados"] = periodo["anos"]
            for linha in bloco.get("tabela", []):
                if linha["total"]:
                    linha.update(previsto=bloco.get("previsto"), executado=bloco.get("executado"), saldo=bloco.get("saldo"), pct=bloco.get("pct"), faixa=bloco.get("faixa", "neutra"))
                if not linha["total"] and linha.get("ano") not in periodo["anos"]:
                    linha.update(previsto=None, executado=None, saldo=None, pct=None, faixa="neutra")
    return indisponivel


def apresentar_pilar(contexto, periodo):
    pp = contexto["painel_pilar"]
    financeiro = contexto["base_param"] == "fin"
    codigo = pp["codigo"]
    nome = NOMES.get(codigo, pp["rotulo"])
    nome_card = "FCRH" if codigo == "FORMACAO" else nome
    contexto.update(periodo_analise=periodo, mes_inicial=periodo["mes_inicial"], mes_final=periodo["mes_final"], erro_periodo=periodo["erro"], dashboard_url=f"/pilar/{contexto['pilar_pk']}/")
    contexto["sem_dados_intervalo"] = _limpar(pp, periodo, financeiro)
    pp.update(rotulo_periodo=periodo["rotulo"], nome_curto=nome, titulo_pagina="AT e Outras Fontes" if pp.get("visao_captacao") else pp["pilar"].nome)
    pp["progresso"] = progresso(pp.get("pct"), pp.get("faixa"))
    if not financeiro and not pp.get("visao_captacao"):
        pp["progresso"]["barra"] = min(max(taxa(pp.get("executado_limitado", pp.get("executado")), pp.get("previsto")) or ZERO, ZERO), Decimal(100))
    pp["pct_detalhado"] = taxa_texto(taxa(pp.get("executado_limitado", pp.get("executado")), pp.get("previsto")))
    contexto["fonte_dashboard"] = "Fontes autorizadas do acompanhamento" if pp.get("visao_captacao") and financeiro else "tabelas financeiras importadas" if financeiro else "Indicadores Gerais do Termo de Retificação do PE"
    cards = []
    if financeiro:
        _projetos(pp)
        cards.append({"titulo": "Realizado total" if pp.get("visao_captacao") else f"Realizado · {nome_card}", "valor": dinheiro(pp.get("executado"), True), "referencia": "de " + dinheiro(pp.get("previsto"), True) + (" captados" if pp.get("visao_captacao") else " do PPI"), "descricao": "realizado em relação ao captado" if pp.get("visao_captacao") else "taxa de execução no período", "hero": True, **pp["progresso"]})
        if pp.get("visao_captacao"):
            fontes = pp.get("registros_captacao", [])
            meta = pp.get("total_captacao", {}).get("recurso_ou_meta")
            pct_meta = taxa(pp.get("previsto"), meta)
            escala = max((r[c] or ZERO for r in fontes for c in ("recurso_ou_meta", "captado")), default=ZERO)
            for r in fontes:
                r.update(codigo=r["pilar__codigo"], nome="Associação Tecnológica" if r["pilar__codigo"] == "AT" else "Outras fontes")
                r["pct_meta"] = taxa(r["captado"], r["recurso_ou_meta"])
                r["pct_exec"] = taxa(r["realizado"], r["captado"])
                r["meta_rotulo"] = taxa_texto(r["pct_meta"])
                r["exec_rotulo"] = taxa_texto(r["pct_exec"])
                r["faixa_meta"] = faixa(r["pct_meta"])
                r["faixa_exec"] = faixa(r["pct_exec"])
                r["progresso_meta"] = {**progresso(r["pct_meta"]), "pct_exibicao": (r["pct_meta"].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if r["pct_meta"] is not None else None)}
                r["progresso_exec"] = {**progresso(r["pct_exec"]), "pct_exibicao": (r["pct_exec"].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if r["pct_exec"] is not None else None)}
                r["valor_compacto"], r["valor_unidade"] = separar_unidade(dinheiro(r["realizado"], True))
                r["barras"] = [{"titulo": titulo, "valor": r[c], "barra": (r[c] or ZERO) / escala * 100 if escala else ZERO, "faixa": status, "percentual": rotulo} for c, titulo, status, rotulo in (
                    ("recurso_ou_meta", "Meta", "neutra", ""), ("captado", "Captado", r["faixa_meta"], r["meta_rotulo"]), ("realizado", "Realizado", r["faixa_exec"], r["exec_rotulo"]))]
            fontes_por_codigo = {fonte["codigo"]: fonte for fonte in fontes}
            cards.clear()
            pp["blocos_cards_financeiros"] = []
            for codigo_fonte, titulo_bloco, campo, titulo_meta, titulo_recurso, titulo_diferenca in (
                ("AT", "Associação Tecnológica (AT) · Captação", "captado", "Meta de captação do recurso", "Recurso captado total", "Diferença captação"),
                ("OUTRASFONTES", "Outras Fontes · Execução", "realizado", "Meta de execução dos recursos", "Recurso executado total", "Diferença execução"),
            ):
                if codigo_fonte not in fontes_por_codigo:
                    continue
                fonte = fontes_por_codigo[codigo_fonte]
                meta_fonte = fonte.get("recurso_ou_meta")
                recurso_fonte = fonte.get(campo)
                diferenca = meta_fonte - recurso_fonte if meta_fonte is not None and recurso_fonte is not None else None
                pct_recurso = taxa(recurso_fonte, meta_fonte)
                cards_fonte = [
                    {"titulo": titulo_meta, "valor": dinheiro(meta_fonte, True), "referencia": "meta total da fonte"},
                    {"titulo": titulo_recurso, "valor": dinheiro(recurso_fonte, True), "referencia": "meta de " + dinheiro(meta_fonte, True), "mostrar_barra": True, "rotulo_barra": taxa_texto(pct_recurso) + " da meta" if pct_recurso is not None else "—", **progresso(pct_recurso)},
                    {"titulo": titulo_diferenca, "valor": dinheiro(diferenca, True), "referencia": "meta menos recurso " + ("captado" if campo == "captado" else "executado"), "descricao": "meta superada" if diferenca is not None and diferenca < 0 else ""},
                ]
                cards.extend(cards_fonte)
                pp["blocos_cards_financeiros"].append({"codigo": codigo_fonte, "titulo": titulo_bloco, "cards": cards_fonte})
            pp["pct_meta_rotulo"] = taxa_texto(pct_meta)
            pp["faixa_meta"] = faixa(pct_meta)
            pp["progresso_meta"] = {**progresso(pct_meta), "pct_exibicao": pct_meta.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if pct_meta is not None else None}
            pp["progresso_exec"] = {**progresso(taxa(pp.get("executado"), pp.get("previsto"))), "pct_exibicao": taxa(pp.get("executado"), pp.get("previsto")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if taxa(pp.get("executado"), pp.get("previsto")) is not None else None}
        else:
            cards.append({"titulo": pp["rotulo_previsto"], "valor": dinheiro(pp.get("previsto"), True), "referencia": "recurso total do pilar no PPI"})
        if not pp.get("visao_captacao"):
            saldo_pct = taxa(pp.get("saldo"), pp.get("previsto"))
            cards.append({"titulo": "Diferença rel. PPI", "valor": dinheiro(pp.get("saldo"), True), "referencia": "de " + dinheiro(pp.get("previsto"), True) + " · saldo a executar", "mostrar_barra": True, "cinza": True, "rotulo_barra": numero_curto(pct_inteiro(pp.get("saldo"), pp.get("previsto"))) + "%" if saldo_pct is not None else "—", **progresso(saldo_pct, "neutra")})
    else:
        _anual(pp)
        grupos = pp.get("tabela_gerencial_fisica", {}).get("grupos", [])
        pares = [(l["previsto"], l["executado"]) for g in grupos for l in g["linhas"]]
        pp["status_counts"] = resumo_fisico(pares) if not contexto["sem_dados_intervalo"] else None
        for grupo in grupos:
            for linha in grupo["linhas"]:
                if " (" in linha["rotulo"]:
                    linha["nome"], linha["unidade"] = linha["rotulo"].rsplit(" (", 1)
                    linha["unidade"] = linha["unidade"].rstrip(")")
        if pp.get("visao_captacao"):
            blocos = pp.get("blocos_fisicos", [])
            for b in blocos:
                percentual = b.get("unidade_indicador") == "Percentual"
                b.update(valores_percentuais=percentual, valor_fmt=valor_fisico(b["executado"], percentual), meta_fmt=valor_fisico(b["previsto"], percentual), saldo_fmt=valor_fisico(b["saldo"], percentual))
                b["titulo_indicador"] = "Empresas associadas · número absoluto" if not percentual else "Recursos de empresas da Associação · percentual" if b["codigo"] == "AT" else "Recursos de outras fontes · percentual"
                b["progresso"] = progresso(b["pct"], b["faixa"])
                b["progresso"]["barra"] = min(max(taxa(b.get("executado_limitado", b["executado"]), b["previsto"]) or ZERO, ZERO), Decimal(100))
                _anual(b, percentual)
            for i, b in enumerate(blocos):
                cards.append({"titulo": "Empresas associadas · AT" if not b["valores_percentuais"] else "Recursos de empresas · AT" if b["codigo"] == "AT" else "Recursos de outras fontes", "valor": b["valor_fmt"], "referencia": "de " + b["meta_fmt"] + " previstos" if b["valores_percentuais"] else "", "referencia_inline": "de " + b["meta_fmt"] + " empresas" if not b["valores_percentuais"] else None, "descricao": "indicador principal da Associação Tecnológica" if not b["valores_percentuais"] else "", "hero": i == 0, "mostrar_barra": i != 0, "cor_fonte": b["codigo"] if i != 0 else None, **b["progresso"]})
        else:
            limitado = pp.get("executado_limitado", pp.get("executado"))
            exibir = limitado if codigo == "STARTUPS" else pp.get("executado")
            descricao = "executado limitado à meta de cada indicador" if codigo == "STARTUPS" else "meta do ciclo atingida" if pp.get("pct") == 100 else "taxa de execução no período"
            cards.append({"titulo": f"Executado · {nome_card}", "valor": numero_curto(exibir), "unidade": "metas" if codigo != "STARTUPS" else None, "referencia": "de " + numero_curto(pp.get("previsto")) + " metas projetadas" if codigo != "STARTUPS" else "", "referencia_inline": "de " + numero_curto(pp.get("previsto")) + " metas" if codigo == "STARTUPS" else None, "descricao": descricao, "extra": numero_curto(pp.get("executado")) + " metas executadas no total" if codigo == "STARTUPS" else "", "hero": True, **pp["progresso"]})
            ciclo = periodo["ciclo"]
            descricao_meta = "empresas de base tecnológica e projetos em inovação aberta" if codigo == "STARTUPS" else "projetos de PD&I e pedidos de PI, " + ("ciclo 2024 a 2027" if ciclo else "no intervalo selecionado") if codigo == "PDI" else "meta total do ciclo 2024 a 2027" if ciclo else "meta do intervalo selecionado"
            cards.append({"titulo": "Meta", "valor": numero_curto(pp.get("previsto")), "unidade": "metas", "referencia": descricao_meta})
            zerado = pp.get("saldo") == 0 and pp.get("previsto") is not None and pp["previsto"] > 0 and pp.get("executado") is not None
            pct_saldo = 100 if zerado else pct_inteiro(pp.get("saldo"), pp.get("previsto"))
            cards.append({"titulo": "Saldo a executar", "valor": numero_curto(pp.get("saldo")), "unidade": "metas", "referencia": "meta superada · nada a realizar" if zerado else "todo o saldo está em projetos em inovação aberta" if codigo == "STARTUPS" else "restante da meta", "mostrar_barra": True, "cinza": not zerado, "rotulo_barra": numero_curto(pct_saldo) + "%" if pct_saldo is not None else "—", **progresso(pct_saldo, "ok" if zerado else "neutra")})
    for i, card in enumerate(cards, 1):
        card["chave"] = str(i)
        valor, unidade = separar_unidade(card.get("valor", ""))
        if unidade:
            card.update(valor=valor, unidade=unidade)
    if financeiro and not pp.get("visao_captacao"):
        cards[0]["titulo"] = "Recurso PPI realizado"
        cards[1]["titulo"] = {"PDI": "Recurso PPI AFCCT total", "FORMACAO": "Recurso PPI FCRH total", "STARTUPS": "Recurso PPI ACS total"}.get(codigo, pp["rotulo_previsto"])
        cards = [cards[1], cards[0], cards[2]]
        pp["grafico_financeiro"] = grafico_carteira(pp["grupos_projetos"])
    pp["cards_overview"] = cards
    if financeiro and not pp.get("visao_captacao"):
        pp["progresso"]["pct_exibicao"] = taxa(pp.get("executado"), pp.get("previsto")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if taxa(pp.get("executado"), pp.get("previsto")) is not None else None
    params = QueryDict(mutable=True)
    params.update({"ano": contexto["ano_param"], "mes_inicial": periodo["mes_inicial"], "mes_final": periodo["mes_final"], "pilar": str(contexto["pilar_pk"])})
    if contexto.get("acompanhamento"):
        params["acompanhamento"] = str(contexto["acompanhamento"].pk)
    contexto["filtros_dashboard"] = params.urlencode()
    return contexto
