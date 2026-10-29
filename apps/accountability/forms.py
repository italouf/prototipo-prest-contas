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
MENSAGEM_PERIODO = "Use MM/AAAA (ex.: 09/2026), trimestre (2T/2024) ou semestre (2S/2024)."

# Referências mensais e formatos legados; T/S minúsculos são normalizados.
_PADRAO_PERIODO = re.compile(r"(?:0[1-9]|1[0-2]|[1-4][TS])/[0-9]{4}")


class UploadPrestacaoForm(forms.Form):
    """Campos do upload: arquivo, centro e período de referência (SDD §10)."""

    arquivo = forms.FileField(label="Arquivo .xlsx")
    centro = forms.CharField(label="Centro de competência", max_length=200)
    periodo_referencia = forms.CharField(
        label="Período de referência", max_length=20,
        help_text="Use MM/AAAA (ex.: 09/2026). Referências trimestrais e semestrais também são aceitas.",
    )

    def clean_arquivo(self):
        arquivo = self.cleaned_data["arquivo"]
        if not arquivo.name.lower().endswith(".xlsx"):
            raise forms.ValidationError(MENSAGEM_EXTENSAO)
        if arquivo.size > TAMANHO_MAXIMO_ARQUIVO:
            raise forms.ValidationError(MENSAGEM_TAMANHO)
        return arquivo

    def clean_periodo_referencia(self):
        valor = self.cleaned_data["periodo_referencia"].strip().upper()
        if not _PADRAO_PERIODO.fullmatch(valor) or valor.endswith("/0000"):
            raise forms.ValidationError(MENSAGEM_PERIODO)
        return valor

    def clean_centro(self):
        return self.cleaned_data["centro"].strip()
