from collections import defaultdict
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from apps.audit.services import registrar_auditoria
from apps.core.permissions import pode_lancar, pilares_visiveis
from .models import HistoricoSolicitacao, PlanoBeneficio, Solicitacao, UsoBeneficio

RESPONSAVEIS = {"PDI": ("PDI", "Resp. técnico PDI"), "Formação": ("FORMACAO", "Resp. técnico FCRH"), "Infraestrutura": ("INFRA", "Resp. técnico Infraestrutura"), "Plataformas e PI": ("PDI", "Resp. técnico PDI"), "Mentoria": ("PDI", "Resp. técnico PDI"), "Estudos": ("AT", "Resp. técnico Estudos"), "Startups": ("STARTUPS", "Resp. técnico ACS")}

def pode_ver_associados(user):
    return pilares_visiveis(user).filter(codigo="AT").exists()

def pode_gerir_associados(user):
    return pode_lancar(user) and pode_ver_associados(user)

def solicitacoes_visiveis(user):
    qs = Solicitacao.objects.select_related("associado__plano", "responsavel_pilar")
    return qs if pode_ver_associados(user) else qs.filter(responsavel_pilar__in=pilares_visiveis(user))

def resumo_beneficios(associado):
    usos = {u.beneficio_id: u.quantidade for u in associado.usos.all()}
    itens, grupos = [], defaultdict(list)
    for pb in associado.plano.beneficios.select_related("beneficio").order_by("beneficio__ordem"):
        b, usado = pb.beneficio, usos.get(pb.beneficio_id, 0)
        item = {"beneficio": b, "plano_beneficio": pb, "usado": usado, "saldo": max(0, pb.cota - usado), "percentual": min(100, usado / pb.cota * 100) if pb.cota else 0}
        itens.append(item)
        grupos[b.categoria].append(item)
    cotas = [i for i in itens if i["beneficio"].quantitativo and i["plano_beneficio"].incluido and i["plano_beneficio"].cota]
    acessos = [i for i in itens if i["beneficio"].codigo in ("est", "gt")]
    percentual = sum(i["percentual"] for i in cotas) / len(cotas) if cotas else sum(bool(i["usado"]) for i in acessos) / len(acessos) * 100 if acessos else 0
    contaveis = [i for i in itens if i["beneficio"].codigo not in ("prio", "lic", "dlic")]
    return {"grupos": dict(grupos), "itens": itens, "percentual": percentual, "utilizados": sum(bool(i["usado"]) for i in contaveis if i["plano_beneficio"].incluido), "incluidos": sum(i["plano_beneficio"].incluido for i in contaveis)}

@transaction.atomic
def registrar_andamento(pk, user, status, texto):
    s = solicitacoes_visiveis(user).select_for_update(of=("self",)).get(pk=pk)
    if not pode_lancar(user):
        raise ValidationError("Seu perfil não permite registrar andamentos.")
    destinos = {"Recebida": {"Recebida", "Encaminhada", "Em andamento", "Respondida"}, "Encaminhada": {"Encaminhada", "Em andamento", "Respondida"}, "Em andamento": {"Em andamento", "Respondida"}, "Respondida": {"Respondida", "Concluída"}, "Concluída": {"Concluída"}}
    if status not in destinos[s.status]:
        raise ValidationError("Transição de status inválida. Preserve a sequência do atendimento.")
    texto = texto.strip()
    if status == "Respondida" and not s.respondida_em and not texto:
        raise ValidationError("Escreva a resposta ao associado.")
    if status == s.status and not texto:
        raise ValidationError("Informe uma observação ou altere o status.")
    anterior, s.status = s.status, status
    if status == "Respondida" and not s.respondida_em:
        s.respondida_em = timezone.localdate()
    s.full_clean()
    s.save()
    descricao = f"Status alterado para {status}." if anterior != status else "Andamento registrado."
    if status == "Encaminhada":
        descricao += f" Encaminhada a {s.responsavel_tecnico}."
    if texto:
        descricao += f" {'Resposta' if status == 'Respondida' else 'Observação'}: {texto}"
    HistoricoSolicitacao.objects.create(solicitacao=s, usuario=user, descricao=descricao, status=status)
    registrar_auditoria(user, "ANDAMENTO_SOLICITACAO", "SolicitacaoAT", pk, "status", anterior, status, texto)
    return s

@transaction.atomic
def atualizar_usos(associado, user, dados):
    if not pode_gerir_associados(user):
        raise ValidationError("Seu perfil não permite alterar benefícios.")
    type(associado).objects.select_for_update().get(pk=associado.pk)
    for pb in PlanoBeneficio.objects.filter(plano=associado.plano).select_related("beneficio"):
        chave = f"uso_{pb.beneficio_id}"
        if chave not in dados:
            continue
        try:
            qtd = int(dados[chave])
        except (TypeError, ValueError):
            raise ValidationError(f"Quantidade inválida: {pb.beneficio.nome}.")
        if qtd < 0 or (not pb.incluido and qtd) or (pb.beneficio.quantitativo and qtd > pb.cota) or (not pb.beneficio.quantitativo and qtd > 1):
            raise ValidationError(f"Uso fora dos limites do plano: {pb.beneficio.nome}.")
        uso, _ = UsoBeneficio.objects.get_or_create(associado=associado, beneficio=pb.beneficio)
        anterior = uso.quantidade
        if anterior != qtd:
            uso.quantidade = qtd
            uso.save()
            registrar_auditoria(user, "ALTERAR_BENEFICIO", "AssociadoAT", associado.pk, pb.beneficio.codigo, str(anterior), str(qtd))
