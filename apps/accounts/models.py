"""Usuário customizado do Portal QuIIN (RF-001 a RF-003)."""
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
