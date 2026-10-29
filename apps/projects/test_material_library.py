from datetime import date
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accountability.models import Acompanhamento, CentroCompetencia
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.pillars.models import Pilar, UsuarioPilar
from apps.planning.views import contexto_pilar, _html_standalone

from .models import BookPrograma, MaterialProjeto, MaterialProdutoAT, ProdutoAT, Projeto


class BibliotecaMateriaisTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        garantir_grupos()
        cls.master = adicionar_grupo(get_user_model().objects.create_user(username="biblioteca-master"), "Master")
        cls.auditor = adicionar_grupo(get_user_model().objects.create_user(username="biblioteca-auditor"), "Auditor")
        cls.focal = adicionar_grupo(get_user_model().objects.create_user(username="biblioteca-focal"), "PontoFocal")
        cls.outras = adicionar_grupo(get_user_model().objects.create_user(username="biblioteca-outras"), "PontoFocal")
        cls.pilares = {c: Pilar.objects.get_or_create(codigo=c, defaults={"nome": c})[0] for c in ("AT", "OUTRASFONTES", "PDI", "FORMACAO", "STARTUPS")}
        UsuarioPilar.objects.create(usuario=cls.focal, pilar=cls.pilares["AT"])
        UsuarioPilar.objects.create(usuario=cls.outras, pilar=cls.pilares["OUTRASFONTES"])
        cls.centro = CentroCompetencia.objects.create(codigo="biblioteca", nome="Biblioteca")
        cls.acomp = Acompanhamento.objects.create(centro=cls.centro, periodo_referencia="3T/2026")
        cls.produto = ProdutoAT.objects.get(centro=cls.centro, codigo_padrao="WHITE_PAPER")
        cls.produto2 = ProdutoAT.objects.get(centro=cls.centro, codigo_padrao="PI")
        cls.projeto = Projeto.objects.create(centro=cls.centro, pilar=cls.pilares["PDI"], nome="Projeto laboratório")
        for produto in (cls.produto, cls.produto2):
            MaterialProdutoAT.objects.bulk_create([MaterialProdutoAT(produto=produto, titulo=f"Documento AT {i:03}", tipo="RELATORIO", url=f"https://example.org/at/{i}", data_publicacao=date(2025, 4, 1) if i % 2 else None) for i in range(120)])
        MaterialProjeto.objects.bulk_create([MaterialProjeto(projeto=cls.projeto, titulo=f"Documento projeto {i:03}", tipo="RELATORIO", url=f"https://example.org/projeto/{i}", data_publicacao=date(2024, 2, 1)) for i in range(120)])
        BookPrograma.objects.create(centro=cls.centro, titulo="Book excluído da busca", url="https://example.org/book")

    def setUp(self):
        self.client.force_login(self.master)

    def url(self, nome="materials:biblioteca", args=None, **params):
        return reverse(nome, args=args) + "?" + urlencode({"acompanhamento": self.acomp.pk, **params})

    def test_dashboard_resumo_sem_listas_ocultas(self):
        for pilar, numero in (("AT", 120), ("PDI", 120)):
            contexto = contexto_pilar(self.pilares[pilar], "todos", "fis", self.master, self.acomp)
            quadro = contexto["quadro_entregaveis_at" if pilar == "AT" else "quadro_entregaveis"]
            dono = next(o for o in quadro["produtos" if pilar == "AT" else "projetos"] if o.pk == (self.produto.pk if pilar == "AT" else self.projeto.pk))
            self.assertEqual(dono.total_materiais, numero)
            self.assertIsNotNone(dono.ultima_inclusao)
            self.assertNotIn("materiais", getattr(dono, "_prefetched_objects_cache", {}))
            resposta = self.client.get(reverse("core:pilar", args=[self.pilares[pilar].pk]), {"base": "fis", "acompanhamento": self.acomp.pk})
            self.assertContains(resposta, "120 materiais")
            self.assertNotContains(resposta, "Documento AT 119")
            self.assertNotContains(resposta, "Documento projeto 119")
            self.assertContains(resposta, "Ver materiais")
        html = _html_standalone("todos", "fis", self.master, pilar=self.pilares["PDI"], acompanhamento=self.acomp)
        self.assertNotIn("Documento projeto 119", html)
        self.assertIn("Book excluído da busca", html)

    def test_union_paginacao_e_chaves_de_tabelas_distintas(self):
        resposta = self.client.get(self.url(ordem="titulo"))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["total"], 360)
        self.assertEqual(len(resposta.context["linhas"]), 25)
        self.assertEqual(resposta.context["form"]["tamanho"].value(), "25")
        pagina2 = self.client.get(self.url(ordem="titulo", page=2))
        keys = lambda r: {(l["fonte"], l["id"]) for l in r.context["linhas"]}
        self.assertFalse(keys(resposta) & keys(pagina2))
        for tamanho in (10, 50):
            self.assertEqual(len(self.client.get(self.url(tamanho=tamanho)).context["linhas"]), tamanho)
        for pagina in ("inválida", "-1", "99999"):
            self.assertEqual(self.client.get(self.url(page=pagina)).status_code, 200)

    def test_busca_filtros_tipos_ano_sem_data_e_origem(self):
        cases = [({"pilar": "AT"}, 240), ({"tipo": "RELATORIO"}, 360), ({"ano_material": "2024"}, 120),
                 ({"ano_material": "sem_data"}, 120), ({"q": "laboratório"}, 120),
                 ({"origem": "AT:" + str(self.produto.pk)}, 120), ({"q": "inexistente"}, 0)]
        for filtros, total in cases:
            with self.subTest(filtros=filtros):
                resposta = self.client.get(self.url(**filtros))
                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(resposta.context["total"], total)
        resposta = self.client.get(self.url(q="Book excluído"))
        self.assertEqual(resposta.context["total"], 0)
        invalido = self.client.get(self.url(tamanho=999999))
        self.assertEqual(invalido.status_code, 400)
        self.assertEqual(invalido.context["total"], 0)

    def test_detalhes_projeto_produto_e_permissoes(self):
        for nome, args in (("deliverables_at:detalhe", [self.produto.pk]), ("projects:detalhe", [self.pilares["PDI"].pk, self.projeto.pk])):
            resposta = self.client.get(self.url(nome, args=args))
            self.assertEqual(resposta.status_code, 200)
            self.assertEqual(resposta.context["total"], 120)
        self.client.force_login(self.focal)
        resposta = self.client.get(self.url())
        self.assertEqual(resposta.context["total"], 240)
        self.assertEqual(self.client.get(self.url(pilar="PDI")).status_code, 403)
        self.assertEqual(self.client.get(self.url("projects:detalhe", args=[self.pilares["PDI"].pk, self.projeto.pk])).status_code, 403)
        self.client.force_login(self.outras)
        for nome in ("materials:biblioteca", "materials:csv", "materials:relatorio"):
            self.assertEqual(self.client.get(self.url(nome)).status_code, 403)

    def test_arquivados_incluem_origem_e_acesso_so_editores(self):
        self.produto.ativo = False
        self.produto.save()
        resposta = self.client.get(self.url(situacao="arquivados"))
        self.assertEqual(resposta.context["total"], 120)
        self.assertTrue(all(not r["dono_ativo"] for r in resposta.context["linhas"]))
        self.assertEqual(self.client.get(self.url()).context["total"], 240)
        self.client.force_login(self.auditor)
        self.assertEqual(self.client.get(self.url("deliverables_at:detalhe", args=[self.produto.pk])).status_code, 404)
        self.assertEqual(self.client.get(self.url(situacao="arquivados")).status_code, 400)
        self.assertNotContains(self.client.get(self.url()), "Arquivar")

    def test_exportacoes_sem_paginacao_e_sem_book_na_busca(self):
        csv = self.client.get(self.url("materials:csv", pilar="PDI", tamanho=10, page=2))
        self.assertEqual(len(csv.content.decode("utf-8-sig").splitlines()), 121)
        self.assertNotContains(csv, "https://example.org/book")
        report = self.client.get(self.url("materials:relatorio", pilar="PDI", tamanho=10, page=2))
        self.assertEqual(len(report.context["linhas"]), 120)
        self.assertNotContains(report, "Arquivar")
        self.assertNotContains(report, "Editar</a>")

    def test_retorno_assinado_preserva_consulta_e_rejeita_url_livre(self):
        resposta = self.client.get(self.url(q="Documento AT", tamanho=10, page=2))
        linha = resposta.context["linhas"][0]
        detalhe = self.client.get(linha["detalhe_url"])
        self.assertEqual(detalhe.context["voltar"], self.url(q="Documento AT", tamanho=10, page=2))
        edicao = self.client.get(linha["editar_url"])
        self.assertEqual(edicao.context["voltar"], self.url(q="Documento AT", tamanho=10, page=2))
        salvo = self.client.post(linha["editar_url"], {"titulo": linha["titulo"], "tipo": "DOCUMENTO", "url": linha["url"]})
        self.assertEqual(salvo.url, self.url(q="Documento AT", tamanho=10, page=2))
        retorno = self.client.post(linha["situacao_url"], {"acao": "arquivar"})
        self.assertEqual(retorno.url, salvo.url)
        falso = self.client.get(self.url("deliverables_at:material_editar", args=[self.produto.pk, MaterialProdutoAT.objects.filter(produto=self.produto).first().pk], retorno="https://evil.example"))
        self.assertTrue(falso.context["voltar"].startswith("/pilar/"))

    def test_gerenciamento_nao_renderiza_materiais(self):
        for nome, args in (("deliverables_at:gerenciar", []), ("projects:gerenciar", [self.pilares["PDI"].pk])):
            resposta = self.client.get(self.url(nome, args=args))
            self.assertEqual(resposta.status_code, 200)
            self.assertContains(resposta, "120 materiais ativos")
            self.assertNotContains(resposta, "Documento AT 119")
            self.assertNotContains(resposta, "Documento projeto 119")
