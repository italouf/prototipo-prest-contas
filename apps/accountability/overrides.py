"""Override manual auditado por acompanhamento (SDD §9).

Mesmo formulário e mesmas chaves do editor legado —
`v__{ano}__{base}__{codigo}__{campo}`, com `codigo` = pilar (financeiro) ou
código do KPI (físico) — mas o destino é `OverrideAcompanhamento`, nunca
`PlanoAnual`. Regras:

- valor vazio (`valor=None`) **remove** o override e restaura o importado;
- `acao=restaurar` (`restaurar_tudo`) remove todos os overrides do acompanhamento;
- precedência: override > importado. `pct`/`saldo`/`faixa` são sempre
  recalculados dos valores efetivos (em `panel._linha`), nunca armazenados;
- permissões: `pode_editar_painel` + `pilares_editaveis_painel`; no físico o
  escopo do PontoFocal é o **pilar do KPI**;
- auditoria: `EDITAR_OVERRIDE_PRESTACAO` (com `valor_anterior`/`valor_novo`)
  e `RESTAURAR_OVERRIDE_PRESTACAO`.

A leitura dos valores efetivos é **a mesma do painel** —
`panel._resumos_financeiros` e `panel._campos_kpi` já aplicam os overrides —
então a grade de edição espelha o painel por construção.
"""
from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.audit.services import registrar_auditoria
from apps.core.permissions import pilares_editaveis_painel, pode_editar_painel
from apps.pillars.models import Pilar
from apps.planning.services import ANOS, BASES, BASES_URL, PILARES_PPI, ROTULOS_PAINEL

from . import panel
from .models import KpiAcompanhamento, OverrideAcompanhamento

# Mesmo teto de `planning.views._parse_grade` (regras de valor idênticas às do
# legado). Constante local para não importar `planning.views` (evita ciclo).
LIMITE_VALOR = Decimal(10) ** 10

CAMPOS = ("previsto", "executado")
BASES_CURTA = {"financeiro": "fin", "fin": "fin", "fisico": "fis", "fis": "fis"}

ACAO_EDITAR = "EDITAR_OVERRIDE_PRESTACAO"
ACAO_RESTAURAR = "RESTAURAR_OVERRIDE_PRESTACAO"


def chave(base, codigo, ano, campo):
    """Chave única do override: `fin|PDI|2026|executado` / `fis|PE-01|2025|previsto`."""
    curta = BASES_CURTA.get(base)
    if curta is None:
        raise ValidationError(f"base inválida: {base}")
    return f"{curta}|{codigo}|{ano}|{campo}"


def _validar_valor(base, valor, codigo):
    try:
        valor = Decimal(valor)
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(f"valor inválido: {codigo}")
    if valor < 0 or valor >= LIMITE_VALOR:
        raise ValidationError(f"valor fora do intervalo: {codigo}")
    if base == "fisico" and valor != valor.to_integral_value():
        raise ValidationError(f"base física exige inteiro: {codigo}")
    return valor


def _resolver_item(acomp, base, item, editaveis):
    """Valida um item e devolve (chave, ano, campo, valor, pilar, kpi) resolvido.

    Mesmas restrições de `_parse_grade` (ano em `ANOS`, campo previsto|executado,
    limites de valor) mais a resolução do `codigo` — pilar ativo (financeiro) ou
    KPI do acompanhamento (físico). Escopo: `PermissionDenied` fora dos pilares
    editáveis (no físico, o pilar do KPI).
    """
    ano, codigo, campo, valor = item
    if not isinstance(ano, int) or ano not in ANOS:
        raise ValidationError(f"ano inválido: {ano}")
    if campo not in CAMPOS:
        raise ValidationError(f"campo inválido: {campo}")
    pilar = kpi = None
    if base == "financeiro":
        pilar = Pilar.objects.filter(ativo=True, codigo=codigo).first()
        if pilar is None:
            raise ValidationError(f"pilar inválido: {codigo}")
        pilar_codigo = pilar.codigo
    else:
        kpi = (KpiAcompanhamento.objects.filter(acompanhamento=acomp, codigo=codigo)
               .select_related("pilar").first())
        if kpi is None:
            raise ValidationError(f"kpi inválido: {codigo}")
        pilar_codigo = kpi.pilar.codigo
    if pilar_codigo not in editaveis:
        raise PermissionDenied
    if valor is not None:
        valor = _validar_valor(base, valor, codigo)
    return chave(base, codigo, ano, campo), ano, campo, valor, pilar, kpi


def aplicar_overrides(acomp, base, itens, usuario):
    """Aplica `[(ano, codigo, campo, valor|None)]` como overrides de `acomp`.

    `valor=None` remove o override (restaura o importado). Tudo é validado
    antes de qualquer gravação e o conjunto inteiro vai numa transação única;
    cada mudança audita `EDITAR_OVERRIDE_PRESTACAO` com `valor_anterior`/
    `valor_novo` do próprio override (`""` = sem override/removido).

    Returns:
        int: quantidade de overrides efetivamente gravados ou removidos
        (reaplicar o mesmo valor não escreve nem audita, como no legado).

    Raises:
        ValidationError: item fora das regras (ano/campo/valor/código/base).
        PermissionDenied: usuário sem `pode_editar_painel` ou sem o pilar.
    """
    base = BASES_URL.get(base, base)
    if base not in BASES:
        raise ValidationError(f"base inválida: {base}")
    if acomp is None:
        raise ValidationError("acompanhamento obrigatório")
    if not pode_editar_painel(usuario):
        raise PermissionDenied
    editaveis = set(pilares_editaveis_painel(usuario).values_list("codigo", flat=True))
    # Fase 1: valida o conjunto inteiro; nada é gravado com item inválido.
    resolvidos = [_resolver_item(acomp, base, item, editaveis) for item in itens]
    aplicados = 0
    with transaction.atomic():
        for chave_str, ano, campo, valor, pilar, kpi in resolvidos:
            atual = OverrideAcompanhamento.objects.filter(
                acompanhamento=acomp, chave=chave_str).first()
            if valor is None:  # valor vazio no editor ⇒ restaura o importado
                if atual is None:
                    continue
                registrar_auditoria(
                    usuario, ACAO_EDITAR, "OverrideAcompanhamento",
                    registro_id=str(atual.pk), campo=campo,
                    valor_anterior=str(atual.valor), valor_novo="")
                atual.delete()
                aplicados += 1
                continue
            if atual is not None:
                if atual.valor == valor:
                    continue
                anterior = atual.valor
                atual.valor = valor
                atual.usuario = usuario
                atual.save(update_fields=["valor", "usuario", "atualizado_em"])
            else:
                atual = OverrideAcompanhamento.objects.create(
                    acompanhamento=acomp, base=base, pilar=pilar, kpi=kpi,
                    ano=ano, campo=campo, valor=valor, chave=chave_str, usuario=usuario)
                anterior = ""
            registrar_auditoria(
                usuario, ACAO_EDITAR, "OverrideAcompanhamento",
                registro_id=str(atual.pk), campo=campo,
                valor_anterior=str(anterior), valor_novo=str(valor))
            aplicados += 1
    return aplicados


def _pilar_do_override(override):
    """Pilar que dá escopo ao override: o próprio (financeiro) ou o do KPI (físico).

    Mesma resolução de `_resolver_item`/`aplicar_overrides`; linha sem alvo
    resolúvel fica fora de todo escopo e nunca é tocada.
    """
    if override.kpi is not None:
        return override.kpi.pilar.codigo
    return override.pilar.codigo if override.pilar is not None else None


def restaurar_tudo(acomp, usuario, *, codigos=None, base=None):
    """Remove os overrides do acompanhamento **no escopo do usuário** e audita.

    Spec §9 combina "remove todos os overrides do acompanhamento" com
    "`pilares_editaveis_painel` (pilar do KPI entra no escopo do PontoFocal)";
    em conflito, a regra de permissão prevalece (Ruling 28): nenhum usuário
    modifica dado fora do seu escopo, nem por operação em massa — gestores
    limpam tudo, PontoFocal só os overrides dos pilares vinculados.

    Returns:
        int: quantidade de overrides efetivamente removidos.
    """
    if acomp is None:
        raise ValidationError("acompanhamento obrigatório")
    if not pode_editar_painel(usuario):
        raise PermissionDenied
    editaveis = set(pilares_editaveis_painel(usuario).values_list("codigo", flat=True))
    if codigos is not None:
        editaveis &= set(codigos)
    with transaction.atomic():
        alvos = [
            override for override in
            OverrideAcompanhamento.objects.filter(acompanhamento=acomp)
            .select_related("pilar", "kpi__pilar")
            if _pilar_do_override(override) in editaveis and (base is None or override.base == base)
        ]
        if alvos:
            OverrideAcompanhamento.objects.filter(pk__in=[o.pk for o in alvos]).delete()
        registrar_auditoria(
            usuario, ACAO_RESTAURAR, "OverrideAcompanhamento",
            registro_id=str(acomp.pk), valor_anterior=str(len(alvos)), valor_novo="0")
    return len(alvos)


def _celulas(valores):
    """Células por ano no shape do legado (`valores`/`celulas`/`total`)."""
    presentes = [v for v in valores if v is not None]
    return {
        "valores": list(valores),
        "celulas": [{"ano": ano, "valor": valor} for ano, valor in zip(ANOS, valores)],
        "total": sum(presentes, Decimal(0)) if presentes else None,
    }


def grade_edicao_overrides(acomp, base, codigos=None):
    """Blocos da grade de edição com os valores **efetivos** (SDD §9).

    Mesmo shape de `planning.services.grade_edicao` — blocos
    `titulo/cabecalho` e linhas
    `codigo/rotulo/campo/valores/celulas[{ano, valor}]/total`. Os valores são os
    efetivos: override quando existe, senão o importado, senão `None`
    (renderiza `—`). `codigos` restringe aos pilares editáveis (None = todos),
    como no legado; no físico o filtro é o pilar do KPI.
    """
    base = BASES_URL.get(base, base)
    if base not in BASES:
        raise ValidationError(f"base inválida: {base}")
    if acomp is None:
        raise ValidationError("acompanhamento obrigatório")

    def permitido(codigo_pilar):
        return codigos is None or codigo_pilar in codigos

    if base == "financeiro":
        # Mesma extração do painel (com overrides aplicados): o ano usa
        # TAB. 1.1 (projetado/realizado) — ver `panel._resumos_financeiros`.
        _, anual = panel._resumos_financeiros(acomp)

        def serie(codigo, campo):
            idx = 0 if campo == "previsto" else 1
            return [None if anual.get((codigo, ano)) is None
                    else anual[(codigo, ano)][idx] for ano in ANOS]

        blocos = []
        for campo, titulo in (("previsto", "Recursos PPI, projetado"),
                              ("executado", "Recursos PPI, executado")):
            linhas = [
                {"codigo": c, "rotulo": ROTULOS_PAINEL[c], "campo": campo,
                 **_celulas(serie(c, campo))}
                for c in PILARES_PPI if permitido(c)
            ]
            if linhas:
                blocos.append({"titulo": titulo, "cabecalho": "Pilar", "linhas": linhas})
        for codigo, titulo in (("AT", "Captação de recursos (AT)"),
                               ("OUTRASFONTES", "Outras fontes")):
            if not permitido(codigo):
                continue
            blocos.append({"titulo": titulo, "cabecalho": "Indicador", "linhas": [
                {"codigo": codigo, "rotulo": "Captado", "campo": "previsto",
                 **_celulas(serie(codigo, "previsto"))},
                {"codigo": codigo, "rotulo": "Executado", "campo": "executado",
                 **_celulas(serie(codigo, "executado"))},
            ]})
        return blocos

    kpis = list(
        KpiAcompanhamento.objects.filter(acompanhamento=acomp)
        .select_related("pilar").prefetch_related("overrides")
        .order_by("sequencia", "codigo")
    )

    def serie_kpi(kpi, campo):
        idx = 0 if campo == "previsto" else 1
        return [panel._campos_kpi(kpi, ano)[idx] for ano in ANOS]

    blocos = []
    for campo, titulo in (("previsto", "Metas por KPI, previsto"),
                          ("executado", "Metas por KPI, executado")):
        linhas = [
            {"codigo": kpi.codigo, "rotulo": f"{kpi.nome} ({kpi.unidade})",
             "campo": campo, **_celulas(serie_kpi(kpi, campo))}
            for kpi in kpis if permitido(kpi.pilar.codigo)
        ]
        if linhas:
            blocos.append({"titulo": titulo, "cabecalho": "KPI", "linhas": linhas})
    return blocos
