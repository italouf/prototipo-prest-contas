"""Slides compostos pelos mesmos DTO do painel importado.

O mês é editorial: valores anuais não são distribuídos pelos meses.
O filtro de pilares precede os totais e a seleção dos gráficos.
"""
import textwrap
from decimal import Decimal

from django.db.models import Q

from apps.accountability.panel import painel_acompanhamento, resumo_financeiro_ciclo
from apps.core.charts import geometria_barras
from apps.core.permissions import pilares_visiveis


PILARES = (
    ("PDI", "Pesquisa, desenvolvimento e inovação", "PDI"),
    ("FORMACAO", "Formação e capacitação", "FCRH"),
    ("STARTUPS", "Atração e criação de startups", "ACS"),
    ("AT", "Associação Tecnológica", "AT"),
)
PILARES_PPI = {"PDI", "FORMACAO", "STARTUPS", "INFRA"}


def _partes(texto, limite_linhas=11):
    """Limite por linhas, sem descartar texto; palavras extensas também cabem."""
    linhas = []
    for paragrafo in texto.splitlines():
        linhas.extend(textwrap.wrap(paragrafo, width=44, break_long_words=True, break_on_hyphens=False) or [""])
    return ["\n".join(linhas[i:i + limite_linhas]) for i in range(0, len(linhas), limite_linhas)] or [""]


def _conteudos_em_paginas(conteudos, limite_linhas=11):
    return [
        {"obj": item, "texto": parte, "continuacao": numero > 0}
        for item in conteudos
        for numero, parte in enumerate(_partes(item.texto, limite_linhas))
    ]


def _grafico(linhas):
    if not linhas:
        return None
    mi = Decimal("1000000")
    return geometria_barras(
        [(linha["rotulo"], "") for linha in linhas],
        [None if linha["recurso"] is None else float(linha["recurso"] / mi) for linha in linhas],
        [None if linha["realizado"] is None else float(linha["realizado"] / mi) for linha in linhas],
        None, largura=1000, altura=230,
        pad={"esq": 25, "dir": 25, "topo": 35, "base": 44},
        larg_barra_max=64, espaco=10,
    )


def compor_apresentacao(apresentacao, usuario):
    """Dados vivos, sem fallback para fontes operacionais ou plano demonstrativo."""
    pilares = list(pilares_visiveis(usuario))
    codigos = [p.codigo for p in pilares]
    ids = [p.pk for p in pilares]
    financeiro = painel_acompanhamento(None, "fin", apresentacao.acompanhamento, codigos)
    if "graficos_ciclo" not in financeiro:
        financeiro.update(resumo_financeiro_ciclo(apresentacao.acompanhamento, codigos))
    fisico = painel_acompanhamento(None, "fis", apresentacao.acompanhamento, codigos)
    grupos = {grupo["codigo"]: grupo["linhas"] for grupo in fisico["tabela"]["grupos"]}
    conteudos = list(
        apresentacao.conteudos.filter(Q(pilar__isnull=True) | Q(pilar_id__in=ids))
        .select_related("pilar").defer("imagem")
    )
    destaques = [c for c in conteudos if c.tipo == "DESTAQUE"]
    gerais = [c for c in destaques if c.pilar_id is None]
    tabela_ppi = financeiro.get("tabela_tab1", {})
    linhas_ppi = [linha for linha in tabela_ppi.get("linhas", []) if not linha["total"]]
    total_ppi = tabela_ppi.get("total")
    # graficos_ciclo contém AT/Outras mesmo quando não selecionados no painel:
    # nunca transportar esses blocos para o contexto sem verificar o escopo.
    fontes = []
    for codigo, chave, titulo in (("AT", "at", "Associação Tecnológica"), ("OUTRASFONTES", "outras", "Outras fontes")):
        if codigo in codigos:
            bloco = financeiro.get("graficos_ciclo", {}).get(chave, {})
            fontes.append({"codigo": codigo, "titulo": titulo, **bloco})

    resumo = []
    if PILARES_PPI.intersection(codigos):
        resumo.append({"rotulo": "Execução PPI", "valor": total_ppi.get("realizado") if total_ppi else None})
    resumo.extend({"rotulo": f"Captação · {fonte['titulo']}", "valor": fonte.get("captado")} for fonte in fontes)
    slides = [
        {"tipo": "capa", "titulo": apresentacao.titulo or "Apresentação de acompanhamento mensal", "chave": "capa"},
        {"tipo": "resumo", "titulo": "O mês em perspectiva", "chave": "resumo", "resumo": resumo,
         "destaques": destaques[:3], "total_destaques": len(destaques)},
    ]
    for item in _conteudos_em_paginas(gerais):
        slides.append({"tipo": "editorial", "titulo": "Destaques", "chave": "destaques", "item": item})
    for codigo, titulo, sigla in PILARES:
        if codigo not in codigos:
            continue
        indicadores = grupos.get(codigo, [])
        for inicio in range(0, max(len(indicadores), 1), 3):
            slides.append({"tipo": "pilar", "titulo": titulo, "sigla": sigla,
                           "chave": codigo.lower(), "indicadores": indicadores[inicio:inicio + 3]})
        for item in _conteudos_em_paginas([c for c in destaques if c.pilar and c.pilar.codigo == codigo]):
            slides.append({"tipo": "editorial", "titulo": f"{sigla} · Destaques", "chave": codigo.lower(), "item": item})
    if PILARES_PPI.intersection(codigos):
        slides.append({"tipo": "ppi", "titulo": "Execução dos recursos PPI", "chave": "ppi",
                       "linhas": linhas_ppi, "total": total_ppi, "grafico": _grafico(linhas_ppi),
                       "infra": grupos.get("INFRA", [])})
        for item in _conteudos_em_paginas([c for c in destaques if c.pilar and c.pilar.codigo == "INFRA"]):
            slides.append({"tipo": "editorial", "titulo": "Infraestrutura · Destaques", "chave": "infra", "item": item})
    if fontes:
        slides.append({"tipo": "fontes", "titulo": "AT e outras fontes", "chave": "fontes",
                       "fontes": fontes, "indicadores": grupos.get("OUTRASFONTES", [])})
        for item in _conteudos_em_paginas([c for c in destaques if c.pilar and c.pilar.codigo == "OUTRASFONTES"]):
            slides.append({"tipo": "editorial", "titulo": "Outras fontes · Destaques", "chave": "outras", "item": item})
    pendencias = _conteudos_em_paginas([c for c in conteudos if c.tipo == "PENDENCIA"], 8)
    acoes = _conteudos_em_paginas([c for c in conteudos if c.tipo == "PROXIMA_ACAO"], 8)
    for i in range(max(len(pendencias), len(acoes), 1)):
        slides.append({"tipo": "encerramento", "titulo": "O que vem a seguir", "chave": "proximos-passos",
                       "pendencia": pendencias[i] if i < len(pendencias) else None,
                       "acao": acoes[i] if i < len(acoes) else None})
    for numero, slide in enumerate(slides, 1):
        slide["numero"] = numero
    return {"slides": slides, "quantidade_slides": len(slides), "pilares_apresentacao": pilares}
