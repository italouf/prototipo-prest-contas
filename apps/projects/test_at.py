from datetime import date
from io import StringIO
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from apps.accountability.models import Acompanhamento, CentroCompetencia, KpiAcompanhamento
from apps.accountability.services import ingestar
from apps.accountability.tests.fixtures_financeiro import FINANCEIRO
from apps.audit.models import AuditLog
from apps.core.overview_period import resolver_periodo
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.pillars.models import Pilar, UsuarioPilar
from apps.planning.views import contexto_pilar, _html_standalone

from .at_catalog import PRODUTOS_AT, TIPOS_MATERIAL_AT
from .at_services import inicializar_produtos_at
from .models import BookPrograma, MaterialProdutoAT, ProdutoAT, TIPOS_MATERIAL


class EntregaveisATTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        garantir_grupos()
        cls.pilares = {c: Pilar.objects.get_or_create(codigo=c, defaults={"nome": c})[0] for c in ("AT", "OUTRASFONTES", "PDI", "FORMACAO", "STARTUPS", "INFRA")}
        cls.usuarios = {}
        for nome, papel, vinculo in (("master", "Master", None), ("admin", "Admin", None), ("focal", "PontoFocal", "AT"), ("outras", "PontoFocal", "OUTRASFONTES"), ("auditor", "Auditor", None), ("lider", "Lideranca", None)):
            user = adicionar_grupo(get_user_model().objects.create_user(username="at-produto-" + nome), papel)
            cls.usuarios[nome] = user
            if vinculo:
                UsuarioPilar.objects.create(usuario=user, pilar=cls.pilares[vinculo])
        cls.centro = CentroCompetencia.objects.create(codigo="at-entregaveis", nome="AT entregáveis")
        cls.acomp = Acompanhamento.objects.create(centro=cls.centro, periodo_referencia="3T/2026")
        cls.produto = ProdutoAT.objects.get(centro=cls.centro, codigo_padrao="WHITE_PAPER")

    def url(self, nome, *args, acomp=None, **params):
        return reverse("deliverables_at:" + nome, args=args) + "?" + urlencode({"acompanhamento": (acomp or self.acomp).pk, **params})

    def painel(self, usuario="master", base="fis", **params):
        return contexto_pilar(self.pilares["AT"], "todos", base, self.usuarios[usuario], self.acomp, resolver_periodo(params))

    def material(self, **campos):
        return MaterialProdutoAT.objects.create(produto=self.produto, titulo="Apresentação inicial", tipo="APRESENTACAO", url="https://example.org/apresentacao", **campos)

    def test_nove_produtos_ordem_e_inicializacao_preserva_renomeado_arquivado(self):
        iniciais = list(ProdutoAT.objects.filter(centro=self.centro))
        self.assertEqual([p.nome for p in iniciais], [nome for _, nome in PRODUTOS_AT])
        self.assertEqual([p.nome for p in self.painel()["quadro_entregaveis_at"]["produtos"]], [nome for _, nome in PRODUTOS_AT])
        ids = [p.pk for p in iniciais]
        self.produto.nome = "Nome revisado"
        self.produto.ordem = 25
        self.produto.ativo = False
        self.produto.save()
        inicializar_produtos_at(self.centro)
        call_command("sincronizar_produtos_at", stdout=StringIO())
        self.produto.refresh_from_db()
        self.assertEqual((self.produto.nome, self.produto.ordem, self.produto.ativo), ("Nome revisado", 25, False))
        self.assertEqual(set(ProdutoAT.objects.filter(centro=self.centro).values_list("pk", flat=True)), set(ids))
        outro = CentroCompetencia.objects.create(codigo="at-centro-novo", nome="Novo centro")
        self.assertEqual(ProdutoAT.objects.filter(centro=outro).count(), 9)

    def test_quadro_fisico_sem_book_e_sem_acesso_so_outras_fontes(self):
        BookPrograma.objects.create(centro=self.centro, titulo="Book geral dos projetos", url="https://example.org/book")
        self.assertIn("quadro_entregaveis_at", self.painel())
        self.assertNotIn("quadro_entregaveis_at", self.painel("outras"))
        self.assertNotIn("quadro_entregaveis_at", self.painel(base="fin"))
        self.assertFalse(self.painel("auditor")["pode_editar_produtos_at"])
        self.client.force_login(self.usuarios["master"])
        resposta = self.client.get(reverse("core:pilar", args=[self.pilares["AT"].pk]), {"base": "fis", "acompanhamento": self.acomp.pk})
        self.assertContains(resposta, 'data-testid="entregaveis-at-accordion"')
        self.assertContains(resposta, "Propriedade Intelectual (PI)")
        self.assertNotContains(resposta, "Book geral")

    def test_permissoes_backend_csv_e_mutacoes(self):
        for usuario in ("master", "admin", "focal"):
            self.client.force_login(self.usuarios[usuario])
            self.assertEqual(self.client.get(self.url("novo")).status_code, 200)
            self.assertEqual(self.client.get(self.url("csv")).status_code, 200)
        for usuario in ("auditor", "lider"):
            self.client.force_login(self.usuarios[usuario])
            self.assertEqual(self.client.get(self.url("csv")).status_code, 200)
            self.assertEqual(self.client.get(self.url("novo")).status_code, 403)
            self.assertEqual(self.client.post(self.url("produto_situacao", self.produto.pk), {"acao": "arquivar"}).status_code, 403)
        self.client.force_login(self.usuarios["outras"])
        self.assertEqual(self.client.post(self.url("material_novo", self.produto.pk), {"titulo": "Proibido", "tipo": "DOCUMENTO", "url": "https://example.org/teste"}).status_code, 403)
        for nome, args in (("novo", []), ("csv", []), ("gerenciar", []), ("editar", [self.produto.pk]), ("material_novo", [self.produto.pk])):
            self.assertEqual(self.client.get(self.url(nome, *args)).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url("csv")).status_code, 302)

    def test_produto_criacao_ordem_renomeacao_e_duplicidade(self):
        self.client.force_login(self.usuarios["focal"])
        resposta = self.client.get(self.url("novo"))
        self.assertEqual(resposta.context["form"]["ordem"].value(), 9)
        self.assertEqual(self.client.post(self.url("novo"), {"nome": "Produto novo", "ordem": 12}).status_code, 302)
        novo = ProdutoAT.objects.get(centro=self.centro, nome="Produto novo")
        self.assertIsNone(novo.codigo_padrao)
        self.assertEqual(self.client.post(self.url("editar", novo.pk), {"nome": "Revisado", "ordem": 0}).status_code, 302)
        self.assertEqual(self.client.post(self.url("novo"), {"nome": "  REVISADO  ", "ordem": 1}).status_code, 200)
        self.assertEqual(self.client.post(self.url("novo"), {"nome": "Ordem negativa", "ordem": -1}).status_code, 200)
        self.assertFalse(ProdutoAT.objects.filter(nome="Ordem negativa").exists())
        self.assertTrue(AuditLog.objects.filter(acao="EDITAR_PRODUTO_AT", registro_id=str(novo.pk)).exists())

    def test_sete_tipos_isolados_links_datas_opcionais_e_edicao(self):
        self.client.force_login(self.usuarios["master"])
        destino = self.url("material_novo", self.produto.pk, mes_inicial="2025-01", mes_final="2025-12")
        form = self.client.get(destino).context["form"]
        self.assertEqual(list(form.fields["tipo"].choices)[1:], list(TIPOS_MATERIAL_AT))
        self.assertEqual(dict(TIPOS_MATERIAL)["RELATORIO"], "Relatório técnico")
        for invalido in ("javascript:alert(1)", "ftp://example.org/file", "sem-link"):
            self.assertEqual(self.client.post(destino, {"titulo": "Teste", "tipo": "RELATORIO", "url": invalido}).status_code, 200)
        self.assertEqual(self.client.post(destino, {"titulo": "Tipo de projeto", "tipo": "SOFTWARE", "url": "https://example.org/teste"}).status_code, 200)
        self.assertFalse(MaterialProdutoAT.objects.exists())
        for tipo, _ in TIPOS_MATERIAL_AT:
            resposta = self.client.post(destino, {"titulo": "Material " + tipo, "tipo": tipo, "url": "https://example.org/" + tipo})
            self.assertEqual(resposta.status_code, 302)
            self.assertIn("base=fis", resposta.url)
            self.assertIn("mes_inicial=2025-01", resposta.url)
            self.assertIn("#entregaveis-at", resposta.url)
        material = MaterialProdutoAT.objects.first()
        self.assertIsNone(material.data_publicacao)
        self.assertEqual(self.client.post(self.url("material_editar", self.produto.pk, material.pk), {"titulo": "Editado", "tipo": "DOCUMENTO", "url": "https://example.org/editado", "data_publicacao": "2026-10-01"}).status_code, 302)
        material.refresh_from_db()
        self.assertEqual((material.titulo, material.data_publicacao), ("Editado", date(2026, 10, 1)))
        self.assertTrue(AuditLog.objects.filter(acao="EDITAR_MATERIAL_AT", registro_id=str(material.pk)).exists())

    def test_arquivo_produto_e_material_sem_perder_links(self):
        material = self.material()
        self.client.force_login(self.usuarios["master"])
        for acao, aparece in (("arquivar", False), ("reativar", True)):
            self.client.post(self.url("produto_situacao", self.produto.pk), {"acao": acao})
            ids = [p.pk for p in self.painel()["quadro_entregaveis_at"]["produtos"]]
            self.assertEqual(self.produto.pk in ids, aparece)
            self.assertTrue(MaterialProdutoAT.objects.filter(pk=material.pk).exists())
        self.client.post(self.url("material_situacao", material.pk), {"acao": "arquivar"})
        self.assertEqual(next(p for p in self.painel()["quadro_entregaveis_at"]["produtos"] if p.pk == self.produto.pk).total_materiais, 0)
        self.client.post(self.url("material_situacao", material.pk), {"acao": "reativar"})
        self.assertEqual(MaterialProdutoAT.objects.get(pk=material.pk).url, material.url)
        self.assertEqual(self.client.get(self.url("gerenciar")).status_code, 200)

    def test_centro_diferente_idor_csrf_e_acao_invalida(self):
        outro = CentroCompetencia.objects.create(codigo="isolado-at", nome="Isolado")
        produto = ProdutoAT.objects.filter(centro=outro).first()
        self.client.force_login(self.usuarios["master"])
        self.assertEqual(self.client.get(self.url("editar", produto.pk)).status_code, 404)
        self.assertEqual(self.client.get(self.url("material_novo", produto.pk)).status_code, 404)
        self.assertEqual(self.client.get(self.url("produto_situacao", self.produto.pk)).status_code, 405)
        self.assertEqual(self.client.post(self.url("produto_situacao", self.produto.pk), {"acao": "desconhecida"}).status_code, 400)
        protegido = Client(enforce_csrf_checks=True)
        protegido.force_login(self.usuarios["master"])
        self.assertEqual(protegido.post(self.url("produto_situacao", self.produto.pk), {"acao": "arquivar"}).status_code, 403)

    def test_filtros_e_exportacoes_completas_sem_mudar_kpis(self):
        self.material(data_publicacao=date(2024, 1, 1))
        kpi = KpiAcompanhamento.objects.create(acompanhamento=self.acomp, pilar=self.pilares["AT"], codigo="AT-TESTE", sequencia=1, nome="Empresas", unidade="Quantidade", meta_total=5, acumulado=2)
        antes = self.painel()["painel_pilar"]["blocos_fisicos"][0]["executado"]
        filtrado = self.painel(mes_inicial="2025-01", mes_final="2025-12")
        self.assertEqual(len(filtrado["quadro_entregaveis_at"]["produtos"]), 9)
        self.client.force_login(self.usuarios["master"])
        csv = self.client.get(self.url("csv", mes_inicial="2025-01"))
        self.assertContains(csv, "https://example.org/apresentacao")
        html = _html_standalone("todos", "fis", self.usuarios["master"], pilar=self.pilares["AT"], acompanhamento=self.acomp)
        self.assertTrue("Apresentação inicial" not in html)
        self.assertIn("1 material", html)
        self.assertContains(self.client.get(self.url("relatorio", self.produto.pk)), "Apresentação inicial")
        self.assertNotIn("Novo produto", html)
        self.assertNotIn("Book geral", html)
        kpi.refresh_from_db()
        self.assertEqual(kpi.acumulado, 2)
        self.assertEqual(self.painel()["painel_pilar"]["blocos_fisicos"][0]["executado"], antes)

    def test_reimportacao_nao_toca_produtos_e_materiais(self):
        material = self.material()
        ids = list(ProdutoAT.objects.filter(centro=self.centro).values_list("pk", flat=True))
        ingestar("FINANCEIRO_GERAL", FINANCEIRO, self.centro.nome, "3T/2026", self.usuarios["master"])
        self.assertEqual(list(ProdutoAT.objects.filter(centro=self.centro).values_list("pk", flat=True)), ids)
        self.assertEqual(MaterialProdutoAT.objects.get(pk=material.pk).url, material.url)
