"""Motor de SLA mensal, links diretos, aprovação e Advertência Formal ITS1 (QuIIN / EMBRAPII)."""
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone

from apps.audit.services import registrar_auditoria
from apps.core.permissions import eh_gestor, pode_aprovar

from .models import CicloSemestral, CompetenciaMensalPilar, LogNotificacaoSLA


def _fmt_dt_local(dt: datetime) -> str:
    if dt is None:
        return ""
    local_dt = timezone.localtime(dt) if timezone.is_aware(dt) else dt
    return local_dt.strftime("%d/%m/%Y às %H:%M")


def gerar_link_direto(
    competencia: CompetenciaMensalPilar,
    aba_codigo: Optional[str] = None,
    base_url: str = "",
) -> str:
    """Gera URL direta contextualizada para o formulário mensal do pilar/aba."""
    path = f"/prestacao/semestral/acesso/{competencia.token_acesso}/"
    if aba_codigo:
        path = f"{path}?{urlencode({'aba': aba_codigo})}"
    if base_url:
        return f"{base_url.rstrip('/')}{path}"
    return path


def disparar_alertas_mensais(
    competencia_date=None,
    ciclo: Optional[CicloSemestral] = None,
    base_url: str = "",
    actor=None,
    incluir_relembrar: bool = False,
) -> Dict[str, Any]:
    """Dispara alertas mensais com link direto e prazo explícito para os pilares."""
    agora = timezone.now()
    estados = ["PENDENTE", "ALERTA_ENVIADO"] if incluir_relembrar else ["PENDENTE"]
    qs = CompetenciaMensalPilar.objects.select_related(
        "ciclo", "configuracao_pilar"
    ).filter(status__in=estados, configuracao_pilar__ativo=True)
    if ciclo is not None:
        qs = qs.filter(ciclo=ciclo)
    if competencia_date is not None:
        qs = qs.filter(competencia=competencia_date)

    enviados = 0
    links = []
    for comp in qs.order_by("competencia", "configuracao_pilar__ordem"):
        cfg = comp.configuracao_pilar
        link = gerar_link_direto(comp, base_url=base_url)
        prazo_str = _fmt_dt_local(comp.prazo_limite)
        assunto = (
            f"[QuIIN · Prestação Semestral EMBRAPII] Coleta Mensal "
            f"{comp.competencia_mm_aaaa} — Pilar {cfg.codigo} (Prazo: {prazo_str})"
        )
        mensagem = (
            f"Prezado(a) {cfg.responsavel_nome},\n\n"
            f"Está aberta a coleta mensal referente à competência {comp.competencia_mm_aaaa} "
            f"do ciclo {comp.ciclo.rotulo_painel} ({comp.ciclo.centro_competencia}), "
            f"sob sua responsabilidade no pilar {cfg.nome}.\n\n"
            f"• Prazo limite (deadline): {prazo_str}\n"
            f"• Acesso direto ao formulário: {link}\n\n"
            f"Após o vencimento do prazo sem submissão formal, o sistema registrará atraso e "
            f"emitirá automaticamente a advertência formal ITS1 com cópia para a Coordenação "
            f"({comp.ciclo.coordenacao_nome}).\n\n"
            f"Atenciosamente,\nSIG QuIIN — Governança EMBRAPII"
        )
        with transaction.atomic():
            status_ant = comp.status
            if comp.status == "PENDENTE":
                comp.status = "ALERTA_ENVIADO"
            if comp.alerta_inicial_em is None:
                comp.alerta_inicial_em = agora
            comp.save(update_fields=["status", "alerta_inicial_em", "atualizado_em"])

            LogNotificacaoSLA.objects.create(
                competencia=comp,
                tipo_evento="ALERTA_MENSAL",
                codigo_ocorrencia="",
                destinatario_nome=cfg.responsavel_nome,
                destinatario_email=cfg.responsavel_email,
                cc_emails="",
                link_direto=link,
                assunto=assunto,
                mensagem=mensagem,
                canal="EMAIL_E_IN_APP",
                disparado_por=actor if actor and getattr(actor, "is_authenticated", False) else None,
                metadados={
                    "competencia": comp.competencia_mm_aaaa,
                    "pilar": cfg.codigo,
                    "prazo_limite": prazo_str,
                },
            )
            registrar_auditoria(
                usuario=actor,
                acao="SEMESTRAL_ALERTA_MENSAL",
                entidade="CompetenciaMensalPilar",
                registro_id=comp.pk,
                campo="status",
                valor_anterior=status_ant,
                valor_novo=comp.status,
                justificativa=f"Alerta mensal enviado a {cfg.responsavel_email} com link direto ({comp.competencia_mm_aaaa}).",
                origem="SLA Engine",
            )
        EmailMessage(
            subject=assunto,
            body=mensagem,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[cfg.responsavel_email],
        ).send(fail_silently=True)
        enviados += 1
        links.append(link)

    return {"enviados": enviados, "links": links}


def verificar_sla_e_emitir_its1(
    agora: Optional[datetime] = None,
    ciclo: Optional[CicloSemestral] = None,
    base_url: str = "",
    actor=None,
) -> Dict[str, Any]:
    """Verifica competências vencidas sem submissão e emite advertência formal ITS1 + CC à Coordenação."""
    referencia = agora or timezone.now()
    qs = CompetenciaMensalPilar.objects.select_related(
        "ciclo", "configuracao_pilar"
    ).filter(
        status__in=["PENDENTE", "ALERTA_ENVIADO"],
        prazo_limite__lt=referencia,
        configuracao_pilar__ativo=True,
    )
    if ciclo is not None:
        qs = qs.filter(ciclo=ciclo)

    emitidas = 0
    ocorrencias = []
    for comp in qs.order_by("competencia", "configuracao_pilar__ordem"):
        cfg = comp.configuracao_pilar
        c = comp.ciclo
        link = gerar_link_direto(comp, base_url=base_url)
        prazo_str = _fmt_dt_local(comp.prazo_limite)
        emitida_str = _fmt_dt_local(referencia)

        assunto_its1 = (
            f"[ADVERTÊNCIA FORMAL ITS1] Atraso na Prestação de Contas {comp.competencia_mm_aaaa} "
            f"— Pilar {cfg.codigo} ({c.centro_competencia})"
        )
        msg_its1 = (
            f"ADVERTÊNCIA FORMAL — CÓDIGO DE OCORRÊNCIA: ITS1\n\n"
            f"Prezado(a) {cfg.responsavel_nome} (Responsável pelo Pilar {cfg.nome}),\n\n"
            f"Registramos o vencimento do prazo limite ({prazo_str}) sem a devida conclusão e "
            f"submissão dos dados mensais da competência {comp.competencia_mm_aaaa} "
            f"({c.rotulo_painel}).\n\n"
            f"• Status atualizado para: ATRASADO / ADVERTÊNCIA ITS1\n"
            f"• Data/hora da ocorrência: {emitida_str}\n"
            f"• Coordenação notificada em cópia: {c.coordenacao_nome} ({c.coordenacao_email})\n"
            f"• Link direto para regularização imediata: {link}\n\n"
            f"Solicitamos o preenchimento e submissão imediata para regularização no SIG QuIIN.\n\n"
            f"Governança QuIIN / SENAI CIMATEC"
        )

        assunto_coord = (
            f"[CC Coordenação · ITS1] Pilar {cfg.codigo} inadimplente na competência "
            f"{comp.competencia_mm_aaaa}"
        )
        msg_coord = (
            f"Prezada Coordenação ({c.coordenacao_nome} / Gestão QuIIN),\n\n"
            f"Informamos que foi emitida automaticamente uma Advertência Formal ITS1 para o "
            f"pilar {cfg.nome} ({cfg.codigo}) devido ao não cumprimento do prazo ({prazo_str}) "
            f"na competência {comp.competencia_mm_aaaa}.\n\n"
            f"• Responsável notificado: {cfg.responsavel_nome} <{cfg.responsavel_email}>\n"
            f"• Emissão da ITS1: {emitida_str}\n"
            f"• Link de acompanhamento: {link}\n\n"
            f"Este comunicado integra a trilha automática de governança e auditoria do SIG QuIIN."
        )

        with transaction.atomic():
            status_ant = comp.status
            comp.status = "ATRASADO_ITS1_EMITIDA"
            comp.its1_emitida_em = referencia
            comp.save(update_fields=["status", "its1_emitida_em", "atualizado_em"])

            log_resp = LogNotificacaoSLA.objects.create(
                competencia=comp,
                tipo_evento="ADVERTENCIA_ITS1",
                codigo_ocorrencia="ITS1",
                destinatario_nome=cfg.responsavel_nome,
                destinatario_email=cfg.responsavel_email,
                cc_emails=c.coordenacao_email,
                link_direto=link,
                assunto=assunto_its1,
                mensagem=msg_its1,
                canal="EMAIL_E_IN_APP",
                disparado_por=actor if actor and getattr(actor, "is_authenticated", False) else None,
                metadados={
                    "codigo": "ITS1",
                    "pilar": cfg.codigo,
                    "competencia": comp.competencia_mm_aaaa,
                    "prazo_limite": prazo_str,
                    "coordenacao_cc": c.coordenacao_email,
                },
            )
            LogNotificacaoSLA.objects.create(
                competencia=comp,
                tipo_evento="COMUNICADO_COORDENACAO",
                codigo_ocorrencia="ITS1",
                destinatario_nome=c.coordenacao_nome,
                destinatario_email=c.coordenacao_email,
                cc_emails=cfg.responsavel_email,
                link_direto=link,
                assunto=assunto_coord,
                mensagem=msg_coord,
                canal="EMAIL_E_IN_APP",
                disparado_por=actor if actor and getattr(actor, "is_authenticated", False) else None,
                metadados={
                    "codigo": "ITS1",
                    "pilar": cfg.codigo,
                    "competencia": comp.competencia_mm_aaaa,
                    "responsavel": cfg.responsavel_email,
                    "log_advertencia_id": log_resp.pk,
                },
            )
            registrar_auditoria(
                usuario=actor,
                acao="SEMESTRAL_ITS1_EMITIDA",
                entidade="CompetenciaMensalPilar",
                registro_id=comp.pk,
                campo="status",
                valor_anterior=status_ant,
                valor_novo="ATRASADO_ITS1_EMITIDA",
                justificativa=(
                    f"Advertência ITS1 emitida para {cfg.responsavel_email} com cópia à Coordenação "
                    f"({c.coordenacao_nome} <{c.coordenacao_email}>) após prazo {prazo_str}."
                ),
                origem="SLA Engine",
            )

        EmailMessage(
            subject=assunto_its1,
            body=msg_its1,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[cfg.responsavel_email],
            cc=[c.coordenacao_email],
        ).send(fail_silently=True)

        EmailMessage(
            subject=assunto_coord,
            body=msg_coord,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[c.coordenacao_email],
        ).send(fail_silently=True)

        emitidas += 1
        ocorrencias.append(
            {
                "competencia_id": comp.pk,
                "pilar": cfg.codigo,
                "competencia": comp.competencia_mm_aaaa,
                "responsavel": cfg.responsavel_email,
                "coordenacao": c.coordenacao_email,
            }
        )

    return {"emitidas": emitidas, "ocorrencias": ocorrencias}


def submeter_competencia(
    competencia: CompetenciaMensalPilar,
    usuario,
    observacao: str = "",
    agora: Optional[datetime] = None,
) -> CompetenciaMensalPilar:
    """Conclui a competência mensal do pilar e envia para análise da Coordenação."""
    if competencia.ciclo.bloqueado_para_edicao_focal and not eh_gestor(usuario):
        raise PermissionDenied(
            f"O ciclo {competencia.ciclo.rotulo_painel} está em status "
            f"'{competencia.ciclo.get_status_display()}'. Apenas Master/Admin pode alterar ou submeter dados."
        )

    referencia = agora or timezone.now()
    status_ant = competencia.status
    era_atrasada = status_ant == "ATRASADO_ITS1_EMITIDA"
    ja_teve_its1 = era_atrasada or status_ant == "REGULARIZADO" or competencia.its1_emitida_em is not None

    with transaction.atomic():
        competencia.submetido_em = referencia
        competencia.submetido_por = usuario if usuario and getattr(usuario, "is_authenticated", False) else None
        if observacao:
            competencia.observacao_submissao = observacao

        competencia.status_aprovacao = "EM_ANALISE"
        competencia.revisado_por = None
        competencia.revisado_em = None
        competencia.comentario_revisao = ""
        competencia.arquivado_painel = False
        competencia.arquivado_em = None

        update_fields = [
            "status",
            "status_aprovacao",
            "submetido_em",
            "submetido_por",
            "observacao_submissao",
            "revisado_por",
            "revisado_em",
            "comentario_revisao",
            "arquivado_painel",
            "arquivado_em",
            "atualizado_em",
        ]
        if era_atrasada:
            competencia.status = "REGULARIZADO"
            competencia.regularizado_em = referencia
            update_fields.append("regularizado_em")
        elif ja_teve_its1:
            competencia.status = "REGULARIZADO"
        else:
            competencia.status = "SUBMETIDO_NO_PRAZO"

        competencia.save(update_fields=update_fields)

        if era_atrasada:
            c = competencia.ciclo
            cfg = competencia.configuracao_pilar
            link = gerar_link_direto(competencia)
            LogNotificacaoSLA.objects.create(
                competencia=competencia,
                tipo_evento="REGULARIZACAO",
                codigo_ocorrencia="ITS1",
                destinatario_nome=c.coordenacao_nome,
                destinatario_email=c.coordenacao_email,
                cc_emails=cfg.responsavel_email,
                link_direto=link,
                assunto=f"[Regularizado após ITS1] {cfg.codigo} · {competencia.competencia_mm_aaaa}",
                mensagem=(
                    f"O pilar {cfg.nome} ({cfg.codigo}) concluiu e regularizou a competência "
                    f"{competencia.competencia_mm_aaaa} em {_fmt_dt_local(referencia)}."
                ),
                canal="IN_APP",
                disparado_por=competencia.submetido_por,
            )

        prefixo_ciclo = (
            f"[Ajuste excepcional Master/Admin em ciclo {competencia.ciclo.status}] "
            if competencia.ciclo.bloqueado_para_edicao_focal
            else ""
        )
        registrar_auditoria(
            usuario=usuario,
            acao="SEMESTRAL_REGULARIZADO" if era_atrasada else "SEMESTRAL_SUBMETIDO",
            entidade="CompetenciaMensalPilar",
            registro_id=competencia.pk,
            campo="status",
            valor_anterior=status_ant,
            valor_novo=competencia.status,
            justificativa=prefixo_ciclo + (observacao or "Submissão mensal da prestação semestral (enviada para análise)."),
            origem="Portal",
        )
    return competencia


def aprovar_competencia(
    competencia: CompetenciaMensalPilar,
    usuario,
    comentario: str = "",
    base_url: str = "",
    agora: Optional[datetime] = None,
) -> CompetenciaMensalPilar:
    """Aprova a coleta mensal semestral de um pilar (Master/Admin)."""
    if not pode_aprovar(usuario):
        raise PermissionDenied("Apenas Master/Admin pode aprovar competências semestrais.")
    if competencia.status_aprovacao == "APROVADO":
        return competencia
    if competencia.status_aprovacao != "EM_ANALISE":
        raise ValidationError("Apenas competências em análise podem ser aprovadas.")

    referencia = agora or timezone.now()
    aprov_ant = competencia.status_aprovacao
    comentario_limpo = (comentario or "").strip()
    cfg = competencia.configuracao_pilar
    c = competencia.ciclo
    link = gerar_link_direto(competencia, base_url=base_url)

    assunto = (
        f"[QuIIN · Prestação Semestral] Competência {competencia.competencia_mm_aaaa} "
        f"aprovada — Pilar {cfg.codigo}"
    )
    revisor_nome = getattr(usuario, "nome_exibicao", None) or getattr(usuario, "username", "Coordenação")
    mensagem = (
        f"Prezado(a) {cfg.responsavel_nome},\n\n"
        f"A entrega mensal da competência {competencia.competencia_mm_aaaa} ({c.rotulo_painel}) "
        f"do pilar {cfg.nome} ({cfg.codigo}) foi APROVADA por {revisor_nome} em {_fmt_dt_local(referencia)}.\n\n"
        + (f"Comentário da revisão: {comentario_limpo}\n\n" if comentario_limpo else "")
        + f"• Link de consulta: {link}\n\n"
        f"Os registros estão consolidados para a exportação oficial EMBRAPII v3.1.\n\n"
        f"Governança QuIIN / SENAI CIMATEC"
    )

    with transaction.atomic():
        competencia.status_aprovacao = "APROVADO"
        competencia.revisado_por = usuario
        competencia.revisado_em = referencia
        competencia.comentario_revisao = comentario_limpo
        competencia.arquivado_painel = False
        competencia.arquivado_em = None
        competencia.save(
            update_fields=[
                "status_aprovacao",
                "revisado_por",
                "revisado_em",
                "comentario_revisao",
                "arquivado_painel",
                "arquivado_em",
                "atualizado_em",
            ]
        )
        LogNotificacaoSLA.objects.create(
            competencia=competencia,
            tipo_evento="APROVACAO_SEMESTRAL",
            codigo_ocorrencia="",
            destinatario_nome=cfg.responsavel_nome,
            destinatario_email=cfg.responsavel_email,
            cc_emails="",
            link_direto=link,
            assunto=assunto,
            mensagem=mensagem,
            canal="EMAIL_E_IN_APP",
            disparado_por=usuario,
            metadados={
                "pilar": cfg.codigo,
                "competencia": competencia.competencia_mm_aaaa,
                "decisao": "APROVADO",
            },
        )
        registrar_auditoria(
            usuario=usuario,
            acao="SEMESTRAL_APROVADO",
            entidade="CompetenciaMensalPilar",
            registro_id=competencia.pk,
            campo="status_aprovacao",
            valor_anterior=aprov_ant,
            valor_novo="APROVADO",
            justificativa=comentario_limpo or f"Aprovação da coleta semestral {competencia.competencia_mm_aaaa} ({cfg.codigo}).",
            origem="Portal",
        )

    EmailMessage(
        subject=assunto,
        body=mensagem,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[cfg.responsavel_email],
    ).send(fail_silently=True)
    return competencia


def devolver_competencia(
    competencia: CompetenciaMensalPilar,
    usuario,
    justificativa: str = "",
    base_url: str = "",
    agora: Optional[datetime] = None,
) -> CompetenciaMensalPilar:
    """Devolve a coleta mensal semestral para correção com justificativa obrigatória (Master/Admin)."""
    if not pode_aprovar(usuario):
        raise PermissionDenied("Apenas Master/Admin pode devolver competências semestrais.")
    justificativa_limpa = (justificativa or "").strip()
    if not justificativa_limpa:
        raise ValidationError("Informe a justificativa para devolver a competência.")
    if competencia.status_aprovacao not in ("EM_ANALISE", "APROVADO"):
        raise ValidationError("Apenas competências submetidas podem ser devolvidas para correção.")

    referencia = agora or timezone.now()
    aprov_ant = competencia.status_aprovacao
    cfg = competencia.configuracao_pilar
    c = competencia.ciclo
    link = gerar_link_direto(competencia, base_url=base_url)

    assunto = (
        f"[QuIIN · Prestação Semestral] Competência {competencia.competencia_mm_aaaa} "
        f"devolvida para correção — Pilar {cfg.codigo}"
    )
    revisor_nome = getattr(usuario, "nome_exibicao", None) or getattr(usuario, "username", "Coordenação")
    mensagem = (
        f"Prezado(a) {cfg.responsavel_nome},\n\n"
        f"A entrega mensal da competência {competencia.competencia_mm_aaaa} ({c.rotulo_painel}) "
        f"do pilar {cfg.nome} ({cfg.codigo}) foi DEVOLVIDA para correção por {revisor_nome} "
        f"em {_fmt_dt_local(referencia)}.\n\n"
        f"• Justificativa da Coordenação:\n{justificativa_limpa}\n\n"
        f"• Link direto para corrigir e reenviar: {link}\n\n"
        f"Após ajustar os registros solicitados, clique novamente em 'Concluir e submeter competência'.\n\n"
        f"Governança QuIIN / SENAI CIMATEC"
    )

    with transaction.atomic():
        competencia.status_aprovacao = "DEVOLVIDO"
        competencia.revisado_por = usuario
        competencia.revisado_em = referencia
        competencia.comentario_revisao = justificativa_limpa
        competencia.arquivado_painel = False
        competencia.arquivado_em = None
        competencia.save(
            update_fields=[
                "status_aprovacao",
                "revisado_por",
                "revisado_em",
                "comentario_revisao",
                "arquivado_painel",
                "arquivado_em",
                "atualizado_em",
            ]
        )
        LogNotificacaoSLA.objects.create(
            competencia=competencia,
            tipo_evento="DEVOLUCAO_SEMESTRAL",
            codigo_ocorrencia="",
            destinatario_nome=cfg.responsavel_nome,
            destinatario_email=cfg.responsavel_email,
            cc_emails="",
            link_direto=link,
            assunto=assunto,
            mensagem=mensagem,
            canal="EMAIL_E_IN_APP",
            disparado_por=usuario,
            metadados={
                "pilar": cfg.codigo,
                "competencia": competencia.competencia_mm_aaaa,
                "decisao": "DEVOLVIDO",
                "justificativa": justificativa_limpa,
            },
        )
        registrar_auditoria(
            usuario=usuario,
            acao="SEMESTRAL_DEVOLVIDO",
            entidade="CompetenciaMensalPilar",
            registro_id=competencia.pk,
            campo="status_aprovacao",
            valor_anterior=aprov_ant,
            valor_novo="DEVOLVIDO",
            justificativa=justificativa_limpa,
            origem="Portal",
        )

    EmailMessage(
        subject=assunto,
        body=mensagem,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[cfg.responsavel_email],
    ).send(fail_silently=True)
    return competencia


def arquivar_competencia(
    competencia: CompetenciaMensalPilar,
    usuario,
    arquivar: bool = True,
    agora: Optional[datetime] = None,
) -> CompetenciaMensalPilar:
    """Arquiva ou restaura uma competência aprovada na coluna Aprovados do Painel de aprovação."""
    if not pode_aprovar(usuario):
        raise PermissionDenied("Apenas Master/Admin pode arquivar competências aprovadas.")
    if arquivar and competencia.status_aprovacao != "APROVADO":
        raise ValidationError("Apenas competências aprovadas podem ser arquivadas.")

    referencia = agora or timezone.now()
    anterior = competencia.arquivado_painel
    if anterior == arquivar:
        return competencia

    with transaction.atomic():
        competencia.arquivado_painel = arquivar
        competencia.arquivado_em = referencia if arquivar else None
        competencia.save(update_fields=["arquivado_painel", "arquivado_em", "atualizado_em"])
        registrar_auditoria(
            usuario=usuario,
            acao="SEMESTRAL_ARQUIVADO" if arquivar else "SEMESTRAL_DESARQUIVADO",
            entidade="CompetenciaMensalPilar",
            registro_id=competencia.pk,
            campo="arquivado_painel",
            valor_anterior=str(anterior),
            valor_novo=str(arquivar),
            justificativa=(
                f"Card aprovado {'arquivado' if arquivar else 'restaurado'} no Painel de aprovação "
                f"({competencia.configuracao_pilar.codigo} · {competencia.competencia_mm_aaaa})."
            ),
            origem="Portal",
        )
    return competencia
