"""Testes do app talentos — Banco de Talentos e Organograma (LOOP 5)."""
import tempfile
from datetime import date, timedelta
from unittest import mock

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.pillars.models import Pilar, UsuarioPilar

GIF_1PX = (
    b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00"
    b"\xff\xff\xff\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00"
    b"\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b"
)


def _request(path="/", usuario=None, dados=None):
    fabrica = RequestFactory()
    requisicao = fabrica.get(path, dados or {})
    requisicao.user = usuario
    return requisicao


def _contexto_de_render(mock_render):
    # render(requisicao, template, contexto)
    return mock_render.call_args[0][2]


class TalentosBaseTestes(TestCase):
    def setUp(self):
        from apps.talentos.models import Colaborador, Competencia

        self.pilar_at = Pilar.objects.create(codigo="AT", nome="Associação Tecnológica", ordem=1)
        self.pilar_ct = Pilar.objects.create(codigo="CT", nome="Capacitação Tecnológica", ordem=2)
        self.comp_eventos = Competencia.objects.create(nome="Gestão de Eventos")
        self.comp_dados = Competencia.objects.create(nome="Análise de Dados")
        self.emprestavel = Colaborador.objects.create(
            nome="Ana Emprestável", cargo="Analista de Eventos", pilar_principal=self.pilar_at
        )
        self.emprestavel.competencias.add(self.comp_eventos)
        self.outro = Colaborador.objects.create(
            nome="Bruno Fixo", cargo="Analista de Dados", pilar_principal=self.pilar_at
        )
        self.outro.competencias.add(self.comp_dados)
        self.usuario = User.objects.create_user(username="consulta_talentos", password="x")

    def _contexto(self, dados=None, usuario=None):
        from apps.talentos.views import OrganogramaView

        requisicao = _request("/talentos/organograma/", usuario or self.usuario, dados)
        with mock.patch("apps.talentos.views.render") as mock_render:
            mock_render.return_value = HttpResponse()
            OrganogramaView.as_view()(requisicao)
        return _contexto_de_render(mock_render)

    def _nomes(self, contexto):
        return [c.nome for c in contexto["colaboradores"]]


class OrganogramaFiltrosTestes(TalentosBaseTestes):
    def test_sem_filtro_retorna_todos(self):
        contexto = self._contexto()
        self.assertEqual(set(self._nomes(contexto)), {"Ana Emprestável", "Bruno Fixo"})
        self.assertEqual(contexto["pilar_selecionado"], "")
        self.assertEqual(contexto["competencia_selecionada"], "")

    def test_filtro_por_competencia_id_retorna_so_quem_tem(self):
        contexto = self._contexto({"competencia": str(self.comp_eventos.id)})
        self.assertEqual(self._nomes(contexto), ["Ana Emprestável"])
        self.assertEqual(contexto["competencia_selecionada"], str(self.comp_eventos.id))

    def test_filtro_por_pilar_codigo(self):
        contexto = self._contexto({"pilar": "CT"})
        self.assertEqual(self._nomes(contexto), [])
        contexto = self._contexto({"pilar": "AT"})
        self.assertEqual(set(self._nomes(contexto)), {"Ana Emprestável", "Bruno Fixo"})
        self.assertEqual(contexto["pilar_selecionado"], "AT")

    def test_filtros_combinados(self):
        from apps.talentos.models import Colaborador

        carla = Colaborador.objects.create(
            nome="Carla Eclética", cargo="Produtora", pilar_principal=self.pilar_ct
        )
        carla.competencias.add(self.comp_eventos)
        contexto = self._contexto({"pilar": "CT", "competencia": str(self.comp_eventos.id)})
        self.assertEqual(self._nomes(contexto), ["Carla Eclética"])

    def test_pilar_inexistente_retorna_lista_vazia(self):
        contexto = self._contexto({"pilar": "XX"})
        self.assertEqual(list(contexto["colaboradores"]), [])
        self.assertEqual(contexto["pilar_selecionado"], "XX")

    def test_competencia_id_invalido_ignora_o_filtro(self):
        contexto = self._contexto({"competencia": "999999"})
        self.assertEqual(set(self._nomes(contexto)), {"Ana Emprestável", "Bruno Fixo"})
        contexto = self._contexto({"competencia": "abc"})
        self.assertEqual(set(self._nomes(contexto)), {"Ana Emprestável", "Bruno Fixo"})

    def test_contexto_traz_pilares_ativos_e_competencias(self):
        Pilar.objects.create(codigo="XX", nome="Inativo", ordem=9, ativo=False)
        contexto = self._contexto()
        self.assertEqual(
            [p.codigo for p in contexto["pilares"]], ["AT", "CT"]
        )
        self.assertEqual(
            {c.nome for c in contexto["competencias"]},
            {"Gestão de Eventos", "Análise de Dados"},
        )


class OrganogramaVigenciaTestes(TalentosBaseTestes):
    def test_vigentes_exclui_encerrada_mas_mostra_ativa(self):
        from apps.talentos.models import Alocacao

        hoje = date.today()
        Alocacao.objects.create(
            colaborador=self.emprestavel,
            projeto_ou_area="Projeto Encerrado",
            horas_semanais=4,
            data_inicio=hoje - timedelta(days=60),
            data_fim=hoje - timedelta(days=30),
        )
        Alocacao.objects.create(
            colaborador=self.emprestavel,
            projeto_ou_area="Projeto Atual",
            horas_semanais=10,
            data_inicio=hoje - timedelta(days=10),
        )
        contexto = self._contexto()
        por_nome = {c.nome: c for c in contexto["colaboradores"]}
        vigentes = [a.projeto_ou_area for a in por_nome["Ana Emprestável"].alocacoes_vigentes]
        self.assertEqual(vigentes, ["Projeto Atual"])


class ColaboradorModeloTestes(TalentosBaseTestes):
    def test_str_colaborador(self):
        self.assertEqual(str(self.emprestavel), "Ana Emprestável (Analista de Eventos)")

    def test_str_competencia(self):
        self.assertEqual(str(self.comp_eventos), "Gestão de Eventos")

    def test_str_alocacao(self):
        from apps.talentos.models import Alocacao

        aloc = Alocacao(
            colaborador=self.emprestavel,
            projeto_ou_area="Feira Tech",
            horas_semanais=10,
            data_inicio=date(2026, 1, 5),
        )
        self.assertIn("Ana Emprestável", str(aloc))
        self.assertIn("Feira Tech", str(aloc))

    def test_alocacao_data_fim_anterior_levanta(self):
        from apps.talentos.models import Alocacao

        aloc = Alocacao(
            colaborador=self.emprestavel,
            projeto_ou_area="Feira Tech",
            horas_semanais=10,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 1, 1),
        )
        with self.assertRaises(ValidationError):
            aloc.full_clean()

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_upload_de_foto_aceito(self):
        from apps.talentos.models import Colaborador

        foto = SimpleUploadedFile("rosto.gif", GIF_1PX, content_type="image/gif")
        colab = Colaborador(
            nome="Com Foto", cargo="Designer", pilar_principal=self.pilar_at, foto=foto
        )
        colab.full_clean()
        colab.save()
        self.assertTrue(colab.foto.name.startswith("talentos/fotos/"))


def _post_request(path, usuario, dados):
    """RequestFactory POST com sessão/mensagens (views usam messages.success)."""
    from django.contrib.messages.middleware import MessageMiddleware
    from django.contrib.sessions.middleware import SessionMiddleware

    fabrica = RequestFactory()
    requisicao = fabrica.post(path, dados)
    requisicao.user = usuario
    SessionMiddleware(lambda r: HttpResponse()).process_request(requisicao)
    MessageMiddleware(lambda r: HttpResponse()).process_request(requisicao)
    return requisicao


class CadastroTalentosTestes(TestCase):
    """Task A — cadastro de colaboradores e alocações no site (TDD)."""

    def setUp(self):
        garantir_grupos()
        self.pilar_at = Pilar.objects.create(codigo="AT", nome="Associação Tecnológica", ordem=1)
        self.focal = adicionar_grupo(
            User.objects.create_user(username="focal_tal", password="x"), "PontoFocal"
        )
        UsuarioPilar.objects.create(usuario=self.focal, pilar=self.pilar_at)
        self.lideranca = adicionar_grupo(
            User.objects.create_user(username="lider_tal", password="x"), "Lideranca"
        )
        self.auditor = adicionar_grupo(
            User.objects.create_user(username="audit_tal", password="x"), "Auditor"
        )
        from apps.talentos.models import Colaborador, Competencia

        self.comp = Competencia.objects.create(nome="Gestão de Eventos")
        self.colaborador = Colaborador.objects.create(
            nome="Ana Emprestável", cargo="Analista de Eventos", pilar_principal=self.pilar_at
        )

    def test_colaborador_criar_get_permitido_200(self):
        from apps.talentos.views import colaborador_criar

        requisicao = _request("/talentos/colaboradores/novo/", self.focal)
        with mock.patch("apps.talentos.views.render") as mock_render:
            mock_render.return_value = HttpResponse()
            resposta = colaborador_criar(requisicao)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(mock_render.call_args[0][1], "talentos/colaborador_form.html")

    def test_colaborador_criar_get_negado_403(self):
        from apps.talentos.views import colaborador_criar

        for usuario in (self.lideranca, self.auditor):
            with self.subTest(usuario=usuario.username):
                requisicao = _request("/talentos/colaboradores/novo/", usuario)
                with (
                    mock.patch("apps.core.permissions.render") as mock_403,
                    mock.patch("apps.talentos.views.render") as mock_render,
                ):
                    mock_403.return_value = HttpResponse(status=403)
                    resposta = colaborador_criar(requisicao)
                self.assertEqual(resposta.status_code, 403)
                mock_render.assert_not_called()

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_colaborador_post_valido_cria_com_foto_redireciona_e_audita(self):
        from apps.audit.models import AuditLog
        from apps.talentos.models import Colaborador
        from apps.talentos.views import colaborador_criar

        foto = SimpleUploadedFile("rosto.gif", GIF_1PX, content_type="image/gif")
        dados = {
            "nome": "Carla Nova",
            "cargo": "Produtora",
            "pilar_principal": str(self.pilar_at.pk),
            "lattes_url": "",
            "competencias": [str(self.comp.pk)],
            "foto": foto,
        }
        requisicao = _post_request("/talentos/colaboradores/novo/", self.focal, dados)
        resposta = colaborador_criar(requisicao)
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.url, reverse("talentos:organograma"))
        colaboradora = Colaborador.objects.get(nome="Carla Nova")
        self.assertTrue(colaboradora.foto.name.startswith("talentos/fotos/"))
        self.assertEqual(list(colaboradora.competencias.all()), [self.comp])
        log = AuditLog.objects.get(acao="CRIAR_COLABORADOR")
        self.assertEqual(log.entidade, "Colaborador")
        self.assertEqual(log.registro_id, str(colaboradora.pk))

    def test_colaborador_editar_post_persiste_e_audita(self):
        from apps.audit.models import AuditLog
        from apps.talentos.views import colaborador_editar

        dados = {
            "nome": "Ana Emprestável",
            "cargo": "Coordenadora de Eventos",
            "pilar_principal": str(self.pilar_at.pk),
            "lattes_url": "",
            "competencias": [],
        }
        requisicao = _post_request(
            f"/talentos/colaboradores/{self.colaborador.pk}/editar/", self.focal, dados
        )
        resposta = colaborador_editar(requisicao, pk=self.colaborador.pk)
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.url, reverse("talentos:organograma"))
        self.colaborador.refresh_from_db()
        self.assertEqual(self.colaborador.cargo, "Coordenadora de Eventos")
        log = AuditLog.objects.get(acao="EDITAR_COLABORADOR")
        self.assertEqual(log.registro_id, str(self.colaborador.pk))

    def test_alocacao_criar_post_valido_cria_vinculada_e_audita(self):
        from apps.audit.models import AuditLog
        from apps.talentos.models import Alocacao
        from apps.talentos.views import alocacao_criar

        dados = {
            "projeto_ou_area": "Feira Tech",
            "horas_semanais": "20",
            "data_inicio": "2026-01-05",
            "data_fim": "",
        }
        requisicao = _post_request(
            f"/talentos/colaboradores/{self.colaborador.pk}/alocacoes/nova/",
            self.focal,
            dados,
        )
        resposta = alocacao_criar(requisicao, colaborador_pk=self.colaborador.pk)
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.url, reverse("talentos:organograma"))
        alocacao = Alocacao.objects.get(projeto_ou_area="Feira Tech")
        self.assertEqual(alocacao.colaborador.pk, self.colaborador.pk)
        log = AuditLog.objects.get(acao="CRIAR_ALOCACAO")
        self.assertEqual(log.registro_id, str(alocacao.pk))

    def test_alocacao_criar_post_data_fim_anterior_reexibe_sem_criar(self):
        from apps.talentos.models import Alocacao
        from apps.talentos.views import alocacao_criar

        dados = {
            "projeto_ou_area": "Feira Tech",
            "horas_semanais": "10",
            "data_inicio": "2026-02-01",
            "data_fim": "2026-01-01",
        }
        requisicao = _post_request(
            f"/talentos/colaboradores/{self.colaborador.pk}/alocacoes/nova/",
            self.focal,
            dados,
        )
        with mock.patch("apps.talentos.views.render") as mock_render:
            mock_render.return_value = HttpResponse()
            resposta = alocacao_criar(requisicao, colaborador_pk=self.colaborador.pk)
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Alocacao.objects.filter(projeto_ou_area="Feira Tech").exists())
        contexto = _contexto_de_render(mock_render)
        self.assertTrue(contexto["form"].errors)

    def test_alocacao_criar_get_negado_403(self):
        from apps.talentos.views import alocacao_criar

        requisicao = _request(
            f"/talentos/colaboradores/{self.colaborador.pk}/alocacoes/nova/",
            self.lideranca,
        )
        with mock.patch("apps.core.permissions.render") as mock_403:
            mock_403.return_value = HttpResponse(status=403)
            resposta = alocacao_criar(requisicao, colaborador_pk=self.colaborador.pk)
        self.assertEqual(resposta.status_code, 403)

    def test_alocacao_editar_post_persiste_e_audita(self):
        from apps.audit.models import AuditLog
        from apps.talentos.models import Alocacao
        from apps.talentos.views import alocacao_editar

        alocacao = Alocacao.objects.create(
            colaborador=self.colaborador,
            projeto_ou_area="Feira Tech",
            horas_semanais=10,
            data_inicio=date(2026, 1, 5),
        )
        dados = {
            "projeto_ou_area": "Feira Tech Ampliada",
            "horas_semanais": "30",
            "data_inicio": "2026-01-05",
            "data_fim": "",
        }
        requisicao = _post_request(
            f"/talentos/alocacoes/{alocacao.pk}/editar/", self.focal, dados
        )
        resposta = alocacao_editar(requisicao, pk=alocacao.pk)
        self.assertEqual(resposta.status_code, 302)
        alocacao.refresh_from_db()
        self.assertEqual(alocacao.projeto_ou_area, "Feira Tech Ampliada")
        self.assertEqual(alocacao.horas_semanais, 30)
        log = AuditLog.objects.get(acao="EDITAR_ALOCACAO")
        self.assertEqual(log.registro_id, str(alocacao.pk))

    def test_organograma_contexto_traz_pode_editar_talentos(self):
        from apps.talentos.views import OrganogramaView

        contexto_focal = self._contexto_organograma(self.focal)
        self.assertTrue(contexto_focal["pode_editar_talentos"])
        contexto_lider = self._contexto_organograma(self.lideranca)
        self.assertFalse(contexto_lider["pode_editar_talentos"])

    def _contexto_organograma(self, usuario):
        from apps.talentos.views import OrganogramaView

        requisicao = _request("/talentos/organograma/", usuario)
        with mock.patch("apps.talentos.views.render") as mock_render:
            mock_render.return_value = HttpResponse()
            OrganogramaView.as_view()(requisicao)
        return _contexto_de_render(mock_render)


class ColaboradorPilarRestritoTestes(TestCase):
    """PontoFocal só cadastra colaborador no seu pilar."""

    def setUp(self):
        garantir_grupos()
        self.pilar_at = Pilar.objects.create(codigo="AT", nome="Associação Tecnológica", ordem=1)
        self.pilar_pdi = Pilar.objects.create(codigo="PDI", nome="PDI / FCCT", ordem=2)
        self.focal_pdi = adicionar_grupo(
            User.objects.create_user(username="focal_pdi", password="x"), "PontoFocal"
        )
        UsuarioPilar.objects.create(usuario=self.focal_pdi, pilar=self.pilar_pdi)

    def test_focal_pdi_cria_com_pdi_ok(self):
        from apps.talentos.models import Colaborador
        from apps.talentos.views import colaborador_criar

        dados = {
            "nome": "Diana PDI",
            "cargo": "Pesquisadora",
            "pilar_principal": str(self.pilar_pdi.pk),
            "lattes_url": "",
            "competencias": [],
            "novas_competencias": "",
        }
        requisicao = _post_request("/talentos/colaboradores/novo/", self.focal_pdi, dados)
        resposta = colaborador_criar(requisicao)
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(
            Colaborador.objects.filter(nome="Diana PDI", pilar_principal=self.pilar_pdi).exists()
        )

    def test_focal_pdi_post_com_pilar_at_rejeitado(self):
        from apps.talentos.models import Colaborador
        from apps.talentos.views import colaborador_criar

        dados = {
            "nome": "Invasor AT",
            "cargo": "Analista",
            "pilar_principal": str(self.pilar_at.pk),
            "lattes_url": "",
            "competencias": [],
            "novas_competencias": "",
        }
        requisicao = _post_request("/talentos/colaboradores/novo/", self.focal_pdi, dados)
        with mock.patch("apps.talentos.views.render") as mock_render:
            mock_render.return_value = HttpResponse()
            resposta = colaborador_criar(requisicao)
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Colaborador.objects.filter(nome="Invasor AT").exists())
        contexto = _contexto_de_render(mock_render)
        self.assertFalse(contexto["form"].is_valid())
        self.assertIn("pilar_principal", contexto["form"].errors)


class NovasCompetenciasTestes(TestCase):
    """Competências livres sem duplicar (campo novas_competencias)."""

    def setUp(self):
        garantir_grupos()
        self.pilar_at = Pilar.objects.create(codigo="AT", nome="Associação Tecnológica", ordem=1)

    def _dados(self, novas):
        return {
            "nome": "Eva Livre",
            "cargo": "Analista",
            "pilar_principal": str(self.pilar_at.pk),
            "lattes_url": "",
            "competencias": [],
            "novas_competencias": novas,
        }

    def test_nome_existente_reutiliza_sem_duplicar(self):
        from apps.talentos.forms import ColaboradorForm
        from apps.talentos.models import Competencia

        Competencia.objects.create(nome="Python")
        total_antes = Competencia.objects.count()
        form = ColaboradorForm(self._dados("python"))
        self.assertTrue(form.is_valid(), form.errors)
        colaborador = form.save()
        self.assertEqual(Competencia.objects.count(), total_antes)
        self.assertEqual([c.nome for c in colaborador.competencias.all()], ["Python"])

    def test_nome_novo_cria_e_vincula(self):
        from apps.talentos.forms import ColaboradorForm
        from apps.talentos.models import Competencia

        form = ColaboradorForm(self._dados("Quantum ML"))
        self.assertTrue(form.is_valid(), form.errors)
        colaborador = form.save()
        self.assertTrue(Competencia.objects.filter(nome="Quantum ML").exists())
        self.assertEqual([c.nome for c in colaborador.competencias.all()], ["Quantum ML"])

    def test_string_vazia_nao_cria_nada(self):
        from apps.talentos.forms import ColaboradorForm
        from apps.talentos.models import Colaborador, Competencia

        for texto in ("", ", ,"):
            with self.subTest(texto=texto):
                total_antes = Competencia.objects.count()
                form = ColaboradorForm(self._dados(texto))
                self.assertTrue(form.is_valid(), form.errors)
                colaborador = form.save()
                self.assertEqual(Competencia.objects.count(), total_antes)
                self.assertEqual(list(colaborador.competencias.all()), [])
                Colaborador.objects.all().delete()
