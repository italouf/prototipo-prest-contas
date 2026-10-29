from datetime import date
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import transaction
from django.test import Client, TestCase
from django.urls import reverse

from apps.accountability import services as ingestao
from apps.accountability.models import Acompanhamento, CentroCompetencia, ProjetoFinanceiro
from apps.accountability.parsers.financeiro_geral import parse_financeiro_geral
from apps.accountability.tests.fixtures_financeiro import FINANCEIRO
from apps.audit.models import AuditLog
from apps.core.overview_period import resolver_periodo
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.pillars.models import Pilar, UsuarioPilar
from apps.planning.views import contexto_pilar, _html_standalone

from .models import BookPrograma, MaterialProjeto, Projeto
from .services import salvar_book


class EntregaveisTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        garantir_grupos()
        cls.pilares = {c: Pilar.objects.get_or_create(codigo=c, defaults={"nome": c})[0] for c in ("PDI", "FORMACAO", "STARTUPS", "INFRA", "AT", "OUTRASFONTES")}
        cls.master = adicionar_grupo(get_user_model().objects.create_user(username="entregaveis-master"), "Master")
        cls.auditor = adicionar_grupo(get_user_model().objects.create_user(username="entregaveis-auditor"), "Auditor")
        cls.focal = adicionar_grupo(get_user_model().objects.create_user(username="entregaveis-focal"), "PontoFocal")
        UsuarioPilar.objects.create(usuario=cls.focal, pilar=cls.pilares["PDI"])
        ingestao.ingestar("FINANCEIRO_GERAL", FINANCEIRO, "Entregáveis", "3T/2026", cls.master)
        cls.acomp = Acompanhamento.objects.get(centro__nome="Entregáveis")
        cls.projeto = Projeto.objects.filter(centro=cls.acomp.centro, pilar=cls.pilares["PDI"]).first()

    def url(self, nome, *args, pilar="PDI", acomp=None, **params):
        from urllib.parse import urlencode
        return reverse("projects:" + nome, args=[self.pilares[pilar].pk, *args]) + "?" + urlencode({"acompanhamento": (acomp or self.acomp).pk, **params})

    def contexto(self, pilar="PDI", **params):
        return contexto_pilar(self.pilares[pilar], "todos", "fis", self.master, self.acomp, resolver_periodo(params))

    def material(self, **kwargs):
        return MaterialProjeto.objects.create(projeto=self.projeto, titulo="Artigo do projeto", tipo="ARTIGO", url="https://example.org/artigo", **kwargs)

    def test_reimportacao_e_remocao_preservam_identidade_materiais_e_valores(self):
        material = self.material()
        ids = set(Projeto.objects.values_list("pk", flat=True))
        campos = [f.name for f in ProjetoFinanceiro._meta.fields if f.name not in ("id", "projeto")]
        valores = list(ProjetoFinanceiro.objects.order_by("origem", "nome").values_list(*campos))
        ingestao.ingestar("FINANCEIRO_GERAL", FINANCEIRO, "Entregáveis", "3T/2026", self.master)
        self.assertEqual(set(Projeto.objects.values_list("pk", flat=True)), ids)
        self.assertEqual(list(ProjetoFinanceiro.objects.order_by("origem", "nome").values_list(*campos)), valores)
        self.assertFalse(ProjetoFinanceiro.objects.filter(projeto__isnull=True).exists())
        payload = parse_financeiro_geral(FINANCEIRO)
        nome = self.projeto.referencias_importacao.first().nome_origem
        payload["projetos"] = [p for p in payload["projetos"] if p["nome"] != nome]
        with transaction.atomic():
            ingestao._gravar_fatos(self.acomp, "FINANCEIRO_GERAL", payload, self.pilares)
        self.assertTrue(Projeto.objects.filter(pk=self.projeto.pk).exists())
        self.assertTrue(MaterialProjeto.objects.filter(pk=material.pk, projeto=self.projeto).exists())

    def test_falha_de_importacao_reverte_catalogo_e_snapshots_juntos(self):
        payload = parse_financeiro_geral(FINANCEIRO)
        payload["projetos"][0]["nome"] = "Projeto transitório que deve ser revertido"
        ids = list(ProjetoFinanceiro.objects.order_by("pk").values_list("pk", flat=True))
        with mock.patch.dict(ingestao._PARSERS, {"FINANCEIRO_GERAL": lambda arquivo: payload}):
            with mock.patch.object(ingestao, "_mensagem_sucesso", side_effect=RuntimeError("Falha após gravar")):
                with self.assertRaises(ingestao.IngestaoError):
                    ingestao.ingestar("FINANCEIRO_GERAL", FINANCEIRO, "Entregáveis", "3T/2026", self.master)
        self.assertFalse(Projeto.objects.filter(nome=payload["projetos"][0]["nome"]).exists())
        self.assertEqual(Projeto.objects.count(), 33)
        self.assertEqual(list(ProjetoFinanceiro.objects.order_by("pk").values_list("pk", flat=True)), ids)

    def test_sincronizacao_de_snapshots_legados_e_idempotente(self):
        registro = ProjetoFinanceiro.objects.filter(projeto=self.projeto).first()
        ProjetoFinanceiro.objects.filter(pk=registro.pk).update(projeto=None)
        for _ in range(2):
            call_command("sincronizar_catalogo_projetos", stdout=StringIO())
        registro.refresh_from_db()
        self.assertEqual(registro.projeto_id, self.projeto.pk)
        self.assertEqual(Projeto.objects.count(), 33)

    def test_projeto_manual_e_renomeacao_nao_perdem_referencia(self):
        self.client.force_login(self.master)
        nome_origem = self.projeto.nome
        resposta = self.client.post(self.url("editar", self.projeto.pk), {"nome": "Nome de exibição revisado", "codigo_embrapii": ""})
        self.assertEqual(resposta.status_code, 302)
        ingestao.ingestar("FINANCEIRO_GERAL", FINANCEIRO, "Entregáveis", "3T/2026", self.master)
        self.assertEqual(ProjetoFinanceiro.objects.get(nome=nome_origem).projeto_id, self.projeto.pk)
        self.assertEqual(Projeto.objects.count(), 33)
        self.client.post(self.url("novo"), {"nome": "Projeto físico novo", "codigo_embrapii": ""})
        manual = Projeto.objects.get(nome="Projeto físico novo")
        payload = parse_financeiro_geral(FINANCEIRO)
        novo = dict(payload["projetos"][0], nome=manual.nome)
        payload["projetos"].append(novo)
        with transaction.atomic():
            ingestao._gravar_fatos(self.acomp, "FINANCEIRO_GERAL", payload, self.pilares)
        self.assertEqual(ProjetoFinanceiro.objects.get(nome=manual.nome).projeto_id, manual.pk)

    def test_book_herdado_tres_pilares_projeto_novo_e_isolamento_centro(self):
        self.material()
        book = BookPrograma(centro=self.acomp.centro, titulo="Book geral", url="https://example.org/book")
        salvar_book(book, self.master)
        for pilar in ("PDI", "FORMACAO", "STARTUPS"):
            quadro = self.contexto(pilar)["quadro_entregaveis"]
            self.assertEqual(quadro["book"].pk, book.pk)
            self.assertEqual(len(quadro["projetos"]), {"PDI": 18, "FORMACAO": 8, "STARTUPS": 7}[pilar])
        novo = Projeto.objects.create(centro=self.acomp.centro, pilar=self.pilares["FORMACAO"], nome="Novo FCRH")
        self.assertIn(novo, self.contexto("FORMACAO")["quadro_entregaveis"]["projetos"])
        outro = CentroCompetencia.objects.create(codigo="outro", nome="Outro centro")
        acomp = Acompanhamento.objects.create(centro=outro, periodo_referencia="3T/2026")
        contexto = contexto_pilar(self.pilares["PDI"], "todos", "fis", self.master, acomp)
        self.assertIsNone(contexto["quadro_entregaveis"]["book"])
        self.assertEqual(list(contexto["quadro_entregaveis"]["projetos"]), [])

    def test_filtro_datas_nao_altera_carteira_nem_indicadores(self):
        self.material(data_publicacao=date(2024, 1, 1))
        completo = self.contexto()
        filtrado = self.contexto(mes_inicial="2025-01", mes_final="2025-12")
        self.assertEqual(list(completo["quadro_entregaveis"]["projetos"]), list(filtrado["quadro_entregaveis"]["projetos"]))
        self.assertEqual(MaterialProjeto.objects.count(), 1)
        self.client.force_login(self.master)
        resposta = self.client.get(reverse("core:pilar", args=[self.pilares["PDI"].pk]), {"base": "fis", "mes_inicial": "2025-01", "mes_final": "2025-12"})
        self.assertContains(resposta, "Artigo do projeto")
        self.assertContains(resposta, "Carteira completa")
        financeiro = self.client.get(reverse("core:pilar", args=[self.pilares["PDI"].pk]), {"base": "fin"})
        self.assertNotContains(financeiro, 'data-testid="entregaveis-accordion"')

    def test_permissoes_views_e_csv(self):
        self.client.force_login(self.focal)
        self.assertEqual(self.client.get(self.url("novo")).status_code, 200)
        self.assertEqual(self.client.post(self.url("novo"), {"nome": "Meu projeto"}).status_code, 302)
        self.assertEqual(self.client.get(self.url("book")).status_code, 403)
        self.assertEqual(self.client.get(self.url("novo", pilar="FORMACAO")).status_code, 403)
        self.assertEqual(self.client.get(self.url("csv", pilar="FORMACAO")).status_code, 403)
        self.client.force_login(self.auditor)
        self.assertEqual(self.client.get(self.url("csv")).status_code, 200)
        self.assertEqual(self.client.post(self.url("novo"), {"nome": "Proibido"}).status_code, 403)
        self.assertEqual(self.client.get(self.url("material_novo", self.projeto.pk)).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url("csv")).status_code, 302)

    def test_validacao_links_edicao_auditoria_e_preservacao_filtros(self):
        self.client.force_login(self.master)
        destino = self.url("material_novo", self.projeto.pk, mes_inicial="2025-01", mes_final="2025-12")
        for invalido in ("javascript:alert(1)", "ftp://example.org/documento", "texto"):
            resposta = self.client.post(destino, {"titulo": "Artigo", "tipo": "ARTIGO", "url": invalido})
            self.assertEqual(resposta.status_code, 200)
            self.assertFalse(MaterialProjeto.objects.exists())
        resposta = self.client.post(destino, {"titulo": "Artigo <script>", "tipo": "ARTIGO", "url": "https://example.org/artigo"})
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("mes_inicial=2025-01", resposta.url)
        self.assertIn("base=fis", resposta.url)
        material = MaterialProjeto.objects.get()
        self.assertIsNone(material.data_publicacao)
        self.assertTrue(AuditLog.objects.filter(acao="CADASTRAR_MATERIAL", registro_id=str(material.pk)).exists())
        html = _html_standalone("todos", "fis", self.master, pilar=self.pilares["PDI"], acompanhamento=self.acomp)
        self.assertIn("Artigo &lt;script&gt;", html)
        self.assertNotIn("Editar material", html)
        self.assertNotIn("Novo projeto", html)
        self.assertIn("https://example.org/artigo", self.client.get(self.url("csv")).content.decode())

    def test_book_substituicao_arquivamento_e_reativacao_com_historico(self):
        self.client.force_login(self.master)
        for titulo in ("Primeiro", "Segundo"):
            resposta = self.client.post(self.url("book"), {"titulo": titulo, "url": "https://example.org/" + titulo})
            self.assertEqual(resposta.status_code, 302)
        self.assertEqual(BookPrograma.objects.count(), 2)
        self.assertEqual(BookPrograma.objects.get(ativo=True).titulo, "Segundo")
        primeiro = BookPrograma.objects.get(titulo="Primeiro")
        self.client.post(self.url("book_situacao", primeiro.pk), {"acao": "reativar"})
        self.assertEqual(BookPrograma.objects.get(ativo=True).pk, primeiro.pk)
        self.client.post(self.url("book_situacao", primeiro.pk), {"acao": "arquivar"})
        self.assertFalse(BookPrograma.objects.filter(ativo=True).exists())
        self.assertEqual(BookPrograma.objects.count(), 2)

    def test_arquivar_projeto_nao_remove_materiais_reativar_restaura(self):
        material = self.material()
        self.client.force_login(self.master)
        for acao, visivel in (("arquivar", False), ("reativar", True)):
            self.assertEqual(self.client.post(self.url("projeto_situacao", self.projeto.pk), {"acao": acao}).status_code, 302)
            self.assertEqual(self.projeto in self.contexto()["quadro_entregaveis"]["projetos"], visivel)
            self.assertTrue(MaterialProjeto.objects.filter(pk=material.pk).exists())

    def test_associacao_de_origem_nao_transfere_materiais_e_rejeita_outro_pilar(self):
        material = self.material()
        destino = Projeto.objects.create(centro=self.acomp.centro, pilar=self.pilares["PDI"], nome="Cadastro físico correto")
        referencia = self.projeto.referencias_importacao.first()
        self.client.force_login(self.master)
        outro_pilar = Projeto.objects.filter(pilar=self.pilares["FORMACAO"]).first()
        self.assertEqual(self.client.post(self.url("referencia", referencia.pk), {"projeto": outro_pilar.pk}).status_code, 200)
        self.assertEqual(self.client.post(self.url("referencia", referencia.pk), {"projeto": destino.pk}).status_code, 302)
        self.assertEqual(ProjetoFinanceiro.objects.get(nome=referencia.nome_origem).projeto_id, destino.pk)
        material.refresh_from_db()
        self.assertEqual(material.projeto_id, self.projeto.pk)
        ingestao.ingestar("FINANCEIRO_GERAL", FINANCEIRO, "Entregáveis", "3T/2026", self.master)
        self.assertEqual(ProjetoFinanceiro.objects.get(nome=referencia.nome_origem).projeto_id, destino.pk)

    def test_acesso_a_registro_de_outro_centro_e_csrf(self):
        centro = CentroCompetencia.objects.create(codigo="isolado", nome="Centro isolado")
        outro = Projeto.objects.create(centro=centro, pilar=self.pilares["PDI"], nome="Isolado")
        self.client.force_login(self.master)
        self.assertEqual(self.client.get(self.url("editar", outro.pk)).status_code, 404)
        self.assertEqual(self.client.get(self.url("projeto_situacao", self.projeto.pk)).status_code, 405)
        self.assertEqual(self.client.get(reverse("projects:csv", args=[self.pilares["PDI"].pk]), {"acompanhamento": "inválido"}).status_code, 404)
        protegido = Client(enforce_csrf_checks=True)
        protegido.force_login(self.master)
        self.assertEqual(protegido.post(self.url("projeto_situacao", self.projeto.pk), {"acao": "arquivar"}).status_code, 403)
