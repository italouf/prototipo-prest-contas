"""Endpoint e UI de upload das planilhas de prestação de contas (SDD §10).

O ``services.ingestar`` é a fronteira de segurança: aqui só se valida o
formulário (extensão/tamanho/período), se pré-detecta o tipo pelas tabelas/abas para
mensagens amigáveis (Ruling 2) e se traduz ``IngestaoError``/``ValidationError``
em ``messages`` pt-BR. Nada do Excel é executado — apenas lido.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import render

from apps.core.permissions import pode_importar_financeiro, sem_permissao

from . import services
from .forms import UploadPrestacaoForm
from .models import ImportacaoAcompanhamento
from .parsers.comum import ArquivoInvalidoError

_IMPORTACOES_HISTORICO = 30


@login_required
def importar(request):
    """GET: formulário + histórico; POST: ingestão do ``.xlsx`` (SDD §10)."""
    if not pode_importar_financeiro(request.user):
        return sem_permissao(request)
    form = UploadPrestacaoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        _processar_upload(request, form)
        form = UploadPrestacaoForm()  # upload já consumido; não repopular
    importacoes = (ImportacaoAcompanhamento.objects
                   .select_related("acompanhamento__centro")
                   .all()[:_IMPORTACOES_HISTORICO])
    return render(request, "accountability/importar.html", {
        "form": form,
        "modelos": services.VALIDADORES,
        "importacoes": importacoes,
    })


def _processar_upload(request, form: UploadPrestacaoForm) -> None:
    """Grava o upload em temporário, detecta o tipo e ingere (ou explica o erro)."""
    arquivo = form.cleaned_data["arquivo"]
    centro = form.cleaned_data["centro"]
    referencia = form.cleaned_data["periodo_referencia"]
    caminho = _salvar_temporario(arquivo)
    try:
        # Ruling 2: a pré-detecção pela estrutura dá a mensagem amigável; o
        # resultado — mesmo ``None`` — segue para o ``ingestar``, que revalida
        # tudo. Nunca contornar o serviço.
        try:
            abas, tabelas = services.inspecionar_arquivo(caminho)
        except ArquivoInvalidoError:
            messages.error(
                request,
                f'Não foi possível ler "{arquivo.name}". '
                f"Verifique se o arquivo não está corrompido.")
            return
        try:
            importacao = services.ingestar(
                services.detejar_tipo_arquivo(abas, tabelas),
                caminho, centro, referencia, request.user)
        except services.IngestaoError as exc:
            messages.error(request, str(exc))
            return
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return
        messages.success(request, _mensagem_sucesso(importacao, referencia))
        if importacao.avisos:
            messages.warning(request, importacao.avisos)
    finally:
        caminho.unlink(missing_ok=True)


def _salvar_temporario(arquivo) -> Path:
    """Upload em ``NamedTemporaryFile(suffix=".xlsx")`` para o parser abrir por caminho."""
    destino = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    try:
        for pedaco in arquivo.chunks():
            destino.write(pedaco)
    finally:
        destino.close()
    return Path(destino.name)


def _mensagem_sucesso(importacao: ImportacaoAcompanhamento, referencia: str) -> str:
    """Contagens por tipo do ``resumo`` gravado pela ingestão (brief Step 3)."""
    contagens = importacao.resumo or {}
    return (f"{contagens.get('projetos', 0)} projetos financeiros, "
            f"{contagens.get('kpis', 0)} KPIs e "
            f"{contagens.get('despesas', 0)} despesas importados "
            f"para {referencia}.")
