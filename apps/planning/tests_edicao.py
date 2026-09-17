"""Testes da edição auditada e das exportações do plano anual (L7, TDD)."""
from datetime import date
from decimal import Decimal as D

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.pillars.models import Pilar, UsuarioPilar
from apps.planning.models import PlanoAnual
from apps.planning.tests import criar_base_anual

APLICAR = "planning:aplicar"


def grade(**kwargs):
    base = {"ano": "todos", "base": "fin"}
    base.update(kwargs)
    return base


class EdicaoPlanoAnualTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        criar_base_anual()

    def setUp(self):
        garantir_grupos()
        self.master = adicionar_grupo(User.objects.create_user(username="ed_master", password="x"), "Master")
        self.focal = adicionar_grupo(User.objects.create_user(username="ed_focal", password="x"), "PontoFocal")
        self.lider = adicionar_grupo(User.objects.create_user(username="ed_lider", password="x"), "Lideranca")
        UsuarioPilar.objects.create(
            usuario=self.focal, pilar=Pilar.objects.get(codigo="PDI"))

    def test_master_edita_valores_e_audita(self):
        self.client.force_login(self.master)
        resposta = self.client.post(reverse(APLICAR), grade(**{
            "v__2026__financeiro__PDI__previsto": "11",
            "v__2026__financeiro__PDI__executado": "9",
        }))
        self.assertRedirects(resposta, "/?ano=todos&base=fin", fetch_redirect_response=False)
        linha = PlanoAnual.objects.get(ano=2026, pilar__codigo="PDI", base="financeiro")
        self.assertEqual((linha.previsto, linha.executado), (D(11), D(9)))
        logs = AuditLog.objects.filter(entidade="PlanoAnual", registro_id=str(linha.pk))
        self.assertEqual(logs.count(), 2)
        campos = {l.campo for l in logs}
        self.assertEqual(campos, {"previsto", "executado"})

    def test_sem_mudanca_nao_audita(self):
        self.client.force_login(self.master)
        antes = AuditLog.objects.count()
        self.client.post(reverse(APLICAR), grade(**{"v__2026__financeiro__PDI__previsto": "10"}))
        self.assertEqual(AuditLog.objects.count(), antes)

    def test_focal_edita_proprio_pilar(self):
        self.client.force_login(self.focal)
        resposta = self.client.post(reverse(APLICAR), grade(**{
            "v__2026__fisico__PDI__executado": "6",
        }))
        self.assertEqual(resposta.status_code, 302)
        linha = PlanoAnual.objects.get(ano=2026, pilar__codigo="PDI", base="fisico")
        self.assertEqual(linha.executado, D(6))

    def test_focal_nao_edita_pilar_alheio(self):
        self.client.force_login(self.focal)
        resposta = self.client.post(reverse(APLICAR), grade(**{
            "v__2026__financeiro__INFRA__executado": "5",
        }))
        self.assertEqual(resposta.status_code, 403)
        linha = PlanoAnual.objects.get(ano=2026, pilar__codigo="INFRA", base="financeiro")
        self.assertEqual(linha.executado, D(4))

    def test_lideranca_recebe_403_e_nada_muda(self):
        self.client.force_login(self.lider)
        resposta = self.client.post(reverse(APLICAR), grade(**{
            "v__2026__financeiro__PDI__executado": "99",
        }))
        self.assertEqual(resposta.status_code, 403)
        linha = PlanoAnual.objects.get(ano=2026, pilar__codigo="PDI", base="financeiro")
        self.assertEqual(linha.executado, D(8))

    def test_valores_invalidos_rejeitam_tudo(self):
        self.client.force_login(self.master)
        for dados in (
            {"v__2026__financeiro__PDI__previsto": "-1"},
            {"v__2026__fisico__PDI__executado": "2.5"},
            {"v__2026__financeiro__PDI__previsto": "abc"},
            {"v__2030__financeiro__PDI__previsto": "5"},
            {"v__2026__financeiro__XX__previsto": "5"},
        ):
            with self.subTest(dados=dados):
                resposta = self.client.post(reverse(APLICAR), grade(**dados))
                self.assertIn(resposta.status_code, (302, 400))
        linha = PlanoAnual.objects.get(ano=2026, pilar__codigo="PDI", base="financeiro")
        self.assertEqual((linha.previsto, linha.executado), (D(10), D(8)))

    def test_aplicar_e_baixar_devolve_html(self):
        self.client.force_login(self.master)
        resposta = self.client.post(reverse(APLICAR), grade(**{
            "v__2026__financeiro__PDI__executado": "9", "acao": "baixar",
        }))
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("attachment", resposta["Content-Disposition"])
        self.assertIn("dashboard_quiin", resposta["Content-Disposition"])
        linha = PlanoAnual.objects.get(ano=2026, pilar__codigo="PDI", base="financeiro")
        self.assertEqual(linha.executado, D(9))

    def test_exige_login(self):
        resposta = self.client.post(reverse(APLICAR), grade())
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/accounts/login/", resposta["Location"])


class ExportacoesPlanoAnualTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        criar_base_anual()

    def setUp(self):
        garantir_grupos()
        self.master = adicionar_grupo(User.objects.create_user(username="ex_master", password="x"), "Master")

    def test_csv_reflete_periodo_e_base(self):
        self.client.force_login(self.master)
        resposta = self.client.get(reverse("planning:csv"), {"ano": "2026", "base": "fis"})
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("text/csv", resposta["Content-Type"])
        self.assertIn("attachment", resposta["Content-Disposition"])
        conteudo = resposta.content.decode("utf-8-sig")
        linhas = conteudo.splitlines()
        self.assertEqual(linhas[0], "Bloco;Item;Indicador;Unidade;Período;Valor")
        self.assertIn("4.1 PPI;PDI;Projetado;metas;Ano 3: 2026;6", linhas)
        self.assertIn("4.2 Captação de recursos;Associação Tecnológica (AT);Executado;metas;Ano 3: 2026;1", linhas)
        self.assertNotIn("R$ milhoes", conteudo)

    def test_csv_invalido_redireciona(self):
        self.client.force_login(self.master)
        resposta = self.client.get(reverse("planning:csv"), {"ano": "2030"})
        self.assertRedirects(resposta, "/?ano=todos&base=fin", fetch_redirect_response=False)

    def test_download_html_standalone(self):
        self.client.force_login(self.master)
        resposta = self.client.get(reverse("planning:export_html"), {"ano": "2026", "base": "fin"})
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("text/html", resposta["Content-Type"])
        self.assertIn("attachment", resposta["Content-Disposition"])
        html = resposta.content.decode()
        self.assertIn("Ano 3: 2026", html)
        self.assertRegex(html, r"R\$\s*</span>\s*15\s*<span")

    def test_exportacoes_exigem_login(self):
        for nome in ("planning:csv", "planning:export_html"):
            resposta = self.client.get(reverse(nome))
            self.assertEqual(resposta.status_code, 302)
