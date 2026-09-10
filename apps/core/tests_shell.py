"""Testes do shell de navegação (R1)."""
from datetime import date

from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.context_processors import nav
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.entries.models import Lancamento
from apps.entries.services import salvar_ou_enviar
from apps.indicators.models import Indicador, Meta
from apps.periods.models import Periodo
from apps.pillars.models import Pilar, UsuarioPilar


class NavContextoTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.erica = adicionar_grupo(
            User.objects.create_user(username="erica_shell", password="x"), "Master"
        )
        self.focal = adicionar_grupo(
            User.objects.create_user(username="focal_shell", password="x"), "PontoFocal"
        )
        self.pdi = Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=1)
        UsuarioPilar.objects.create(usuario=self.focal, pilar=self.pdi)
        self.periodo = Periodo.objects.create(
            competencia=date(2026, 6, 1), status="ABERTO", aberto_por=self.erica
        )
        self.ind = Indicador.objects.create(
            pilar=self.pdi, codigo="PDI-PROJ-INI", nome="Projetos iniciados", tipo="QTD"
        )
        Meta.objects.create(
            indicador=self.ind, competencia_inicio=date(2026, 1, 1),
            competencia_fim=date(2026, 12, 31), periodicidade="MENSAL", valor=2,
        )
        salvar_ou_enviar(self.periodo, self.pdi, self.erica, {str(self.ind.pk): {"valor": "1"}}, enviar=True)

    def _contexto(self, usuario):
        requisicao = RequestFactory().get("/")
        requisicao.user = usuario
        return nav(requisicao)

    def test_gestor_ve_pendencia_de_aprovacao_por_pilar(self):
        contexto = self._contexto(self.erica)
        self.assertEqual(contexto["pendencias_nav"][self.pdi.pk], 1)
        self.assertEqual(contexto["total_pendencias"], 1)
        self.assertIn(self.periodo, list(contexto["periodos_nav"]))

    def test_focal_ve_pendencia_de_devolvido(self):
        lancamento = Lancamento.objects.get(periodo=self.periodo)
        lancamento.status = "DEVOLVIDO"
        lancamento.save(update_fields=["status"])
        contexto = self._contexto(self.focal)
        self.assertEqual(contexto["pendencias_nav"][self.pdi.pk], 1)

    def test_anonimo_nao_recebe_contexto_de_navegacao(self):
        from django.contrib.auth.models import AnonymousUser

        requisicao = RequestFactory().get("/")
        requisicao.user = AnonymousUser()
        self.assertEqual(nav(requisicao), {})


class BuscaGlobalTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.erica = adicionar_grupo(
            User.objects.create_user(username="erica_busca", password="x"), "Master"
        )
        self.focal = adicionar_grupo(
            User.objects.create_user(username="focal_busca", password="x"), "PontoFocal"
        )
        self.pdi = Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=1)
        self.at = Pilar.objects.create(codigo="AT", nome="Associação Tecnológica", ordem=2)
        UsuarioPilar.objects.create(usuario=self.focal, pilar=self.pdi)
        self.ind_pdi = Indicador.objects.create(
            pilar=self.pdi, codigo="PDI-ARTIGOS", nome="Artigos publicados", tipo="QTD"
        )
        self.ind_at = Indicador.objects.create(
            pilar=self.at, codigo="AT-CNPJ-NOVOS", nome="CNPJs novos", tipo="QTD"
        )

    def test_busca_requer_login(self):
        resposta = self.client.get(reverse("core:busca"), {"q": "artigos"})
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/accounts/login/", resposta["Location"])

    def test_busca_respeita_pilares_visiveis(self):
        self.client.force_login(self.focal)
        resposta = self.client.get(reverse("core:busca"), {"q": "cnpj"})
        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, "AT-CNPJ-NOVOS")
        resposta_pdi = self.client.get(reverse("core:busca"), {"q": "artigos"})
        self.assertContains(resposta_pdi, "PDI-ARTIGOS")

    def test_busca_com_menos_de_dois_caracteres_nao_busca(self):
        self.client.force_login(self.erica)
        resposta = self.client.get(reverse("core:busca"), {"q": "a"})
        self.assertContains(resposta, "ao menos 2 caracteres")

    def test_busca_sem_htmx_renderiza_pagina_completa(self):
        self.client.force_login(self.erica)
        resposta = self.client.get(reverse("core:busca"), {"q": "artigos"})
        self.assertContains(resposta, "Busca")
        self.assertContains(resposta, "PDI-ARTIGOS")
