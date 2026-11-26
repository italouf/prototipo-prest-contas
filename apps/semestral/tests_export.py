"""Testes automatizados de Round-Trip Excel Integrity (T2 — Exportação Lossless v3.1)."""
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from django.conf import settings
from django.test import TestCase
import openpyxl

from .models import CicloSemestral, CompetenciaMensalPilar, ConfiguracaoPilarSemestral
from .models_registros import (
    RegAcsEmpresa,
    RegAcsPedidoPi,
    RegAcsProfissional,
    RegAcsProjetoFormacao,
    RegAcsProjetoPdi,
    RegAcsPublicacao,
    RegAfcctPedidoPi,
    RegAfcctProfissional,
    RegAfcctProjetoFormacao,
    RegAfcctProjetoPdi,
    RegAfcctPublicacao,
    RegAtAtividade,
    RegAtProspeccao,
    RegFcrhProfissional,
    RegFcrhProjeto,
    RegFinAssociadas,
    RegFinConselho,
    RegFinCoopInternacional,
    RegFinCoopNacional,
    RegFinEquipe,
    RegFinEventos,
    RegFinLicenciamentoPI,
    RegFinMidia,
    RegFinOutrasFontes,
    RegOutrosComentarios,
)
from .xlsx_exporter import (
    TEMPLATE_MAP,
    TEMPLATES_DIR,
    exportar_pacote_semestral_zip,
    exportar_planilha_embrapii,
    validar_integridade_xlsx,
)


class RoundTripExcelIntegrityTestes(TestCase):
    """Popula todas as 28 abas QuIIN nos 5 arquivos e valida preservação OOXML total."""

    def setUp(self):
        self.ciclo = CicloSemestral.objects.create(
            ano=2026,
            semestre=1,
            centro_competencia="QuIIN (SENAI CIMATEC)",
            abreviacao_cc="QIN",
            termo_cooperacao="042/2023-QIN",
            periodo_referencia_label="1º semestre/2026",
            coordenacao_nome="Mabel",
            coordenacao_email="mabel.gestao@quiin.local",
        )
        pilar_defs = [
            ("FIN_QUIIN", "Financeiro QuIIN (Aba 10 + Abas Azuis 11–18)", "FIN", 1),
            ("FCRH", "FCRH — Formação e Capacitação de RH", "FCRH", 2),
            ("ACS", "ACS — Atração e Criação de Startups", "ACS", 3),
            ("AFCCT", "AFCCT — Ampliação e Fortalecimento de Competências", "AFCCT", 4),
            ("AT", "AT — Associação Tecnológica", "AT", 5),
        ]
        self.comps = {}
        for cod, nome, arq, ordem in pilar_defs:
            cfg = ConfiguracaoPilarSemestral.objects.create(
                codigo=cod,
                nome=nome,
                arquivo_embrapii=arq,
                responsavel_nome=f"Resp {cod}",
                responsavel_email=f"{cod.lower()}@quiin.local",
                ordem=ordem,
            )
            c_jan = CompetenciaMensalPilar.objects.create(
                ciclo=self.ciclo,
                configuracao_pilar=cfg,
                competencia=date(2026, 1, 1),
                prazo_limite=datetime(2026, 2, 5, 23, 59, tzinfo=timezone.utc),
            )
            c_fev = CompetenciaMensalPilar.objects.create(
                ciclo=self.ciclo,
                configuracao_pilar=cfg,
                competencia=date(2026, 2, 1),
                prazo_limite=datetime(2026, 3, 5, 23, 59, tzinfo=timezone.utc),
            )
            self.comps[cod] = (c_jan, c_fev)

        self._popular_todas_as_28_abas()

    def _popular_todas_as_28_abas(self):
        fin_jan, fin_fev = self.comps["FIN_QUIIN"]
        # 10. Conta Ação - Outras Fontes (inclui >8 registros para testar R11..R18 vs R19 com fórmula em D)
        for i in range(1, 11):
            RegFinOutrasFontes.objects.create(
                competencia_mensal=fin_jan if i <= 5 else fin_fev,
                acao_relacionada="AFCCT" if i != 9 else "Ampliação de Infraestrutura",
                codigo_projeto_atividade=f"QIN-PROJ-{i:03d}",
                tipo_despesa="Material de consumo",
                mes_ano_competencia=date(2026, 1 if i <= 5 else 2, 1),
                entidade_aporte="Parceiro Privado & CIMATEC",
                descricao=f"Compra criogênica #{i} — Quântica",
                data_movimentacao=date(2026, 1, 15 + (i % 10)),
                valor=Decimal("1250.75") * i,
            )
        # 11. Equipe
        RegFinEquipe.objects.create(
            competencia_mensal=fin_jan,
            nome_completo="Dra. Mariana Quântica & Souza",
            cpf_passaporte="12345678901",
            titulacao="Doutor(a)",
            formacao_academica="Física Computacional",
            atividade_funcao="Coordenador(a) do CC",
            disponibilidade_horas_mes=160,
            link_lattes="http://lattes.cnpq.br/0000000000000001",
            data_admissao=date(2024, 3, 1),
            observacoes="Dedicação integral ao QuIIN.",
        )
        # 12. Licenciamento de PIs
        RegFinLicenciamentoPI.objects.create(
            competencia_mensal=fin_jan,
            titulo_pi="Algoritmo de Otimização QAOA",
            codigo_projeto="QIN-AFCCT-2025-1-10-1",
            tipo_pi="Programa de computador",
            numero_pedido_inpi="BR512026000123",
            empresa_estrangeira="Não",
            razao_social="Quantum Tech Ltda",
            cnpj="12345678000199",
            pais_sede="Brasil",
            participacao_resultados="Royalties 3%",
            observacoes="Licenciamento não exclusivo.",
        )
        # 13. Acompanhamento Associadas
        RegFinAssociadas.objects.create(
            competencia_mensal=fin_fev,
            razao_social="Indústria Óptica S.A.",
            nome_fantasia="ÓpticaLab",
            cnpj="98765432000110",
            eh_startup="Não",
            data_inicio_associacao=date(2024, 6, 1),
            categoria_at="A",
            associacao_vigente="Sim",
            contrib_ano1=Decimal("50000.00"),
            contrib_ano2=Decimal("60000.00"),
            contrib_ano3=Decimal("0.00"),
            contrib_ano4=Decimal("0.00"),
            nome_contato="Carlos Mendes",
            cargo_contato="Diretor de P&D",
            email_contato="carlos@opticalab.local",
            part_pdi="Sim",
            part_fcrh="Sim",
            part_acs="Não",
            part_lic_pi="Não",
            doacao_infra="Não",
            observacoes="Associada ativa.",
        )
        # 14. Cooperação Nacional
        RegFinCoopNacional.objects.create(
            competencia_mensal=fin_jan,
            nome_instituicao="USP São Carlos",
            cidade_instituicao="São Carlos/SP",
            data_inicio=date(2025, 2, 1),
            vigente="Sim",
            codigos_projetos="QIN-AFCCT-2025-2-1-1",
            instrumento_formalizacao="Acordo de Cooperação Técnica",
            nome_contato="Prof. Renato Silva",
            cargo_contato="Pesquisador",
            email_contato="renato@usp.local",
            objetivo="Pesquisa conjunta em qubits supercondutores.",
            resultados_atividades="2 artigos em preparação.",
            observacoes="",
        )
        # 15. Cooperação Internacional (2 registros para validar H11 com fórmula vs H12 sem fórmula)
        for idx, vigente in enumerate(["Sim", "Não"], start=1):
            RegFinCoopInternacional.objects.create(
                competencia_mensal=fin_fev,
                nome_instituicao=f"Fraunhofer Institute #{idx}",
                pais="Alemanha",
                cidade="Munique",
                data_inicio=date(2024, 9, 1),
                vigente=vigente,
                data_encerramento=date(2026, 2, 15) if vigente == "Não" else None,
                codigos_projetos="QIN-AFCCT-2024-9-1-1",
                instrumento_formalizacao="MoU",
                nome_contato="Dr. Hans Mueller",
                cargo_contato="Head of Quantum",
                email_contato="hans@fraunhofer.local",
                objetivo="Intercâmbio de pesquisadores.",
                resultados_atividades="Workshop conjunto realizado.",
                observacoes="Parceria estratégica.",
            )
        # 16. Mídia
        RegFinMidia.objects.create(
            competencia_mensal=fin_jan,
            titulo_publicacao="SENAI CIMATEC inaugura laboratório QuIIN",
            veiculo_divulgacao="Portal Inovação Brasil",
            porta_voz_fonte="Mabel QuIIN",
            link_publicacao="https://quiin.senai.local/noticia-1",
            data_publicacao=date(2026, 1, 20),
            observacoes="Matéria de capa.",
        )
        # 17. Eventos
        RegFinEventos.objects.create(
            competencia_mensal=fin_fev,
            titulo_evento="Quantum LatAm Summit 2026",
            tipo_evento="Seminário técnico",
            formato_evento="Híbrido",
            tipo_participacao="Palestrante",
            local_realizacao="Salvador/BA/Brasil",
            data_realizacao=date(2026, 2, 18),
            participantes_cc="Equipe QuIIN",
            resultado_alcancado="3 prospecções iniciadas.",
            entidades_contatadas="Petrobras, Vale",
            observacoes="Painel principal.",
        )
        # 18. Conselho Consultivo
        RegFinConselho.objects.create(
            competencia_mensal=fin_jan,
            nome_membro="Dra. Helena Costa",
            cpf="11122233344",
            instituicao_vinculada="MCTI",
            categoria_representante="Setor Público",
            nivel_representacao="Titular",
            duracao_mandato_anos=Decimal("2.0"),
            data_entrada=date(2024, 1, 10),
            membro_ativo="Sim",
            observacoes="Reunião semestral realizada.",
        )

        # ---------------- FCRH ----------------
        fcrh_jan, fcrh_fev = self.comps["FCRH"]
        RegFcrhProjeto.objects.create(
            competencia_mensal=fcrh_jan,
            titulo="Bootcamp Computação Quântica Aplicada",
            objetivo="Capacitar engenheiros da indústria.",
            descricao_publica="Curso intensivo em Qiskit e algoritmos variacionais.",
            ementa_detalhada="Módulo 1 a 4",
            carga_horaria_total=Decimal("80.0"),
            publico_alvo="Engenheiros e pesquisadores",
            status_atual="Em andamento",
            valor_total_planejado=Decimal("150000.00"),
            data_inicio=date(2026, 1, 10),
            qtd_iniciaram=40,
            qtd_concluiram=32,
            tipo_formacao="Curso de curta duração",
            onde_realizada="No próprio CC",
            vinculo_linhas_tematicas="Computação Quântica",
            qtd_empresas_at=4,
            observacoes="Turma 01/2026.",
        )
        RegFcrhProfissional.objects.create(
            competencia_mensal=fcrh_fev,
            nome_completo="Lucas Almeida",
            cpf="55566677788",
            email="lucas@empresa.local",
            codigo_projeto="QIN-FCRH-2026-1-10-1",
            vinculo_profissional="Com uma empresa da AT",
            data_conclusao=date(2026, 2, 20),
            certificado_emitido="Sim (não reconhecido pelo MEC)",
            link_certificados="https://cert.quiin.local/1",
            observacao="Concluiu com 95%.",
        )
        RegOutrosComentarios.objects.create(
            competencia_mensal=fcrh_jan,
            arquivo="FCRH",
            aba="4. Outros comentários",
            comentario="Comentário de janeiro FCRH.",
        )
        RegOutrosComentarios.objects.create(
            competencia_mensal=fcrh_fev,
            arquivo="FCRH",
            aba="4. Outros comentários",
            comentario="Comentário de fevereiro FCRH.",
        )

        # ---------------- ACS ----------------
        acs_jan, acs_fev = self.comps["ACS"]
        RegAcsProjetoPdi.objects.create(
            competencia_mensal=acs_jan,
            titulo="Sensoriamento Quântico com Diamantes NV",
            ambiente_inovacao_aberta="Sim",
            forma_cooperada="Sim",
            objetivo="Protótipo de magnetômetro.",
            descricao_publica="Desenvolvimento de sensor quântico.",
            trl_inicial="TRL 2",
            trl_final="TRL 4",
            status_atual="Em andamento",
            valor_total_planejado=Decimal("320000.00"),
            qtd_pis_geradas=1,
            qtd_publicacoes_geradas=1,
            data_inicio=date(2026, 1, 12),
            qtd_empresas_base_tec=2,
            observacoes="",
        )
        RegAcsPedidoPi.objects.create(
            competencia_mensal=acs_fev,
            titulo_pi="Magnetômetro NV Compacto",
            codigo_projeto="QIN-PJACS-2026-1-12-1",
            tipo_pi="Patente - Invenção",
            data_pedido=date(2026, 2, 10),
            numero_pedido_inpi="BR102026000456",
            link="https://inpi.local/456",
            observacoes="",
        )
        RegAcsPublicacao.objects.create(
            competencia_mensal=acs_fev,
            titulo_publicacao="NV-Center Magnetometry at Room Temp",
            codigo_projeto="QIN-PJACS-2026-1-12-1",
            data_publicacao_aceite=date(2026, 2, 15),
            titulo_periodico="Quantum Science & Tech",
            classificacao_periodico="A1",
            autores="Silva, R.; Costa, H.",
            outras_informacoes="DOI 10.1088/qst",
            link="https://doi.org/10.1088/qst",
            observacoes="",
        )
        RegAcsProjetoFormacao.objects.create(
            competencia_mensal=acs_jan,
            titulo="Empreendedorismo DeepTech Quântico",
            objetivo="Capacitar founders.",
            descricao_publica="Mentoria para startups quânticas.",
            ementa_detalhada="Modelagem de negócios e PI.",
            carga_horaria_total=Decimal("40.0"),
            publico_alvo="Pesquisadores empreendedores",
            status_atual="Concluído",
            valor_total_planejado=Decimal("60000.00"),
            data_inicio=date(2026, 1, 5),
            data_termino=date(2026, 2, 1),
            qtd_iniciaram=20,
            qtd_concluiram=18,
            tipo_formacao="Curso de curta duração",
            onde_realizada="No próprio CC",
            vinculo_linhas_tematicas="Startups",
            observacoes="",
        )
        RegAcsProfissional.objects.create(
            competencia_mensal=acs_fev,
            nome_completo="Beatriz Lima",
            cpf="22233344455",
            email="beatriz@startup.local",
            codigo_projeto="QIN-FCRH-ACS-2026-1-5-1",
            vinculo_profissional="Profissional de startup vinculada ao Centro",
            data_conclusao=date(2026, 2, 1),
            certificado_emitido="Sim (não reconhecido pelo MEC)",
            link_certificados="https://cert.quiin.local/acs1",
            observacao="",
        )
        RegAcsEmpresa.objects.create(
            competencia_mensal=acs_jan,
            razao_social="Qubit Brasil Ltda",
            nome_fantasia="QubitBR",
            codigo_projeto="QIN-PJACS-2026-1-12-1",
            cnpj="44555666000177",
            eh_ebt_ou_startup="Sim",
            startup_atraida_criada="Criada",
            nome_contato="André Nogueira",
            cargo="CEO",
            telefone="71999990000",
            email="andre@qubitbr.local",
            houve_alavancagem="Não",
            valor_alavancagem=Decimal("100000.00"),
            quem_realizou_alavancagem="FAPESB",
            modelo_alavancagem="Subvenção econômica",
            observacao="Startup incubada no CIMATEC.",
        )
        RegOutrosComentarios.objects.create(
            competencia_mensal=acs_fev,
            arquivo="ACS",
            aba="6. Outros comentários",
            comentario="Sem intercorrências no ACS.",
        )

        # ---------------- AFCCT ----------------
        af_jan, af_fev = self.comps["AFCCT"]
        for i in range(1, 3):
            RegAfcctProjetoPdi.objects.create(
                competencia_mensal=af_jan if i == 1 else af_fev,
                titulo=f"Criptografia Pós-Quântica #{i}",
                resumo_projeto="Implementação PQC em hardware.",
                descricao_publica="Biblioteca PQC resistente a ataques quânticos.",
                envolvimento_empresas_at="Sim" if i == 1 else "Não",
                nomes_profissionais_at="Eng. João" if i == 1 else "N/A",
                empresas_at_vinculadas="ÓpticaLab" if i == 1 else "N/A",
                trl_inicial="TRL 3",
                trl_final="TRL 5",
                status_atual="Em andamento",
                resultados_executados="Benchmarking em FPGA.",
                valor_total_planejado=Decimal("450000.00"),
                qtd_pis_geradas=1,
                qtd_publicacoes_geradas=2,
                data_inicio=date(2026, 1, 8 + i),
                data_prevista_termino=date(2026, 12, 20),
                cooperacao_nacional_internacional="Não",
                observacoes="",
            )
        RegAfcctPedidoPi.objects.create(
            competencia_mensal=af_fev,
            titulo_pi="Protocolo QKD Híbrido",
            codigo_projeto="QIN-AFCCT-2026-1-9-1",
            tipo_pi="Patente - Invenção",
            data_pedido=date(2026, 2, 12),
            numero_pedido_inpi="BR102026000999",
            link="",
            observacoes="",
        )
        RegAfcctPublicacao.objects.create(
            competencia_mensal=af_fev,
            titulo_publicacao="Post-Quantum TLS Benchmarks",
            codigo_projeto="QIN-AFCCT-2026-1-9-1",
            data_publicacao_aceite=date(2026, 2, 22),
            titulo_periodico="IEEE Quantum Engineering",
            classificacao_periodico="A1",
            autores="Nogueira, P.; Santos, L.",
            outras_informacoes="v. 7",
            link="https://ieee.local/pqc",
            observacoes="",
        )
        RegAfcctProjetoFormacao.objects.create(
            competencia_mensal=af_jan,
            titulo="Capacitação Interna em Criogenia",
            objetivo="Treinar equipe interna do CC.",
            descricao_publica="Operação de refrigeradores de diluição.",
            status_atual="Concluído",
            valor_total_planejado=Decimal("45000.00"),
            data_inicio=date(2026, 1, 14),
            data_termino=date(2026, 1, 30),
            qtd_iniciaram=10,
            qtd_concluiram=10,
            tipo_formacao="Curso de curta duração",
            onde_realizada="No próprio CC",
            vinculo_linhas_tematicas="Hardware Quântico",
            observacoes="",
        )
        RegAfcctProfissional.objects.create(
            competencia_mensal=af_fev,
            nome_completo="Gabriel Torres",
            cpf="33344455566",
            email="gabriel@cimatec.local",
            codigo_projeto="QIN-AFCCT-FC-CC-2026-1-14-1",
            vinculo_profissional="Quadro de pessoal",
            data_conclusao=date(2026, 1, 30),
            certificado_emitido="Sim (não reconhecido pelo MEC)",
            link_certificados="",
            observacao="Treinamento concluído.",
        )
        RegOutrosComentarios.objects.create(
            competencia_mensal=af_jan,
            arquivo="AFCCT",
            aba="5. Outros comentários",
            comentario="Observação consolidada AFCCT.",
        )

        # ---------------- AT ----------------
        at_jan, at_fev = self.comps["AT"]
        RegAtAtividade.objects.create(
            competencia_mensal=at_jan,
            titulo="Workshop de Roadmap Quântico para Associadas",
            associadas_participantes="ÓpticaLab, Energia S.A.",
            objetivo="Alinhar demandas industriais.",
            descricao_publica="Sessões técnicas com empresas associadas.",
            status_atual="Concluído",
            valor_executado=Decimal("35000.00"),
            origem_valor="Valor da AT",
            data_inicio=date(2026, 1, 25),
            data_termino=date(2026, 1, 26),
            observacoes="Sucesso absoluto.",
        )
        RegAtProspeccao.objects.create(
            competencia_mensal=at_fev,
            iniciativa="CC EMBRAPII",
            tipo_interacao="Reunião técnica",
            razao_social="PetroQuímica Sul S.A.",
            nome_fantasia="PetroSul",
            cnpj="77888999000155",
            data_prospeccao=date(2026, 2, 14),
            nomes_contatos="Fernanda Rocha",
            cargo="Gerente de Inovação",
            descricao_resultado="Proposta de associação enviada.",
            proposta_emitida="Sim",
            resultado_proposta="Entidade realizou Associação",
            observacoes="",
        )
        RegOutrosComentarios.objects.create(
            competencia_mensal=at_fev,
            arquivo="AT",
            aba="4. Outros comentários",
            comentario="Comentário consolidado AT.",
        )

    def _ler_celulas(self, wb, aba: str, max_row: int):
        """Lê apenas as primeiras `max_row` linhas em modo streaming read_only."""
        ws = wb[aba]
        cells = {}
        for r_idx, row in enumerate(ws.iter_rows(min_row=1, max_row=max_row, values_only=False), start=1):
            for c_idx, cell in enumerate(row, start=1):
                col = openpyxl.utils.get_column_letter(c_idx)
                cells[f"{col}{r_idx}"] = cell.value
        return cells

    def test_round_trip_integridade_5_arquivos_28_abas(self):
        tags = ("FIN", "FCRH", "ACS", "AFCCT", "AT")
        exported = {}
        for tag in tags:
            tpl_path, _ = TEMPLATE_MAP[tag]
            fname, out_bytes = exportar_planilha_embrapii(self.ciclo, tag)
            exported[tag] = (fname, out_bytes)
            stats = validar_integridade_xlsx(tpl_path, out_bytes)
            self.assertGreater(stats["sheet_protections_preserved"], 0)
            self.assertGreater(stats["ext_lst_blocks_preserved"], 0)
            self.assertGreater(stats["formulas_preserved"], 0)

        # Validar pacote ZIP consolidado
        zip_name, zip_bytes = exportar_pacote_semestral_zip(self.ciclo)
        self.assertTrue(zip_name.endswith(".zip"))
        with ZipFile(BytesIO(zip_bytes), "r") as zf:
            names = zf.namelist()
            self.assertEqual(len(names), 5)
            for tag in tags:
                self.assertIn(exported[tag][0], names)

        # FIN (read_only=True streaming)
        wb_fin = openpyxl.load_workbook(BytesIO(exported["FIN"][1]), read_only=True, data_only=False)
        try:
            sum_fin = self._ler_celulas(wb_fin, "0. Sumário", 25)
            self.assertEqual(sum_fin["J21"], "QuIIN (SENAI CIMATEC)")
            self.assertEqual(sum_fin["J22"], "042/2023-QIN")
            self.assertEqual(sum_fin["J23"], "1º semestre/2026")

            c10 = self._ler_celulas(wb_fin, "10. Conta Ação - Outras Fontes", 22)
            self.assertEqual(c10["C11"], "AFCCT")
            self.assertEqual(c10["D11"], "QIN-PROJ-001")
            self.assertEqual(c10["G11"], "Parceiro Privado & CIMATEC")
            self.assertEqual(c10["C19"], "Ampliação de Infraestrutura")
            self.assertTrue(str(c10["D19"]).startswith("="))

            c11 = self._ler_celulas(wb_fin, "11. Equipe", 13)
            self.assertEqual(c11["C11"], "Dra. Mariana Quântica & Souza")
            self.assertEqual(c11["H11"], 160)

            c12 = self._ler_celulas(wb_fin, "12. Licenciamento de PIs", 13)
            self.assertEqual(c12["C11"], "Algoritmo de Otimização QAOA")
            self.assertTrue(str(c12["I11"]).startswith("="))

            c13 = self._ler_celulas(wb_fin, "13. Acompanhamento Associadas", 15)
            self.assertEqual(c13["C13"], "Indústria Óptica S.A.")
            self.assertEqual(c13["K13"], 50000)
            self.assertTrue(str(c13["O13"]).startswith("=SUM"))

            c14 = self._ler_celulas(wb_fin, "14. Cooperação Nacional", 13)
            self.assertEqual(c14["C11"], "USP São Carlos")
            self.assertTrue(str(c14["G11"]).startswith("="))

            c15 = self._ler_celulas(wb_fin, "15. Cooperação Internacional", 14)
            self.assertEqual(c15["C11"], "Fraunhofer Institute #1")
            self.assertTrue(str(c15["H11"]).startswith("="))
            self.assertIsNotNone(c15["H12"])

            self.assertEqual(self._ler_celulas(wb_fin, "16. Mídia", 12)["C10"], "SENAI CIMATEC inaugura laboratório QuIIN")
            self.assertEqual(self._ler_celulas(wb_fin, "17. Eventos", 12)["C10"], "Quantum LatAm Summit 2026")
            c18 = self._ler_celulas(wb_fin, "18. Conselho Consultivo", 13)
            self.assertEqual(c18["C11"], "Dra. Helena Costa")
            self.assertTrue(str(c18["K11"]).startswith("="))
        finally:
            wb_fin.close()

        # FCRH
        wb_fcrh = openpyxl.load_workbook(BytesIO(exported["FCRH"][1]), read_only=True, data_only=False)
        try:
            self.assertEqual(self._ler_celulas(wb_fcrh, "1. Sumário", 19)["J15"], "QuIIN (SENAI CIMATEC)")
            f2 = self._ler_celulas(wb_fcrh, "2. Info projetos FCRH", 13)
            self.assertEqual(f2["C11"], "Bootcamp Computação Quântica Aplicada")
            self.assertTrue(str(f2["D11"]).startswith("="))
            self.assertEqual(self._ler_celulas(wb_fcrh, "3. Profissionais Capacitados", 12)["C10"], "Lucas Almeida")
            self.assertEqual(
                self._ler_celulas(wb_fcrh, "4. Outros comentários", 12)["B10"],
                "[01/2026] Comentário de janeiro FCRH.\n\n[02/2026] Comentário de fevereiro FCRH.",
            )
        finally:
            wb_fcrh.close()

        # ACS
        wb_acs = openpyxl.load_workbook(BytesIO(exported["ACS"][1]), read_only=True, data_only=False)
        try:
            a2 = self._ler_celulas(wb_acs, "2. Info projetos PD&I ACS", 13)
            self.assertEqual(a2["C11"], "Sensoriamento Quântico com Diamantes NV")
            self.assertTrue(str(a2["D11"]).startswith("="))
            self.assertEqual(self._ler_celulas(wb_acs, "2.1. Pedidos de PI", 12)["C10"], "Magnetômetro NV Compacto")
            self.assertEqual(self._ler_celulas(wb_acs, "2.2. Publicações", 12)["C10"], "NV-Center Magnetometry at Room Temp")
            self.assertEqual(self._ler_celulas(wb_acs, "3. Info projetos Formação", 13)["C11"], "Empreendedorismo DeepTech Quântico")
            self.assertEqual(self._ler_celulas(wb_acs, "4. Profissionais Capacitados", 12)["C10"], "Beatriz Lima")
            a5 = self._ler_celulas(wb_acs, "5. Empresas envolvidas", 12)
            self.assertEqual(a5["C10"], "Qubit Brasil Ltda")
            self.assertTrue(str(a5["N10"]).startswith("="))
            self.assertTrue(str(a5["O10"]).startswith("="))
            self.assertEqual(self._ler_celulas(wb_acs, "6. Outros comentários", 12)["B10"], "[02/2026] Sem intercorrências no ACS.")
        finally:
            wb_acs.close()

        # AFCCT
        wb_af = openpyxl.load_workbook(BytesIO(exported["AFCCT"][1]), read_only=True, data_only=False)
        try:
            af2 = self._ler_celulas(wb_af, "2. Info Projetos PD&I AFCCT", 14)
            self.assertEqual(af2["C11"], "Criptografia Pós-Quântica #1")
            self.assertEqual(af2["H11"], "Eng. João")
            self.assertEqual(af2["C12"], "Criptografia Pós-Quântica #2")
            self.assertTrue(str(af2["H12"]).startswith("="))
            self.assertTrue(str(af2["I12"]).startswith("="))
            self.assertEqual(self._ler_celulas(wb_af, "2.1. Pedidos de PI", 13)["C11"], "Protocolo QKD Híbrido")
            self.assertEqual(self._ler_celulas(wb_af, "2.2. Publicações", 13)["C11"], "Post-Quantum TLS Benchmarks")
            self.assertEqual(self._ler_celulas(wb_af, "3. Info projetos Formação", 13)["C11"], "Capacitação Interna em Criogenia")
            self.assertEqual(self._ler_celulas(wb_af, "4. Profissionais Capacitados", 12)["C10"], "Gabriel Torres")
            self.assertEqual(self._ler_celulas(wb_af, "5. Outros comentários", 12)["B10"], "[01/2026] Observação consolidada AFCCT.")
        finally:
            wb_af.close()

        # AT
        wb_at = openpyxl.load_workbook(BytesIO(exported["AT"][1]), read_only=True, data_only=False)
        try:
            at2 = self._ler_celulas(wb_at, "2. Info atividades AT", 13)
            self.assertEqual(at2["C11"], "Workshop de Roadmap Quântico para Associadas")
            self.assertTrue(str(at2["D11"]).startswith("="))
            self.assertTrue(str(at2["K11"]).startswith("="))
            self.assertTrue(str(at2["L11"]).startswith("="))
            self.assertEqual(self._ler_celulas(wb_at, "3. Prospecção", 12)["C10"], "CC EMBRAPII")
            self.assertEqual(self._ler_celulas(wb_at, "4. Outros comentários", 12)["B10"], "[02/2026] Comentário consolidado AT.")
        finally:
            wb_at.close()

    def test_arquivos_originais_mockup_nao_modificados(self):
        manifest = json.loads((TEMPLATES_DIR / "manifest.json").read_text(encoding="utf-8"))
        mockup_dir = Path(settings.BASE_DIR) / "mockup" / "exemplos_arquivos" / "PREST_SEMESTRAL"
        for _tag, item in manifest.items():
            orig = mockup_dir / item["original_filename"]
            self.assertTrue(orig.exists(), f"Original ausente: {orig}")
            digest = hashlib.sha256(orig.read_bytes()).hexdigest()
            self.assertEqual(digest, item["sha256"], f"Original alterado: {orig}")


    def test_resolver_template_path_usa_fallback_mockup_quando_template_padrao_ausente(self):
        from unittest.mock import patch
        from apps.semestral import xlsx_exporter

        fake_missing_map = {
            tag: (Path("/caminho/inexistente") / path.name, pattern)
            for tag, (path, pattern) in xlsx_exporter.TEMPLATE_MAP.items()
        }
        with patch.object(xlsx_exporter, "TEMPLATE_MAP", fake_missing_map):
            for tag in ("FIN", "FCRH", "ACS", "AFCCT", "AT"):
                resolved = xlsx_exporter.resolver_template_path(tag)
                self.assertTrue(resolved.is_file(), f"Fallback não encontrado para {tag}: {resolved}")
                self.assertEqual(resolved.parent, xlsx_exporter.FALLBACK_TEMPLATES_DIR)
            _nome, dados = exportar_planilha_embrapii(self.ciclo, "AFCCT")
            self.assertGreater(len(dados), 10000)
