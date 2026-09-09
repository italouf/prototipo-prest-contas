"""Testes de auditoria e controle de acesso (RF-007, RF-100 a RF-106)."""
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.audit.services import registrar_auditoria
from apps.core.permissions import adicionar_grupo, garantir_grupos


class AuditoriaTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.auditor = User.objects.create_user(username="auditor", password="auditor123")
        self.auditor = adicionar_grupo(self.auditor, "Auditor")
        self.lideranca = User.objects.create_user(username="lideranca", password="lider123")
        self.lideranca = adicionar_grupo(self.lideranca, "Lideranca")
        self.master = User.objects.create_user(username="erica", password="erica123")
        self.master = adicionar_grupo(self.master, "Master")
        for i in range(30):
            registrar_auditoria(self.master, "LOGIN", "Sessao", campo="login", valor_novo="sucesso")

    def test_registro_de_auditoria_guarda_campos_principais(self):
        registrar_auditoria(self.auditor, "FECHAR_PERIODO", "Periodo", registro_id=9, campo="status", valor_novo="FECHADO")
        registro = AuditLog.objects.get(acao="FECHAR_PERIODO")
        self.assertEqual(registro.usuario, self.auditor)
        self.assertEqual(registro.entidade, "Periodo")
        self.assertEqual(registro.registro_id, "9")
        self.assertIsNotNone(registro.data_hora)

    def test_auditor_visualiza_auditoria(self):
        self.client.force_login(self.auditor)
        resposta = self.client.get(reverse("audit:lista"))
        self.assertEqual(resposta.status_code, 200)

    def test_lideranca_nao_acessa_auditoria(self):
        self.client.force_login(self.lideranca)
        resposta = self.client.get(reverse("audit:lista"))
        self.assertEqual(resposta.status_code, 403)

    def test_auditoria_filtra_por_acao(self):
        registrar_auditoria(self.master, "FECHAR_PERIODO", "Periodo", registro_id=1, campo="status", valor_novo="FECHADO")
        self.client.force_login(self.auditor)
        resposta = self.client.get(reverse("audit:lista"), {"acao": "FECHAR_PERIODO"})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["total"], 1)
        self.assertContains(resposta, "Período fechado")

    def test_auditoria_pagina_resultados(self):
        self.client.force_login(self.auditor)
        primeira = self.client.get(reverse("audit:lista"))
        self.assertEqual(primeira.context["total"], 30)
        self.assertEqual(primeira.context["page_obj"].paginator.num_pages, 2)
        self.assertEqual(primeira.context["page_obj"].object_list.count(), 25)
        segunda = self.client.get(reverse("audit:lista"), {"page": 2})
        self.assertEqual(segunda.context["page_obj"].object_list.count(), 5)