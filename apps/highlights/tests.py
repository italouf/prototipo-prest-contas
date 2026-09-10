"""Testes do app highlights — Destaques Qualitativos (LOOP 2)."""
from datetime import date, timedelta
from unittest import mock

from django.contrib import admin
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.highlights.models import DestaqueMensal
from apps.periods.models import Periodo
from apps.pillars.models import Pilar


def _request(path="/", usuario=None):
    fabrica = RequestFactory()
    requisicao = fabrica.get(path)
    requisicao.user = usuario
    return requisicao


def _contexto_de_render(mock_render):
    # render(requisicao, template, contexto)
    return mock_render.call_args[0][2]


class DestaqueMensalModeloTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.usuario = User.objects.create_user(username="erica", password="erica123")
        self.periodo = Periodo.objects.create(competencia=date(2026, 6, 1), status="ABERTO")

    def test_str_retorna_titulo_e_rotulo_do_periodo(self):
        destaque = DestaqueMensal.objects.create(
            periodo=self.periodo, titulo="Recorde de captação", descricao="Detalhes.", criado_por=self.usuario
        )
        self.assertEqual(str(destaque), f"Recorde de captação ({self.periodo.rotulo})")


class DashboardDestaquesTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.master = adicionar_grupo(User.objects.create_user(username="erica", password="x"), "Master")
        self.pdi = Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=1)
        self.formacao = Pilar.objects.create(codigo="FORMACAO", nome="Formação", ordem=2)
        self.periodo = Periodo.objects.create(competencia=date(2026, 6, 1), status="ABERTO")

    def test_home_traz_destaque_geral_e_do_pilar_limitado_a_6(self):
        from apps.core.views import dashboard

        base = timezone.now()
        criados = []
        for i in range(7):
            d = DestaqueMensal.objects.create(
                periodo=self.periodo,
                pilar=self.pdi if i % 2 == 0 else None,
                titulo=f"Destaque {i}",
                descricao=f"Descrição {i}.",
            )
            criados.append(d)
        # Ordenação determinística por criado_em.
        for i, d in enumerate(criados):
            DestaqueMensal.objects.filter(pk=d.pk).update(criado_em=base + timedelta(seconds=i))

        requisicao = _request("/", self.master)
        with mock.patch("apps.core.views.render") as mock_render:
            mock_render.return_value = HttpResponse()
            dashboard(requisicao)
        contexto = _contexto_de_render(mock_render)
        self.assertIn("destaques", contexto)
        destaques = list(contexto["destaques"])
        self.assertEqual(len(destaques), 6)
        # Últimos 6, mais recente primeiro.
        self.assertEqual(
            [d.titulo for d in destaques],
            ["Destaque 6", "Destaque 5", "Destaque 4", "Destaque 3", "Destaque 2", "Destaque 1"],
        )

    def test_home_com_destaque_geral_e_de_pilar_aparecem_no_contexto(self):
        from apps.core.views import dashboard

        geral = DestaqueMensal.objects.create(
            periodo=self.periodo, pilar=None, titulo="Geral do mês", descricao="Visão geral."
        )
        do_pilar = DestaqueMensal.objects.create(
            periodo=self.periodo, pilar=self.pdi, titulo="Feito do PDI", descricao="Detalhe do pilar."
        )
        requisicao = _request("/", self.master)
        with mock.patch("apps.core.views.render") as mock_render:
            mock_render.return_value = HttpResponse()
            dashboard(requisicao)
        destaques = list(_contexto_de_render(mock_render)["destaques"])
        self.assertIn(geral, destaques)
        self.assertIn(do_pilar, destaques)

    def test_home_sem_periodo_traz_destaques_vazio(self):
        from apps.core.views import dashboard

        Periodo.objects.all().delete()
        DestaqueMensal.objects.all().delete()
        requisicao = _request("/", self.master)
        with mock.patch("apps.core.views.render") as mock_render:
            mock_render.return_value = HttpResponse()
            dashboard(requisicao)
        self.assertEqual(list(_contexto_de_render(mock_render)["destaques"]), [])


class PilarDestaquesTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.master = adicionar_grupo(User.objects.create_user(username="erica", password="x"), "Master")
        self.pdi = Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=1)
        self.outro = Pilar.objects.create(codigo="AT", nome="AT", ordem=2)
        self.periodo = Periodo.objects.create(competencia=date(2026, 6, 1), status="ABERTO")

    def test_pilar_filtra_geral_mais_do_pilar_e_esconde_outro_pilar(self):
        from apps.core.views import pilar as pilar_view

        geral = DestaqueMensal.objects.create(
            periodo=self.periodo, pilar=None, titulo="Geral", descricao="Geral do período."
        )
        do_pilar = DestaqueMensal.objects.create(
            periodo=self.periodo, pilar=self.pdi, titulo="Do PDI", descricao="Só PDI."
        )
        de_outro = DestaqueMensal.objects.create(
            periodo=self.periodo, pilar=self.outro, titulo="De outro", descricao="Só AT."
        )
        requisicao = _request("/", self.master)
        with mock.patch("apps.core.views.render") as mock_render:
            mock_render.return_value = HttpResponse()
            pilar_view(requisicao, pk=self.pdi.pk)
        destaques = list(_contexto_de_render(mock_render)["destaques"])
        self.assertIn(geral, destaques)
        self.assertIn(do_pilar, destaques)
        self.assertNotIn(de_outro, destaques)

    def test_pilar_destaques_evita_n1_ao_ler_pilar(self):
        from apps.core.views import pilar as pilar_view

        DestaqueMensal.objects.create(
            periodo=self.periodo, pilar=self.pdi, titulo="Com pilar 1", descricao="Um."
        )
        DestaqueMensal.objects.create(
            periodo=self.periodo, pilar=self.pdi, titulo="Com pilar 2", descricao="Dois."
        )
        requisicao = _request("/", self.master)
        with mock.patch("apps.core.views.render") as mock_render:
            mock_render.return_value = HttpResponse()
            pilar_view(requisicao, pk=self.pdi.pk)
        destaques_qs = _contexto_de_render(mock_render)["destaques"]
        with self.assertNumQueries(1):
            destaques = list(destaques_qs)
            for destaque in destaques:
                _ = destaque.pilar.nome if destaque.pilar_id else None


class DestaqueAdminPermissoesTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.site = admin.AdminSite()
        from apps.highlights.admin import DestaqueMensalAdmin

        self.model_admin = DestaqueMensalAdmin(DestaqueMensal, self.site)
        self.usuarios = {}
        for grupo in ("Master", "Admin", "PontoFocal", "Lideranca", "Auditor"):
            usuario = User.objects.create_user(username=f"usuario_{grupo.lower()}", password="x")
            adicionar_grupo(usuario, grupo)
            self.usuarios[grupo] = usuario

    def _requisicao(self, grupo):
        return _request("/admin/", self.usuarios[grupo])

    def test_master_pode_adicionar(self):
        self.assertTrue(self.model_admin.has_add_permission(self._requisicao("Master")))

    def test_auditor_nao_adiciona_mas_visualiza(self):
        self.assertFalse(self.model_admin.has_add_permission(self._requisicao("Auditor")))
        self.assertTrue(self.model_admin.has_view_permission(self._requisicao("Auditor")))

    def test_permissoes_de_escrita_so_para_gestao_e_focal(self):
        for grupo in ("Master", "Admin", "PontoFocal"):
            with self.subTest(grupo=grupo):
                req = self._requisicao(grupo)
                self.assertTrue(self.model_admin.has_add_permission(req))
                self.assertTrue(self.model_admin.has_change_permission(req))
                self.assertTrue(self.model_admin.has_delete_permission(req))
                self.assertTrue(self.model_admin.has_view_permission(req))
        for grupo in ("Lideranca", "Auditor"):
            with self.subTest(grupo=grupo):
                req = self._requisicao(grupo)
                self.assertFalse(self.model_admin.has_add_permission(req))
                self.assertFalse(self.model_admin.has_change_permission(req))
                self.assertFalse(self.model_admin.has_delete_permission(req))
                self.assertTrue(self.model_admin.has_view_permission(req))

    def test_superuser_sem_grupo_pode_adicionar_alterar_excluir_e_ver(self):
        superuser = User.objects.create_superuser(username="root", password="x", email="root@teste.com")
        fabrica = RequestFactory()
        requisicao = fabrica.get("/admin/")
        requisicao.user = superuser
        self.assertTrue(self.model_admin.has_add_permission(requisicao))
        self.assertTrue(self.model_admin.has_change_permission(requisicao))
        self.assertTrue(self.model_admin.has_delete_permission(requisicao))
        self.assertTrue(self.model_admin.has_view_permission(requisicao))
