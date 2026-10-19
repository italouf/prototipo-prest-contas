"""Usuário customizado do Portal QuIIN (RF-001 a RF-003)."""
import re

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    nome = models.CharField("Nome de exibição", max_length=150, blank=True)

    class Meta:
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"

    def __str__(self):
        return self.nome or self.username

    @property
    def nome_exibicao(self):
        return self.nome or self.username

    @property
    def nome_topbar(self):
        """Nome sem indicações de perfil adicionadas ao cadastro de exibição."""
        return re.sub(
            r"\s*\((?:master|admin|administrador(?:a)?|ponto\s*focal|lideran[çc]a|auditor(?:a)?|coordena[çc][ãa]o)\)\s*$",
            "", self.nome_exibicao, flags=re.IGNORECASE,
        ).strip() or self.username
