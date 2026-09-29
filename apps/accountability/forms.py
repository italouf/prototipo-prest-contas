"""Formulário do upload das planilhas de prestação de contas (SDD §10).

Valida aqui o que é regra de formulário — extensão, tamanho e formato do
período — **antes** de tocar no parser; a validação do conteúdo do arquivo
continua sendo do ``services.ingestar`` (fronteira de segurança).
"""

from __future__ import annotations

import re

from django import forms

# SDD §10 / brief: só ``.xlsx`` e no máximo 25 MB por upload.
TAMANHO_MAXIMO_ARQUIVO = 25 * 1024 * 1024
MENSAGEM_EXTENSAO = "Envie um arquivo .xlsx."
MENSAGEM_TAMANHO = "O arquivo deve ter no máximo 25 MB."
MENSAGEM_PERIODO = "Use o formato 2T/2024."

# ``[1-4][TS]``: trimestre (T) ou semestre (S) — o sufixo ``s`` minúsculo é
# aceito e normalizado para maiúsculas no ``clean_periodo_referencia``.
_PADRAO_PERIODO = re.compile(r"^[1-4][TS]/\d{4}$")


class UploadPrestacaoForm(forms.Form):
    """Campos do upload: arquivo, centro e período de referência (SDD §10)."""

    arquivo = forms.FileField(label="Arquivo .xlsx")
    centro = forms.CharField(label="Centro de competência", max_length=200)
    periodo_referencia = forms.CharField(label="Período de referência", max_length=20)

    def clean_arquivo(self):
        arquivo = self.cleaned_data["arquivo"]
        if not arquivo.name.lower().endswith(".xlsx"):
            raise forms.ValidationError(MENSAGEM_EXTENSAO)
        if arquivo.size > TAMANHO_MAXIMO_ARQUIVO:
            raise forms.ValidationError(MENSAGEM_TAMANHO)
        return arquivo

    def clean_periodo_referencia(self):
        valor = self.cleaned_data["periodo_referencia"].strip().upper()
        if not _PADRAO_PERIODO.match(valor):
            raise forms.ValidationError(MENSAGEM_PERIODO)
        return valor

    def clean_centro(self):
        return self.cleaned_data["centro"].strip()
