"""Testes do app talentos — Banco de Talentos e Organograma (LOOP 5)."""
import tempfile
from datetime import date, timedelta
from unittest import mock

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from apps.accounts.models import User
from apps.pillars.models import Pilar

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
