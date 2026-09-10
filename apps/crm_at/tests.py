"""Testes do app crm_at — CRM e Funil da Associação Tecnológica (LOOP 4)."""
from decimal import Decimal
from unittest import mock

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.crm_at.models import Empresa, Oportunidade
from apps.pillars.models import Pilar, UsuarioPilar


def _request(path="/", usuario=None):
    fabrica = RequestFactory()
    requisicao = fabrica.get(path)
    requisicao.user = usuario
    return requisicao


def _contexto_de_render(mock_render):
    # render(requisicao, template, contexto)
    return mock_render.call_args[0][2]


def _empresa(nome, cnpj, status="PROSPECT"):
    empresa = Empresa(nome=nome, cnpj=cnpj, status=status)
    empresa.full_clean()
    empresa.save()
    return empresa


class EmpresaModeloTestes(TestCase):
    def test_str_retorna_nome(self):
        empresa = Empresa(nome="Acme S.A.", cnpj="12.345.678/0001-95")
        self.assertEqual(str(empresa), "Acme S.A.")

    def test_cnpj_invalido_levanta_validation_error(self):
        empresa = Empresa(nome="Invalida Ltda", cnpj="123")
        with self.assertRaises(ValidationError):
            empresa.full_clean()

    def test_cnpj_com_mascara_valida_passa(self):
        empresa = Empresa(nome="Valida Ltda", cnpj="12.345.678/0001-95")
        empresa.full_clean()  # não deve levantar


class FunilATViewTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.pilar_at = Pilar.objects.create(codigo="AT", nome="Associação Tecnológica", ordem=1)
        self.usuario = adicionar_grupo(User.objects.create_user(username="focal_at", password="x"), "PontoFocal")
        UsuarioPilar.objects.create(usuario=self.usuario, pilar=self.pilar_at)
        self.emp_a = _empresa("Alfa Ltda", "11.111.111/0001-11")
        self.emp_b = _empresa("Beta S.A.", "22.222.222/0001-22")
        self.emp_c = _empresa("Gama ME", "33.333.333/0001-33")
        Oportunidade.objects.create(empresa=self.emp_a, valor_previsto=Decimal("1000.00"), fase="PROSPECCAO")
        Oportunidade.objects.create(empresa=self.emp_b, valor_previsto=Decimal("2000.00"), fase="NEGOCIACAO")
        Oportunidade.objects.create(empresa=self.emp_c, valor_previsto=Decimal("3000.00"), fase="FECHAMENTO")

    def _contexto(self, usuario=None):
        from apps.crm_at.views import FunilATView

        requisicao = _request("/crm-at/funil/", usuario or self.usuario)
        with mock.patch("apps.crm_at.views.render") as mock_render:
            mock_render.return_value = HttpResponse()
            FunilATView.as_view()(requisicao)
        return _contexto_de_render(mock_render)

    def test_oportunidades_aparecem_nos_grupos_certos(self):
        contexto = self._contexto()
        grupos = {g["fase"]: g for g in contexto["grupos"]}
        self.assertEqual(len(contexto["grupos"]), 7)
        self.assertEqual([o.empresa.nome for o in grupos["PROSPECCAO"]["oportunidades"]], ["Alfa Ltda"])
        self.assertEqual([o.empresa.nome for o in grupos["NEGOCIACAO"]["oportunidades"]], ["Beta S.A."])
        self.assertEqual([o.empresa.nome for o in grupos["FECHAMENTO"]["oportunidades"]], ["Gama ME"])
        self.assertEqual(grupos["PROSPECCAO"]["total"], Decimal("1000.00"))

    def test_pipeline_open_exclui_fechamento_e_perdido(self):
        Oportunidade.objects.create(
            empresa=self.emp_a, valor_previsto=Decimal("500.00"), fase="PERDIDO"
        )
        contexto = self._contexto()
        self.assertEqual(contexto["pipeline_open"], Decimal("3000.00"))

    def test_renovacoes_contam_e_somam_certo(self):
        Oportunidade.objects.create(
            empresa=self.emp_a, valor_previsto=Decimal("700.00"),
            fase="RENOVACAO", tipo="RENOVACAO",
        )
        Oportunidade.objects.create(
            empresa=self.emp_b, valor_previsto=Decimal("900.00"),
            fase="FECHAMENTO", tipo="RENOVACAO",
        )
        contexto = self._contexto()
        self.assertEqual(contexto["renovacoes_qtd"], 1)
        self.assertEqual(contexto["renovacoes_total"], Decimal("700.00"))

    def test_usuario_sem_vinculo_at_recebe_403(self):
        from apps.crm_at.views import FunilATView

        sem_acesso = adicionar_grupo(User.objects.create_user(username="sem_at", password="x"), "PontoFocal")
        requisicao = _request("/crm-at/funil/", sem_acesso)
        with mock.patch("apps.core.permissions.render") as mock_render:
            mock_render.return_value = HttpResponse(status=403)
            resposta = FunilATView.as_view()(requisicao)
        mock_render.assert_called_once()
        self.assertEqual(resposta.status_code, 403)


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


class CadastroCRMTestes(TestCase):
    """Task A — cadastro de oportunidades e empresas no site (TDD)."""

    def setUp(self):
        garantir_grupos()
        self.pilar_at = Pilar.objects.create(codigo="AT", nome="Associação Tecnológica", ordem=1)
        self.focal_at = adicionar_grupo(
            User.objects.create_user(username="focal_cad", password="x"), "PontoFocal"
        )
        UsuarioPilar.objects.create(usuario=self.focal_at, pilar=self.pilar_at)
        self.focal_sem_at = adicionar_grupo(
            User.objects.create_user(username="focal_outro", password="x"), "PontoFocal"
        )
        self.lideranca = adicionar_grupo(
            User.objects.create_user(username="lider_cad", password="x"), "Lideranca"
        )
        self.auditor = adicionar_grupo(
            User.objects.create_user(username="audit_cad", password="x"), "Auditor"
        )
        self.empresa = _empresa("Acme S.A.", "12.345.678/0001-95")

    def test_criar_get_permitido_200(self):
        from apps.crm_at.views import oportunidade_criar

        requisicao = _request("/crm-at/oportunidades/nova/", self.focal_at)
        with mock.patch("apps.crm_at.views.render") as mock_render:
            mock_render.return_value = HttpResponse()
            resposta = oportunidade_criar(requisicao)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(mock_render.call_args[0][1], "crm_at/oportunidade_form.html")

    def test_criar_get_negado_403(self):
        from apps.crm_at.views import oportunidade_criar

        for usuario in (self.lideranca, self.auditor, self.focal_sem_at):
            with self.subTest(usuario=usuario.username):
                requisicao = _request("/crm-at/oportunidades/nova/", usuario)
                with (
                    mock.patch("apps.core.permissions.render") as mock_403,
                    mock.patch("apps.crm_at.views.render") as mock_render,
                ):
                    mock_403.return_value = HttpResponse(status=403)
                    resposta = oportunidade_criar(requisicao)
                self.assertEqual(resposta.status_code, 403)
                mock_render.assert_not_called()

    def test_criar_post_valido_cria_redireciona_e_audita(self):
        from apps.audit.models import AuditLog
        from apps.crm_at.views import oportunidade_criar

        dados = {
            "empresa": str(self.empresa.pk),
            "valor_previsto": "1500.00",
            "fase": "QUALIFICACAO",
            "tipo": "NOVO_CNPJ",
            "observacao": "Primeiro contato.",
        }
        requisicao = _post_request("/crm-at/oportunidades/nova/", self.focal_at, dados)
        resposta = oportunidade_criar(requisicao)
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.url, reverse("crm_at:funil"))
        oportunidade = Oportunidade.objects.get(empresa=self.empresa)
        self.assertEqual(oportunidade.fase, "QUALIFICACAO")
        log = AuditLog.objects.get(acao="CRIAR_OPORTUNIDADE")
        self.assertEqual(log.entidade, "Oportunidade")
        self.assertEqual(log.registro_id, str(oportunidade.pk))
        self.assertEqual(log.campo, "fase")
        self.assertEqual(log.valor_novo, "QUALIFICACAO")

    def test_empresa_post_cnpj_curto_reexibe_sem_criar(self):
        from apps.crm_at.views import empresa_criar

        dados = {"nome": "Curta Ltda", "cnpj": "123", "status": "PROSPECT"}
        requisicao = _post_request("/crm-at/empresas/nova/", self.focal_at, dados)
        with mock.patch("apps.crm_at.views.render") as mock_render:
            mock_render.return_value = HttpResponse()
            resposta = empresa_criar(requisicao)
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Empresa.objects.filter(nome="Curta Ltda").exists())
        contexto = _contexto_de_render(mock_render)
        self.assertIn("cnpj", contexto["form"].errors)

    def test_empresa_criar_get_negado_403(self):
        from apps.crm_at.views import empresa_criar

        requisicao = _request("/crm-at/empresas/nova/", self.lideranca)
        with mock.patch("apps.core.permissions.render") as mock_403:
            mock_403.return_value = HttpResponse(status=403)
            resposta = empresa_criar(requisicao)
        self.assertEqual(resposta.status_code, 403)

    def test_empresa_criar_respeita_next_interno(self):
        from apps.crm_at.views import empresa_criar

        dados = {"nome": "Nova Ltda", "cnpj": "44.444.444/0001-44", "status": "PROSPECT"}
        fabrica = RequestFactory()
        requisicao = fabrica.post("/crm-at/empresas/nova/?next=/crm-at/oportunidades/nova/", dados)
        requisicao.user = self.focal_at
        from django.contrib.messages.middleware import MessageMiddleware
        from django.contrib.sessions.middleware import SessionMiddleware

        SessionMiddleware(lambda r: HttpResponse()).process_request(requisicao)
        MessageMiddleware(lambda r: HttpResponse()).process_request(requisicao)
        resposta = empresa_criar(requisicao)
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.url, "/crm-at/oportunidades/nova/")
        self.assertTrue(Empresa.objects.filter(nome="Nova Ltda").exists())

    def test_empresa_criar_ignora_next_externo(self):
        from apps.crm_at.views import empresa_criar

        dados = {"nome": "Outra Ltda", "cnpj": "55.555.555/0001-55", "status": "PROSPECT"}
        fabrica = RequestFactory()
        requisicao = fabrica.post(
            "/crm-at/empresas/nova/?next=https://externo.exemplo/phish", dados
        )
        requisicao.user = self.focal_at
        from django.contrib.messages.middleware import MessageMiddleware
        from django.contrib.sessions.middleware import SessionMiddleware

        SessionMiddleware(lambda r: HttpResponse()).process_request(requisicao)
        MessageMiddleware(lambda r: HttpResponse()).process_request(requisicao)
        resposta = empresa_criar(requisicao)
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.url, reverse("crm_at:funil"))

    def test_editar_post_move_fase_persiste_e_audita(self):
        from apps.audit.models import AuditLog
        from apps.crm_at.views import oportunidade_editar

        oportunidade = Oportunidade.objects.create(
            empresa=self.empresa, valor_previsto=Decimal("1000.00"), fase="PROSPECCAO"
        )
        dados = {
            "empresa": str(self.empresa.pk),
            "valor_previsto": "1000.00",
            "fase": "NEGOCIACAO",
            "tipo": "NOVO_CNPJ",
            "observacao": "",
        }
        requisicao = _post_request(
            f"/crm-at/oportunidades/{oportunidade.pk}/editar/", self.focal_at, dados
        )
        resposta = oportunidade_editar(requisicao, pk=oportunidade.pk)
        self.assertEqual(resposta.status_code, 302)
        oportunidade.refresh_from_db()
        self.assertEqual(oportunidade.fase, "NEGOCIACAO")
        log = AuditLog.objects.get(acao="EDITAR_OPORTUNIDADE")
        self.assertEqual(log.valor_anterior, "PROSPECCAO")
        self.assertEqual(log.valor_novo, "NEGOCIACAO")

    def test_editar_get_negado_403(self):
        from apps.crm_at.views import oportunidade_editar

        oportunidade = Oportunidade.objects.create(
            empresa=self.empresa, valor_previsto=Decimal("1000.00"), fase="PROSPECCAO"
        )
        requisicao = _request(
            f"/crm-at/oportunidades/{oportunidade.pk}/editar/", self.lideranca
        )
        with mock.patch("apps.core.permissions.render") as mock_403:
            mock_403.return_value = HttpResponse(status=403)
            resposta = oportunidade_editar(requisicao, pk=oportunidade.pk)
        self.assertEqual(resposta.status_code, 403)

    def test_funil_contexto_traz_pode_editar_crm(self):
        from apps.crm_at.views import FunilATView

        contexto_focal = self._contexto_funil(self.focal_at)
        self.assertTrue(contexto_focal["pode_editar_crm"])
        contexto_lider = self._contexto_funil(self.lideranca)
        self.assertFalse(contexto_lider["pode_editar_crm"])

    def _contexto_funil(self, usuario):
        from apps.crm_at.views import FunilATView

        requisicao = _request("/crm-at/funil/", usuario)
        with mock.patch("apps.crm_at.views.render") as mock_render:
            mock_render.return_value = HttpResponse()
            FunilATView.as_view()(requisicao)
        return _contexto_de_render(mock_render)
