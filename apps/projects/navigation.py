"""Retorno assinado para consultas internas, sem aceitar redirecionamento livre."""
from urllib.parse import urlsplit

from django.core import signing
from django.urls import Resolver404, resolve

SALT = "materials.navigation.v1"


def token_retorno(request, centro):
    return signing.dumps({"url": request.get_full_path(), "usuario": request.user.pk, "centro": centro.pk}, salt=SALT, compress=True)


def aplicar_retorno(request, contexto):
    token = request.GET.get("retorno", "")
    try:
        dados = signing.loads(token, salt=SALT, max_age=86400)
        destino = urlsplit(dados["url"])
        rota = resolve(destino.path)
        permitidas = ("materials:biblioteca", "projects:detalhe", "deliverables_at:detalhe")
        if (dados["usuario"] == request.user.pk and dados["centro"] == contexto["centro"].pk
                and not destino.scheme and not destino.netloc and rota.view_name in permitidas):
            contexto["voltar"] = dados["url"]
            contexto["retorno_consulta"] = dados["url"]
    except (signing.BadSignature, KeyError, TypeError, ValueError, Resolver404):
        pass
    return contexto
