"""Contratos da apresentação importada, RBAC, edição auditada e imagens no DB."""
from datetime import date
from decimal import Decimal
from io import BytesIO

from PIL import Image
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.accountability.models import (
    Acompanhamento, CentroCompetencia, KpiAcompanhamento,
    OverrideAcompanhamento, ResumoFinanceiro,
)
from apps.accountability.panel import painel_acompanhamento
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.periods.models import Periodo
from apps.pillars.models import Pilar, UsuarioPilar

from .admin import ApresentacaoMensalAdmin, ConteudoApresentacaoAdmin
from .forms import ConteudoApresentacaoForm
from .models import ApresentacaoMensal, ConteudoApresentacao
from .presentation import compor_apresentacao


def imagem_png():
    arquivo = BytesIO()
    Image.new("RGB", (16, 16), "#2ebf7d").save(arquivo, "PNG")
    return SimpleUploadedFile("destaque.png", arquivo.getvalue(), content_type="image/png")


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class ApresentacaoTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        garantir_grupos()
        cls.usuarios = {}
        for papel in ("Master", "Admin", "PontoFocal", "Lideranca", "Auditor"):
            cls.usuarios[papel] = adicionar_grupo(
                User.objects.create_user(username=f"ap_{papel}", password="teste123", is_staff=True), papel,
            )
        cls.master = cls.usuarios["Master"]
        cls.pilares = {}
        for ordem, codigo in enumerate(("PDI", "FORMACAO", "STARTUPS", "INFRA", "AT", "OUTRASFONTES"), 1):
            cls.pilares[codigo], _ = Pilar.objects.get_or_create(codigo=codigo, defaults={"nome": codigo, "ordem": ordem})
        UsuarioPilar.objects.create(usuario=cls.usuarios["PontoFocal"], pilar=cls.pilares["PDI"])
        centro = CentroCompetencia.objects.create(codigo="quiin", nome="Centro QuIIN")
        cls.acomp = Acompanhamento.objects.create(centro=centro, periodo_referencia="3T/2026")
        for codigo in ("PDI", "FORMACAO", "STARTUPS", "INFRA"):
            ResumoFinanceiro.objects.create(
                acompanhamento=cls.acomp, origem="TAB. 1", pilar=cls.pilares[codigo],
                recurso_ou_meta=1000000, realizado=250000,
            )
        for codigo in ("AT", "OUTRASFONTES"):
            ResumoFinanceiro.objects.create(
                acompanhamento=cls.acomp, origem="TAB. 9", pilar=cls.pilares[codigo],
                recurso_ou_meta=500000, captado=200000, realizado=30000,
            )
        cls.kpi = KpiAcompanhamento.objects.create(
            acompanhamento=cls.acomp, codigo="PE-01", sequencia=1, pilar=cls.pilares["PDI"],
            nome="Projetos de pesquisa", unidade="Número absoluto", meta_total=20, acumulado=8,
            meta_2024=10, executado_2024=3, projecao_2026=99,
        )
        cls.apresentacao = ApresentacaoMensal.objects.create(
            competencia=date(2026, 10, 1), acompanhamento=cls.acomp, criado_por=cls.master,
        )
        cls.url = reverse("core:mensal")
        cls.editor = reverse("core:mensal_editar") + "?periodo=2026-10-01"

    def setUp(self):
        self.client.force_login(self.master)

    def conteudo(self, **kwargs):
        valores = {"apresentacao": self.apresentacao, "titulo": "Destaque de pesquisa", "texto": "Um marco do centro."}
        valores.update(kwargs)
        return ConteudoApresentacao.objects.create(**valores)

    def test_roteiro_de_nove_slides_e_fonte_explicita(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["quantidade_slides"], 9)
        self.assertEqual([s["tipo"] for s in resposta.context["slides"]],
                         ["capa", "resumo", "pilar", "pilar", "pilar", "pilar", "ppi", "fontes", "encerramento"])
        self.assertContains(resposta, "3T/2026")
        self.assertContains(resposta, 'data-presentation-deck')
        self.assertContains(resposta, 'vendor/reveal-6.0.2/reveal.js')
        self.assertNotContains(resposta, "Evolução financeira mensal")

    def test_numeros_e_ajustes_sao_os_do_painel(self):
        OverrideAcompanhamento.objects.create(
            acompanhamento=self.acomp, base="financeiro", pilar=self.pilares["PDI"], ano=0,
            campo="executado", valor=Decimal("400000.02"), chave="fin|PDI|0|executado",
        )
        OverrideAcompanhamento.objects.create(
            acompanhamento=self.acomp, base="fisico", kpi=self.kpi, ano=0,
            campo="executado", valor=12, chave="fis|PE-01|0|executado",
        )
        resposta = self.client.get(self.url)
        codigos = list(self.pilares)
        painel_fin = painel_acompanhamento(None, "fin", self.acomp, codigos)
        painel_fis = painel_acompanhamento(None, "fis", self.acomp, codigos)
        ppi = next(s for s in resposta.context["slides"] if s["tipo"] == "ppi")
        pdi = next(s for s in resposta.context["slides"] if s["chave"] == "pdi")
        self.assertEqual(ppi["total"], painel_fin["tabela_tab1"]["total"])
        self.assertEqual(pdi["indicadores"], painel_fis["tabela"]["grupos"][0]["linhas"])
        self.assertContains(resposta, "R$ 400.000,02")

    def test_reimportacao_atualiza_e_novo_acompanhamento_nao_troca_vinculo(self):
        ResumoFinanceiro.objects.filter(acompanhamento=self.acomp, pilar=self.pilares["PDI"]).update(realizado=123456)
        Acompanhamento.objects.create(centro=self.acomp.centro, periodo_referencia="4T/2026")
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.context["apresentacao"].acompanhamento_id, self.acomp.pk)
        self.assertContains(resposta, "R$ 123.456,00")
        self.assertNotContains(resposta, "4T/2026")

    def test_mais_recente_e_mes_sem_configuracao_sem_escrita(self):
        ApresentacaoMensal.objects.create(competencia=date(2026, 11, 1), acompanhamento=self.acomp)
        self.assertEqual(self.client.get(self.url).context["apresentacao"].competencia, date(2026, 11, 1))
        quantidade = ApresentacaoMensal.objects.count()
        resposta = self.client.get(self.url, {"periodo": "2026-09-01"})
        self.assertContains(resposta, "ainda não configurada")
        self.assertEqual(ApresentacaoMensal.objects.count(), quantidade)
        self.assertEqual(Periodo.objects.count(), 0)

    def test_sem_apresentacoes_mostra_configuracao(self):
        self.apresentacao.delete()
        resposta = self.client.get(self.url)
        self.assertContains(resposta, "Configurar apresentação")
        self.assertNotContains(resposta, "data-presentation-deck")

    def test_periodos_malformados_redirecionam(self):
        for periodo in ("2026-13-01", "2026-10-12", "20261001", "amanhã"):
            with self.subTest(periodo=periodo):
                self.assertRedirects(self.client.get(self.url, {"periodo": periodo}), self.url + "?periodo=2026-10-01", fetch_redirect_response=False)

    def test_login_obrigatorio_e_post_na_leitura_nao_aceito(self):
        self.assertEqual(self.client.post(self.url).status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_focal_ve_somente_seu_pilar_totais_e_imagens(self):
        self.conteudo(titulo="Geral permitido")
        self.conteudo(titulo="Pesquisa permitida", pilar=self.pilares["PDI"])
        proibido = self.conteudo(titulo="Segredo AT", pilar=self.pilares["AT"], imagem=b"imagem", imagem_mime="image/png")
        self.client.force_login(self.usuarios["PontoFocal"])
        resposta = self.client.get(self.url)
        self.assertContains(resposta, "Geral permitido")
        self.assertContains(resposta, "Pesquisa permitida")
        self.assertNotContains(resposta, "Segredo AT")
        self.assertNotContains(resposta, "R$ 200.000,00")
        ppi = next(s for s in resposta.context["slides"] if s["tipo"] == "ppi")
        self.assertEqual(ppi["total"]["realizado"], Decimal(250000))
        self.assertEqual(len(ppi["linhas"]), 1)
        self.assertNotContains(resposta, 'data-slide-kind="fontes"')
        self.assertEqual(self.client.get(reverse("core:mensal_imagem", args=[proibido.pk])).status_code, 404)
        pdf = self.client.get(self.url, {"print-pdf": "1"})
        self.assertNotContains(pdf, "Segredo AT")
        self.assertNotContains(pdf, "R$ 200.000,00")

    def test_leitores_sem_edicao_e_crud_bloqueado(self):
        conteudo = self.conteudo()
        urls = [self.editor, reverse("core:mensal_conteudo_novo", args=[self.apresentacao.pk]),
                reverse("core:mensal_conteudo_editar", args=[self.apresentacao.pk, conteudo.pk])]
        for papel in ("PontoFocal", "Lideranca", "Auditor"):
            self.client.force_login(self.usuarios[papel])
            self.assertNotContains(self.client.get(self.url), "Editar apresentação")
            for url in urls:
                with self.subTest(papel=papel, url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)
                    self.assertEqual(self.client.post(url, {}).status_code, 403)
            self.assertEqual(self.client.post(reverse("core:mensal_conteudo_excluir", args=[self.apresentacao.pk, conteudo.pk])).status_code, 403)

    def test_dados_ausentes_zero_e_projecoes_nao_sao_execucao(self):
        ResumoFinanceiro.objects.filter(pilar=self.pilares["PDI"]).update(realizado=0)
        ResumoFinanceiro.objects.filter(pilar=self.pilares["FORMACAO"]).update(realizado=None)
        KpiAcompanhamento.objects.filter(pk=self.kpi.pk).update(acumulado=None)
        ctx = compor_apresentacao(self.apresentacao, self.master)
        ppi = next(s for s in ctx["slides"] if s["tipo"] == "ppi")
        self.assertEqual(ppi["linhas"][0]["realizado"], Decimal(0))
        self.assertIsNone(ppi["linhas"][1]["realizado"])
        pdi = next(s for s in ctx["slides"] if s["chave"] == "pdi")
        self.assertIsNone(pdi["indicadores"][0]["executado"])
        self.assertIsNone(pdi["indicadores"][0]["pct"])

    def test_meta_superada_preserva_valor_e_cumprimento_limitado(self):
        KpiAcompanhamento.objects.filter(pk=self.kpi.pk).update(acumulado=35)
        pdi = next(s for s in compor_apresentacao(self.apresentacao, self.master)["slides"] if s["chave"] == "pdi")
        self.assertEqual(pdi["indicadores"][0]["executado"], Decimal(35))
        self.assertEqual(pdi["indicadores"][0]["pct"], 100)

    def test_acompanhamento_apenas_com_captacao_preserva_dados_disponiveis(self):
        ResumoFinanceiro.objects.filter(acompanhamento=self.acomp, origem="TAB. 1").delete()
        slides = compor_apresentacao(self.apresentacao, self.master)["slides"]
        fontes = next(s for s in slides if s["tipo"] == "fontes")
        self.assertEqual(fontes["fontes"][0]["captado"], Decimal(200000))
        self.assertEqual(fontes["fontes"][0]["meta"], Decimal(500000))
        ppi = next(s for s in slides if s["tipo"] == "ppi")
        self.assertIsNone(ppi["total"]["realizado"])

    def test_texto_longo_paginado_sem_perda_e_html_escapado(self):
        texto = " ".join(f"palavra{n}" for n in range(500))
        self.conteudo(titulo="<script>malicioso</script>", texto=texto)
        resposta = self.client.get(self.url)
        paginas = [s["item"]["texto"] for s in resposta.context["slides"] if s["tipo"] == "editorial"]
        self.assertGreater(len(paginas), 1)
        self.assertEqual(" ".join(" ".join(paginas).split()), texto)
        self.assertNotContains(resposta, "<script>malicioso</script>")
        self.assertContains(resposta, "&lt;script&gt;malicioso&lt;/script&gt;")

    def test_pdf_usa_mesmos_slides_sem_shell(self):
        resposta = self.client.get(self.url, {"periodo": "2026-10-01", "print-pdf": "1"})
        self.assertEqual(resposta.context["quantidade_slides"], 9)
        self.assertContains(resposta, "data-presentation-print")
        self.assertNotContains(resposta, 'data-testid="sidebar"')
        self.assertNotContains(resposta, 'data-testid="app-header"')

    def test_hx_recebe_pagina_com_main_para_swap(self):
        resposta = self.client.get(self.url, headers={"HX-Request": "true", "HX-Boosted": "true"})
        self.assertContains(resposta, 'id="main"')
        self.assertContains(resposta, 'data-testid="presentation-deck"')
        self.assertContains(resposta, "presentation.js")

    def test_orcamento_de_queries(self):
        for n in range(10):
            self.conteudo(titulo=f"Registro {n}", pilar=self.pilares["PDI"])
        with CaptureQueriesContext(connection) as consultas:
            resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertLessEqual(len(consultas), 30)

    def test_salvar_apresentacao_admin_master_e_auditoria(self):
        for papel, mes in (("Master", "2026-11"), ("Admin", "2026-12")):
            self.client.force_login(self.usuarios[papel])
            resposta = self.client.post(reverse("core:mensal_editar"), {
                "competencia": mes, "acompanhamento": self.acomp.pk, "titulo": "Reunião de acompanhamento",
            })
            self.assertEqual(resposta.status_code, 302)
            obj = ApresentacaoMensal.objects.get(competencia=f"{mes}-01")
            self.assertEqual(obj.criado_por, self.usuarios[papel])
            self.assertTrue(AuditLog.objects.filter(entidade="ApresentacaoMensal", registro_id=str(obj.pk), acao="CRIAR_APRESENTACAO").exists())
        self.assertEqual(Periodo.objects.count(), 0)

    def test_editar_vinculo_e_mes_duplicado(self):
        novo = Acompanhamento.objects.create(centro=self.acomp.centro, periodo_referencia="4T/2026")
        resposta = self.client.post(self.editor, {"competencia": "2026-01", "acompanhamento": novo.pk, "titulo": "Nova referência"})
        self.assertEqual(resposta.status_code, 302)
        self.apresentacao.refresh_from_db()
        self.assertEqual(self.apresentacao.acompanhamento, novo)
        self.assertEqual(self.apresentacao.competencia, date(2026, 10, 1))
        resposta = self.client.post(reverse("core:mensal_editar"), {"competencia": "2026-10", "acompanhamento": novo.pk})
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.context["form"].errors)

    def test_referencia_mensal_aparece_na_selecao_e_na_capa(self):
        mensal = Acompanhamento.objects.create(centro=self.acomp.centro, periodo_referencia="09/2026")
        resposta = self.client.get(self.editor)
        self.assertContains(resposta, "Centro QuIIN · 09/2026")
        resposta = self.client.post(self.editor, {
            "competencia": "2026-10", "acompanhamento": mensal.pk, "titulo": ""})
        self.assertEqual(resposta.status_code, 302)
        self.apresentacao.refresh_from_db()
        self.assertEqual(self.apresentacao.acompanhamento, mensal)
        self.assertEqual(self.apresentacao.competencia, date(2026, 10, 1))
        resposta = self.client.get(self.url, {"periodo": "2026-10-01"})
        self.assertContains(resposta, "Referência dos dados <strong>09/2026</strong>", html=True)
        self.acomp.refresh_from_db()
        self.assertEqual(self.acomp.periodo_referencia, "3T/2026")

    def test_upload_imagem_no_banco_leitura_e_remocao(self):
        url = reverse("core:mensal_conteudo_novo", args=[self.apresentacao.pk])
        resposta = self.client.post(url, {"tipo": "DESTAQUE", "titulo": "Laboratório", "texto": "Infraestrutura disponível.", "ordem": 2, "arquivo_imagem": imagem_png()})
        self.assertEqual(resposta.status_code, 302)
        obj = ConteudoApresentacao.objects.get(titulo="Laboratório")
        self.assertTrue(bytes(obj.imagem).startswith(b"\x89PNG"))
        self.assertEqual(obj.imagem_alt, "Laboratório")
        self.assertEqual(obj.imagem_mime, "image/png")
        img = self.client.get(reverse("core:mensal_imagem", args=[obj.pk]))
        self.assertEqual(img.content, bytes(obj.imagem))
        self.assertEqual(img["Content-Type"], "image/png")
        self.assertEqual(img["Cache-Control"], "private, no-store")
        resposta = self.client.post(reverse("core:mensal_conteudo_editar", args=[self.apresentacao.pk, obj.pk]), {
            "tipo": "PENDENCIA", "titulo": obj.titulo, "texto": obj.texto, "ordem": 0, "remover_imagem": "on",
        })
        self.assertEqual(resposta.status_code, 302)
        obj.refresh_from_db()
        self.assertEqual(bytes(obj.imagem), b"")
        self.assertEqual(self.client.get(reverse("core:mensal_imagem", args=[obj.pk])).status_code, 404)

    def test_imagem_de_alta_resolucao_abaixo_de_5_mb_e_aceita(self):
        buffer = BytesIO()
        with Image.new("RGB", (6000, 4000), "#2ebf7d") as imagem:
            imagem.save(buffer, "JPEG")
        dados = buffer.getvalue()
        self.assertLess(len(dados), 5 * 1024 * 1024)
        resposta = self.client.post(
            reverse("core:mensal_conteudo_novo", args=[self.apresentacao.pk]),
            {"tipo": "DESTAQUE", "titulo": "Foto de alta resolução", "texto": "Registro do mês.", "ordem": 0,
             "arquivo_imagem": SimpleUploadedFile("foto.jpg", dados, content_type="image/jpeg")},
        )
        self.assertEqual(resposta.status_code, 302)
        conteudo = ConteudoApresentacao.objects.get(titulo="Foto de alta resolução")
        self.assertEqual(bytes(conteudo.imagem), dados)
        self.assertEqual(conteudo.imagem_mime, "image/jpeg")

    def test_imagem_invalida_e_tipo_incompativel(self):
        url = reverse("core:mensal_conteudo_novo", args=[self.apresentacao.pk])
        resposta = self.client.post(url, {"tipo": "DESTAQUE", "titulo": "Inválido", "texto": "Texto", "ordem": 0,
                                         "arquivo_imagem": SimpleUploadedFile("x.png", b"nao-e-imagem", content_type="image/png")})
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("arquivo_imagem", resposta.context["form"].errors)
        form = ConteudoApresentacaoForm({"tipo": "PENDENCIA", "titulo": "Teste", "texto": "Texto", "ordem": 0}, {"arquivo_imagem": imagem_png()})
        self.assertFalse(form.is_valid())
        self.assertIn("tipo", form.errors)
        arquivo = imagem_png()
        arquivo.size = 6 * 1024 * 1024
        form = ConteudoApresentacaoForm({"tipo": "DESTAQUE", "titulo": "Teste", "texto": "Texto", "ordem": 0}, {"arquivo_imagem": arquivo})
        self.assertFalse(form.is_valid())
        self.assertIn("arquivo_imagem", form.errors)

    def test_exclusao_exige_post_e_nao_cruza_apresentacoes(self):
        obj = self.conteudo()
        url = reverse("core:mensal_conteudo_excluir", args=[self.apresentacao.pk, obj.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        outro = ApresentacaoMensal.objects.create(competencia=date(2026, 11, 1), acompanhamento=self.acomp)
        self.assertEqual(self.client.post(reverse("core:mensal_conteudo_excluir", args=[outro.pk, obj.pk])).status_code, 404)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(ConteudoApresentacao.objects.filter(pk=obj.pk).exists())
        self.assertTrue(AuditLog.objects.filter(acao="EXCLUIR_APRESENTACAO", entidade="ConteudoApresentacao").exists())

    def test_modelo_rejeita_competencia_no_meio_do_mes(self):
        obj = ApresentacaoMensal(competencia=date(2026, 10, 15), acompanhamento=self.acomp)
        with self.assertRaises(ValidationError):
            obj.full_clean()

    def test_admin_restringe_escrita_e_formulario_de_conteudo_funciona(self):
        for model, classe in ((ApresentacaoMensal, ApresentacaoMensalAdmin), (ConteudoApresentacao, ConteudoApresentacaoAdmin)):
            instancia = classe(model, admin.site)
            for papel, usuario in self.usuarios.items():
                request = RequestFactory().get("/admin/")
                request.user = usuario
                self.assertEqual(instancia.has_add_permission(request), papel in ("Master", "Admin"))
                self.assertEqual(instancia.has_change_permission(request), papel in ("Master", "Admin"))
                self.assertEqual(instancia.has_delete_permission(request), papel in ("Master", "Admin"))
        resposta = self.client.post(reverse("admin:reports_conteudoapresentacao_add"), {
            "apresentacao": self.apresentacao.pk, "tipo": "DESTAQUE", "titulo": "Via Admin",
            "texto": "Imagem salva pelo Admin.", "ordem": 0, "arquivo_imagem": imagem_png(), "_save": "Salvar",
        })
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(ConteudoApresentacao.objects.get(titulo="Via Admin").imagem)
