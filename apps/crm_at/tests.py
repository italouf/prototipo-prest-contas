"""Testes do app crm_at — CRM e Funil da Associação Tecnológica (LOOP 4)."""
from decimal import Decimal
from unittest import mock

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

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
