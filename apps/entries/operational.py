"""Catálogo, base inicial e homologação dos resultados que alimentam os painéis."""
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.accountability.models import KpiAcompanhamento, ProjetoFinanceiro, ResumoFinanceiro
from apps.audit.services import registrar_auditoria
from apps.core.permissions import eh_gestor, pode_lancar, usuario_pode_pilar
from .models import BaseOperacional, IndicadorOperacional, LancamentoOperacional, ProjetoFinanceiroFonte

ZERO = Decimal(0)


def decimal(valor):
    return None if valor is None else Decimal(str(valor))


def registrar(usuario, acao, obj, anterior="", novo="", justificativa=""):
    registrar_auditoria(usuario, acao, type(obj).__name__, registro_id=str(obj.pk),
                       valor_anterior=str(anterior), valor_novo=str(novo), justificativa=justificativa)
    from .effective import invalidar
    invalidar()


def valor_atual(indicador, competencia=None):
    q = indicador.revisoes.filter(status="APROVADO")
    if competencia:
        q = q.filter(periodo__competencia__lte=competencia)
    aprovado = q.order_by("-periodo__competencia", "-versao").first()
    if aprovado:
        return aprovado.valor
    base = BaseOperacional.objects.filter(acompanhamento_id=indicador.acompanhamento_id).first()
    if not base or competencia and competencia < base.competencia_corte:
        return None
    return decimal(base.snapshot["alvos"].get(indicador.chave, {}).get("valor"))


@transaction.atomic
def confirmar_base(acomp, competencia, usuario, justificativa="", reconciliar=False):
    if not eh_gestor(usuario):
        raise PermissionDenied
    if competencia.day != 1 or not 2024 <= competencia.year <= 2027:
        raise ValidationError("Informe uma competência do ciclo 2024–2027.")
    type(acomp).objects.select_for_update().get(pk=acomp.pk)
    base = BaseOperacional.objects.select_for_update().filter(acompanhamento=acomp).first()
    if base and not reconciliar:
        return base
    if base and not justificativa.strip():
        raise ValidationError("A conciliação exige justificativa.")
    anterior = {"versao": base.versao, "competencia_corte": base.competencia_corte, "snapshot": base.snapshot} if base else None
    # O resolvedor é desabilitado durante a captura para nunca importar a si próprio.
    from .effective import suspender
    from apps.accountability import panel
    from apps.pillars.models import Pilar
    alvos, totais, anuais = {}, {}, {}

    def alvo(chave, pilar, nome, base_exibicao, tipo, unidade, categoria, referencia, valor, campo="realizado", anos=None):
        item, _ = IndicadorOperacional.objects.update_or_create(acompanhamento=acomp, chave=chave,
            defaults=dict(pilar=pilar, nome=nome, base=base_exibicao, tipo=tipo, unidade=unidade,
                          alvo=categoria, referencia=str(referencia), campo=campo, ativo=True))
        alvos[chave] = {"valor": valor, "anos": anos or {}}
        return item

    with suspender():
        for k in KpiAcompanhamento.objects.filter(acompanhamento=acomp).select_related("pilar").prefetch_related("overrides"):
            percentual = k.unidade == "Percentual" and k.codigo != "PE-09"
            valor = panel._campos_kpi(k, None)[1]
            anos = {str(a): panel._campos_kpi(k, a)[1] for a in range(2024, 2028)}
            alvo(f"kpi:{k.codigo}", k.pilar, k.nome,
                 "financeiro" if k.pilar.codigo in ("AT", "OUTRASFONTES") and percentual else "fisico",
                 "PER" if percentual else "QTD", "%" if percentual else "publicações" if k.codigo == "PE-09" else "un",
                 "KPI", k.codigo, valor, anos=anos)
        ajustes = panel._overrides_financeiros(acomp)
        for r in ResumoFinanceiro.objects.filter(acompanhamento=acomp, origem__in=["TAB. 1", "TAB. 9", "TAB. 1.1"]).select_related("pilar"):
            codigo = r.pilar.codigo
            valor = ajustes.get((codigo, r.ano or 0, "executado"), r.realizado)
            if r.ano:
                anuais[f"{codigo}:{r.ano}"] = valor
            elif r.origem != "TAB. 1.1":
                totais[codigo] = {"realizado": valor, "captado": ajustes.get((codigo, 0, "previsto"), r.captado),
                    "captado_anos_1_2": ajustes.get((codigo, 0, "captado_anos_1_2"), r.captado_anos_1_2),
                    "captado_ano3_ytd": ajustes.get((codigo, 0, "captado_ano3_ytd"), r.captado_ano3_ytd)}
                if codigo == "INFRA":
                    alvo("pilar:INFRA:realizado", r.pilar, "Infraestrutura · realizado", "financeiro", "MON", "R$", "PILAR", codigo, valor)
        for p in ProjetoFinanceiro.objects.filter(acompanhamento=acomp, projeto__isnull=False).select_related("pilar", "projeto"):
            alvo(f"projeto:{p.projeto_id}:realizado", p.pilar, p.nome + " · realizado", "financeiro", "MON", "R$", "PROJETO", p.projeto_id, p.realizado)
        for p in ProjetoFinanceiroFonte.objects.filter(centro=acomp.centro, ativo=True).select_related("pilar"):
            for campo in ("captado", "realizado"):
                chave = f"fonte:{p.pk}:{campo}"
                anterior = base.snapshot["alvos"].get(chave, {}).get("valor") if base else None
                # Carteiras cadastradas têm abertura explícita; nunca presumir valores históricos.
                if anterior is not None:
                    alvo(chave, p.pilar, p.nome + " · " + campo, "financeiro", "MON", "R$", "FONTE", p.pk, decimal(anterior), campo)
    IndicadorOperacional.objects.filter(acompanhamento=acomp).exclude(chave__in=alvos).update(ativo=False)
    import json
    from django.core.serializers.json import DjangoJSONEncoder
    snapshot = json.loads(json.dumps({"alvos": alvos, "totais": totais, "anuais": anuais}, cls=DjangoJSONEncoder))
    if base:
        base.snapshot = snapshot
        base.versao += 1
        base.competencia_corte = competencia
        base.confirmado_por = usuario
        base.save()
    else:
        base = BaseOperacional.objects.create(acompanhamento=acomp, competencia_corte=competencia,
                                              snapshot=snapshot, confirmado_por=usuario)
    registrar(usuario, "CONCILIAR_BASE_OPERACIONAL", base,
        anterior=json.dumps(anterior, cls=DjangoJSONEncoder, ensure_ascii=False) if anterior else "",
        novo=json.dumps({"versao": base.versao, "competencia_corte": base.competencia_corte, "snapshot": base.snapshot}, cls=DjangoJSONEncoder, ensure_ascii=False),
        justificativa=justificativa)
    return base


def parse_valor(indicador, bruto):
    try:
        texto = str(bruto).strip().replace(" ", "")
        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")
        valor = Decimal(texto)
    except (InvalidOperation, ValueError):
        raise ValidationError("Informe um valor numérico válido.")
    if not valor.is_finite() or valor < 0 or valor >= Decimal("1000000000000"):
        raise ValidationError("Valor fora do intervalo permitido.")
    if indicador.tipo == "PER":
        valor /= 100
    casas = 2 if indicador.tipo == "MON" else 6
    if indicador.tipo == "QTD" and valor != valor.to_integral_value():
        raise ValidationError("Quantidades exigem números inteiros.")
    if valor != valor.quantize(Decimal(1).scaleb(-casas)):
        raise ValidationError("Precisão incompatível com a unidade do indicador.")
    return valor


def validar_acesso(indicador, periodo, usuario):
    if not pode_lancar(usuario) or not usuario_pode_pilar(usuario, indicador.pilar):
        raise PermissionDenied
    if not indicador.ativo:
        raise ValidationError("Indicador fora do catálogo atual.")
    if not periodo.permite_edicao:
        raise ValidationError("O período está fechado. Solicite uma reabertura justificada.")
    base = BaseOperacional.objects.get(acompanhamento_id=indicador.acompanhamento_id)
    if periodo.competencia < base.competencia_corte:
        raise ValidationError("Competência anterior à base inicial. Concilie a referência histórica antes de lançar.")
    if indicador.chave not in base.snapshot["alvos"]:
        raise ValidationError("Alvo sem base inicial confirmada.")
    if indicador.alvo in ("PROJETO", "FONTE") and base.snapshot["alvos"][indicador.chave]["valor"] is None:
        raise ValidationError("A execução histórica deste projeto está indisponível. Confirme o acumulado de abertura na planilha oficial e concilie a base antes de lançar; não se presume zero.")
    return base


@transaction.atomic
def salvar(indicador, periodo, usuario, bruto, comentario, enviar=False, direto=False):
    base = validar_acesso(indicador, periodo, usuario)
    base = BaseOperacional.objects.select_for_update().get(pk=base.pk)
    # A mesma trava é usada por envio, aprovação, ajuste direto e conciliação.
    from apps.periods.models import Periodo
    periodo = Periodo.objects.select_for_update().get(pk=periodo.pk)
    validar_acesso(indicador, periodo, usuario)
    if direto and not eh_gestor(usuario):
        raise PermissionDenied
    valor = parse_valor(indicador, bruto)
    atual = valor_atual(indicador, periodo.competencia)
    if atual is not None and valor < atual and not comentario.strip():
        raise ValidationError("Redução do acumulado exige justificativa.")
    if direto and not comentario.strip():
        raise ValidationError("O ajuste direto exige justificativa.")
    item = LancamentoOperacional.objects.filter(indicador=indicador, periodo=periodo,
        status__in=["RASCUNHO", "ENVIADO", "DEVOLVIDO"]).first()
    if item and item.status == "ENVIADO":
        raise ValidationError("A proposta já foi enviada e está bloqueada para edição.")
    if item is None:
        versao = (indicador.revisoes.filter(periodo=periodo).aggregate(v=Max("versao"))["v"] or 0) + 1
        item = LancamentoOperacional(indicador=indicador, periodo=periodo, versao=versao, criado_por=usuario)
    item.valor, item.valor_base, item.base_versao = valor, atual, base.versao
    item.comentario = comentario.strip()
    item.status = "ENVIADO" if enviar or direto else "RASCUNHO"
    if enviar or direto:
        item.enviado_em = timezone.now()
    item.save()
    registrar(usuario, "ENVIAR_OPERACIONAL" if enviar else "SALVAR_OPERACIONAL", item, novo=valor)
    if direto:
        return aprovar(item, usuario, direto=True)
    return item


@transaction.atomic
def aprovar(item, usuario, direto=False):
    if not eh_gestor(usuario):
        raise PermissionDenied
    BaseOperacional.objects.select_for_update().get(acompanhamento_id=item.indicador.acompanhamento_id)
    item = LancamentoOperacional.objects.select_for_update().get(pk=item.pk)
    from apps.periods.models import Periodo
    item.periodo = Periodo.objects.select_for_update().get(pk=item.periodo_id)
    if item.status == "APROVADO":
        return item
    if item.status != "ENVIADO":
        raise ValidationError("Apenas propostas enviadas podem ser aprovadas.")
    validar_acesso(item.indicador, item.periodo, usuario)
    base = BaseOperacional.objects.get(acompanhamento_id=item.indicador.acompanhamento_id)
    if base.versao != item.base_versao or valor_atual(item.indicador, item.periodo.competencia) != item.valor_base:
        raise ValidationError("O valor vigente mudou desde o envio. Devolva para revisão antes de aprovar.")
    item.status, item.revisado_por, item.aprovado_em = "APROVADO", usuario, timezone.now()
    item.origem = "Ajuste direto do gestor" if direto else "Lançamento"
    item.save()
    registrar(usuario, "APROVAR_OPERACIONAL", item, item.valor_base, item.valor, item.comentario if direto else "")
    return item


@transaction.atomic
def devolver(item, usuario, justificativa):
    if not eh_gestor(usuario):
        raise PermissionDenied
    BaseOperacional.objects.select_for_update().get(acompanhamento_id=item.indicador.acompanhamento_id)
    item = LancamentoOperacional.objects.select_for_update().get(pk=item.pk)
    if item.status != "ENVIADO" or not justificativa.strip():
        raise ValidationError("A devolução exige uma proposta enviada e uma justificativa.")
    item.status, item.comentario_revisao, item.revisado_por = "DEVOLVIDO", justificativa.strip(), usuario
    item.save()
    registrar(usuario, "DEVOLVER_OPERACIONAL", item, novo=justificativa.strip())


@transaction.atomic
def criar_projeto_fonte(base, pilar, nome, captado, realizado, usuario):
    if not eh_gestor(usuario) or pilar.codigo not in ("AT", "OUTRASFONTES"):
        raise PermissionDenied
    base = BaseOperacional.objects.select_for_update().get(pk=base.pk)
    if not nome.strip():
        raise ValidationError("Informe o nome do projeto financeiro.")
    p = ProjetoFinanceiroFonte.objects.filter(centro=base.acompanhamento.centro, pilar=pilar, nome=nome.strip()).first()
    if p and IndicadorOperacional.objects.filter(acompanhamento=base.acompanhamento, referencia=str(p.pk), alvo="FONTE").exists():
        raise ValidationError("Este projeto já está vinculado à base. Atualize seus resultados no catálogo.")
    if p is None:
        p = ProjetoFinanceiroFonte(centro=base.acompanhamento.centro, pilar=pilar, nome=nome.strip(), criado_por=usuario)
        p.full_clean()
        p.save()
    for campo, bruto in (("captado", captado), ("realizado", realizado)):
        item = IndicadorOperacional.objects.create(acompanhamento=base.acompanhamento, pilar=pilar,
            chave=f"fonte:{p.pk}:{campo}", nome=p.nome + " · " + campo, base="financeiro", tipo="MON", unidade="R$",
            alvo="FONTE", referencia=str(p.pk), campo=campo)
        valor = parse_valor(item, bruto)
        total = decimal(base.snapshot["totais"].get(pilar.codigo, {}).get(campo))
        alocado = sum((decimal(v["valor"]) or ZERO for k, v in base.snapshot["alvos"].items()
                       if k.startswith("fonte:") and k.endswith(":" + campo)
                       and IndicadorOperacional.objects.filter(acompanhamento=base.acompanhamento, chave=k, pilar=pilar).exists()), ZERO)
        if total is None or alocado + valor > total:
            raise ValidationError("A abertura excede o saldo histórico da fonte. Concilie a base antes de distribuir.")
        base.snapshot["alvos"][item.chave] = {"valor": str(valor), "anos": {}}
    base.versao += 1
    base.save()
    import json
    registrar(usuario, "CRIAR_PROJETO_FIN_FONTE", p, novo=json.dumps({
        "nome": nome, "base": base.pk, "versao": base.versao,
        "abertura": {campo: base.snapshot["alvos"][f"fonte:{p.pk}:{campo}"]["valor"] for campo in ("captado", "realizado")},
    }, ensure_ascii=False))
    return p
