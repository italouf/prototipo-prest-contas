# Upload e Ingestão de Prestação de Contas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir upload dos três Excel oficiais de prestação de contas, extrair/validar/gravar seus dados de forma idempotente e usar esses snapshots para substituir as duas bases do painel anual, com override manual auditado.

**Architecture:** Novo app Django `apps/accountability` com snapshots por `(centro, periodo_referencia)`; parsers `openpyxl` read-only puro (sem banco); serviço `ingestar()` que valida tudo antes de gravar e apaga/recria somente os fatos da fonte enviada dentro de uma transação; `panel.py` devolve o mesmo DTO de `planning.services.painel()` para o template não mudar; overrides ficam numa tabela própria ligada ao acompanhamento.

**Tech Stack:** Django 5.2, openpyxl 3.1.5 (já em `requirements.txt`), SQLite/Postgres, Django templates + HTMX/Alpine, `django.test.TestCase`.

**Spec:** `docs/superpowers/specs/2026-09-29-upload-ingestao-prestacao-design.md` — o plano argumenta a partir dele; leia ambos.

## Global Constraints

- Python 3.11+, Django 5.2.17, openpyxl 3.1.5 — **não** adicionar pandas, FastAPI, Pydantic ou qualquer dependência nova.
- Ler Excel apenas com `openpyxl.load_workbook(..., read_only=True, data_only=True)`; nunca `eval`, fórmulas ou macros.
- Nenhum hex de cor novo, nenhum CDN, sem dependência de Node em runtime (RNF-011/RNF-003).
- Permissões validadas na view (backend), nunca só no template (RNF-004).
- Valores monetários sempre `Decimal`; vazio ⇒ `NULL`, nunca `0` implícito.
- Mensagens de erro em pt-BR citando aba/célula/linha; padrão do projeto.
- `AT_LEI_TICS` nunca é somada em `AT` (REGRA DURA).
- Unidades diferentes nunca são somadas; sem correspondência ⇒ `—`.
- Não alterar `Periodo`, `FinanceiroConsolidado`, `Lancamento`, `PlanoAnual` (modelos e registros preservados).
- Comandos usam a venv do projeto: `.\.venv\Scripts\python.exe manage.py ...` (Windows).
- Não fazer commit de `db.sqlite3`, `media/`, `test-results/`.

## Review Focus

Estas são as entradas/falhas que o SDD implica mas que nenhum teste óbvio cobre; cada uma tem seu teste no task dono:

1. **Reenviar o mesmo arquivo** não pode duplicar fatos — `test_reenvio_do_mesmo_arquivo_nao_duplica` (Task 5).
2. **Falha no meio da gravação** não pode deixar fatos parciais — `test_falha_na_gravacao_faz_rollback_total` (Task 5).
3. **Reimportar uma fonte** não pode apagar as outras (`FINANCEIRO_GERAL` vs `INDICADORES_PE`) — `test_reimportar_uma_fonte_preserva_as_demas` (Task 5).
4. **Base física sem executado (2026/2027)** precisa exibir `—`, não `0%`/"Execução crítica" — `test_kpi_sem_executado_no_ano_exibe_traco` (Task 7).
5. **Banco sem acompanhamento** (seed/testes atuais) precisa continuar caindo no painel legado `PlanoAnual` — `test_painel_sem_acompanhamento_usa_plano_legado` (Task 7).
6. **`6.1 Lei TICs`** não pode vazar para `AT` — `test_lei_tics_segregada_do_at` (Task 4).
7. **Metadado divergente entre abas do v2** deve bloquear o lote — `test_metadados_divergentes_entre_abas_rejeitam` (Task 4).

---

### Task 1: App `apps/accountability` + modelos + migração

**Files:**
- Create: `apps/accountability/__init__.py`
- Create: `apps/accountability/apps.py` (`AccountabilityConfig`, `name = "apps.accountability"`, `verbose_name = "Prestação de contas"`)
- Create: `apps/accountability/models.py`
- Create: `apps/accountability/admin.py`
- Create: `apps/accountability/tests/__init__.py`
- Create: `apps/accountability/tests/test_models.py`
- Modify: `config/settings.py:32-46` (inserir `"apps.accountability"` após `"apps.finance"`)
- Create: `apps/accountability/migrations/0001_initial.py` (via `makemigrations`)

**Interfaces:**
- Consumes: `apps.pillars.models.Pilar`, `apps.indicators.models.Indicador` (não usado aqui), `settings.AUTH_USER_MODEL`.
- Produces (requisitados pelos Tasks 2–8): `CentroCompetencia`, `Acompanhamento`, `ImportacaoAcompanhamento`, `ResumoFinanceiro`, `ProjetoFinanceiro`, `KpiAcompanhamento`, `DespesaAcompanhamento`, `OverrideAcompanhamento`, `TIPOS_FONTE`.

- [ ] **Step 1: Write the failing tests**

`apps/accountability/tests/test_models.py`:

```python
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.pillars.models import Pilar
from .models import Acompanhamento, CentroCompetencia, KpiAcompanhamento, OverrideAcompanhamento


class AcompanhamentoUnicidadeTestes(TestCase):
    def test_centro_e_periodo_referencia_sao_unicos(self):
        centro = CentroCompetencia.objects.create(codigo="quiin", nome="QuIIN")
        Acompanhamento.objects.create(centro=centro, periodo_referencia="2T/2024")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Acompanhamento.objects.create(centro=centro, periodo_referencia="2T/2024")

    def test_mesmo_periodo_para_centros_diferentes_e_permitido(self):
        Acompanhamento.objects.create(
            centro=CentroCompetencia.objects.create(codigo="quiin", nome="QuIIN"),
            periodo_referencia="2T/2024")
        Acompanhamento.objects.create(
            centro=CentroCompetencia.objects.create(codigo="outro-cc", nome="Outro CC"),
            periodo_referencia="2T/2024")
        self.assertEqual(Acompanhamento.objects.count(), 2)


class OverrideChaveTestes(TestCase):
    def setUp(self):
        self.acomp = Acompanhamento.objects.create(
            centro=CentroCompetencia.objects.create(codigo="quiin", nome="QuIIN"),
            periodo_referencia="2T/2024")
        self.pilar = Pilar.objects.create(codigo="PDI", nome="PDI")

    def test_chave_unica_para_mesmo_acompanhamento(self):
        pilar = self.pilar
        OverrideAcompanhamento.objects.create(
            acompanhamento=self.acomp, base="financeiro", pilar=pilar,
            ano=2026, campo="executado", valor=10, chave="fin|PDI|2026|executado")
        with self.assertRaises(IntegrityError), transaction.atomic():
            OverrideAcompanhamento.objects.create(
                acompanhamento=self.acomp, base="financeiro", pilar=pilar,
                ano=2026, campo="executado", valor=11, chave="fin|PDI|2026|executado")

    def test_override_fisico_exige_kpi_e_rejeita_pilar(self):
        kpi = KpiAcompanhamento.objects.create(
            acompanhamento=self.acomp, codigo="PE-01", sequencia=1,
            nome="Projetos de PD&I", unidade="Número absoluto", pilar=self.pilar)
        objeto = OverrideAcompanhamento(
            acompanhamento=self.acomp, base="fisico", kpi=kpi,
            ano=2025, campo="executado", valor=5, chave="fis|PE-01|2025|executado")
        objeto.full_clean()

        invalido = OverrideAcompanhamento(
            acompanhamento=self.acomp, base="fisico",
            ano=2025, campo="executado", valor=5, chave="fis|?|2025|executado")
        with self.assertRaises(ValidationError):
            invalido.full_clean()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe manage.py test apps.accountability -v 2`
Expected: FAIL with `ModuleNotFoundError: No module named 'apps.accountability'`

- [ ] **Step 3: Implement the models**

`apps/accountability/models.py` com os oito modelos e `TIPOS_FONTE` do SDD §3.
Regras fixas: `DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)`
para valores; `percentual*` com `max_digits=10, decimal_places=6, null=True`;
`Acompanhamento` com `UniqueConstraint(fields=["centro","periodo_referencia"],
name="uniq_centro_periodo_acompanhamento")`; `OverrideAcompanhamento.clean()`
valida base↔pilar/kpi (SDD §3) e `chave` é preenchida pelo chamador.
Adicione `"apps.accountability"` em `config/settings.py`.

- [ ] **Step 4: Create and run the migration**

Run: `.\.venv\Scripts\python.exe manage.py makemigrations accountability`
Expected: `0001_initial.py` criado com os 8 modelos

Run: `.\.venv\Scripts\python.exe manage.py migrate`
Expected: `Applying accountability.0001_initial... OK`

- [ ] **Step 5: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe manage.py test apps.accountability -v 2`
Expected: PASS (4 testes)

- [ ] **Step 6: Register models in `apps/accountability/admin.py`**

`list_display` curto por modelo (acompanhamento, origem/aba, valores-chave) para
conferência manual no admin.

- [ ] **Step 7: Commit**

```bash
git add apps/accountability config/settings.py
git commit -m "feat(prestacao): app accountability com modelos de ingestao e override"
```

---

### Task 2: Parser de `FINANCEIRO GERAL.xlsx`

**Files:**
- Create: `apps/accountability/parsers/__init__.py`
- Create: `apps/accountability/parsers/comum.py`
- Create: `apps/accountability/parsers/financeiro_geral.py`
- Test: `apps/accountability/tests/test_parsers_financeiro.py`

**Interfaces:**
- Consumes: modelos do Task 1 apenas como *shape* de dict (parser não toca no banco).
- Produces:
  - `comum.normalizar(texto: object) -> str` (minúsculas, sem acento, espaços colapsados)
  - `comum.para_decimal(valor: object) -> Decimal | None` (bool⇒None, `Decimal(str(v))`, texto BR, `#REF!`/`#VALUE!`⇒None)
  - `comum.PAYLOAD_VAZIO: dict` — `{"metadados": {"centro": None, "periodo_referencia": None, "termo": None}, "resumos": [], "projetos": [], "kpis": [], "despesas": [], "avisos": [], "erros": []}`
  - `financeiro_geral.parse_financeiro_geral(caminho) -> dict` (mesmo shape de `PAYLOAD_VAZIO`)

- [ ] **Step 1: Write the failing test**

`apps/accountability/tests/test_parsers_financeiro.py`:

```python
from decimal import Decimal
from pathlib import Path

from apps.accountability.parsers.comum import normalizar, para_decimal
from apps.accountability.parsers.financeiro_geral import parse_financeiro_geral

ARQUIVO = (Path(__file__).resolve().parents[3] / "mockup" / "exemplos_arquivos"
           / "FINANCEIRO GERAL.xlsx")


def _resumo(payload, origem, codigo_pilar, ano=None):
    return next(r for r in payload["resumos"]
                if r["origem"] == origem and r["pilar"] == codigo_pilar and r["ano"] == ano)


def _projetos(payload, origem):
    return [p for p in payload["projetos"] if p["origem"] == origem]


class ParseFinanceiroGeralTestes:
    @classmethod
    def setup_class(cls):
        cls.p = parse_financeiro_geral(ARQUIVO)

    def test_linha_de_senhas(self):
        assert para_decimal("1.234,56") == Decimal("1234.56")
        assert para_decimal("#REF!") is None
        assert normalizar("  AFCCT / PD&I ") == "afcct / pd&i"

    def test_tab1_resumo_por_pilar(self):
        pdi = _resumo(self.p, "TAB. 1", "PDI")
        assert pdi["recurso_ou_meta"] == Decimal("29000000")
        assert pdi["realizado"] == Decimal("17675109.56")
        assert _resumo(self.p, "TAB. 1", "FORMACAO")["realizado"] == Decimal("7749636.72")
        assert _resumo(self.p, "TAB. 1", "STARTUPS")["realizado"] == Decimal("2251069.32")
        assert _resumo(self.p, "TAB. 1", "INFRA")["realizado"] == Decimal("7299414.35")

    def test_totais_de_reconciliacao_sao_linhas_distintas(self):
        assert _resumo(self.p, "TAB. 3", "PDI")["realizado"] == Decimal("17675109.56")
        assert _resumo(self.p, "TAB. 5", "FORMACAO")["realizado"] == Decimal("7749636.72")
        assert _resumo(self.p, "TAB. 8", "STARTUPS")["realizado"] == Decimal("2251069.32")

    def test_tab9_at_e_outras_fontes(self):
        at = _resumo(self.p, "TAB. 9", "AT")
        assert at["recurso_ou_meta"] == Decimal("7750000")
        assert at["captado"] == Decimal("5616700")
        assert at["captado_anos_1_2"] == Decimal("346200")
        assert at["realizado"] == Decimal("220597")
        assert _resumo(self.p, "TAB. 9", "OUTRASFONTES")["captado"] == Decimal("10226768")

    def test_totais_gerais_nao_geram_linha_de_pilar(self):
        assert not [r for r in self.p["resumos"] if r["pilar"] == "TOTAL"]

    def test_projetos_por_bloco(self):
        assert len(_projetos(self.p, "TAB. 2")) == 18
        assert len(_projetos(self.p, "TAB. 4")) == 8
        assert len(_projetos(self.p, "TAB. 6")) == 7
        primeiro = _projetos(self.p, "TAB. 2")[0]
        assert primeiro["nome"] == "Pós Processamento"
        assert primeiro["status"] == "Encerrado"
        assert primeiro["orcado"] == Decimal("3799447.4")
        assert primeiro["realizado"] == Decimal("3795618")

    def test_sem_valores_anuais_emite_aviso(self):
        assert not [r for r in self.p["resumos"] if r["ano"] is not None]
        assert any("TAB. 1.1" in a for a in self.p["avisos"])

    def test_tab7_ausente_gera_aviso_e_nao_erro(self):
        assert any("TAB. 7" in a for a in self.p["avisos"])
        assert self.p["erros"] == []

    def test_cabecalho_inesperado_vira_erro_com_linha(self, tmp_path):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "FINANCEIRO "
        ws["C1"] = "TAB. 1 - VISÃO CONSOLIDADA"
        ws["C3"] = "COLOCA ERRADA"
        ws["C5"] = "AFCCT / PD&I"
        ws["D5"] = 29000000
        caminho = tmp_path / "errado.xlsx"
        wb.save(caminho)
        p = parse_financeiro_geral(caminho)
        assert p["erros"], "cabeçalho divergente deve virar erro"
        assert any("TAB. 1" in e for e in p["erros"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe manage.py test apps.accountability.tests.test_parsers_financeiro -v 2`
Expected: FAIL with `ModuleNotFoundError: No module named 'apps.accountability.parsers'`

- [ ] **Step 3: Implement `comum.py`**

Normalização/decisão de tipo conforme Interfaces; além disso
`comum.abrir_workbook(caminho)` devolve o workbook `read_only=True, data_only=True`
e `comum.eh_erro_formula(valor)` (`True` para strings iniciadas por `#`).
Erros de leitura do openpyxl são convertidos em `ArquivoInvalidoError(message)`
(nova exceção em `comum.py`).

- [ ] **Step 4: Implement `parse_financeiro_geral(caminho)`**

Estratégia (o SDD §4 fixa células; a implementação valida antes de ler):

1. Abre a workbook e exige exatamente uma aba cujo `normalizar(title)`
   comece com `"financeiro"` — senão `erros.append(...)` e retorna o payload.
2. Percorre as linhas buscando rótulos normalizados:
   `tab. 1`/`tab. 1.1`/`tab. 3`/`tab. 5`/`tab. 8`/`tab. 9` e os títulos de projeto
   (`tab. 2`/`tab. 4`/`tab. 6`). Guarda a linha do título e a linha do cabeçalho
   de colunas logo abaixo.
3. Confere o cabeçalho esperado (`C{cabecalho}` = `ação`/`projeto`/`pilar`);
   se divergir, `erros.append("Aba ...: cabeçalho esperado ... na linha N")`.
4. Lê os blocos pelas colunas posicionais da tabela do SDD §4, com
   `para_decimal()`, e monta dicts de `resumos`/`projetos`.
5. Para cada bloco de projeto, itera de `cabecalho+2` até a primeira célula `C`
   cujo `normalizar` comece com `"total"`; valida a coluna de nome não vazia.
6. TAB. 1.1: só cria linhas `ano` se algum de `O:S` for não-nulo no pilar; se
   nenhuma linha anual for criada, `avisos.append("TAB. 1.1 sem valores anuais por pilar; a visão anual exibirá —")`.
7. TAB. 7 nunca é exigida: se não encontrada, `avisos.append("TAB. 7 não encontrada; ignorada.")`.
8. Rótulo de pilar desconhecido ⇒ `erros.append(...)` apontando célula.

- [ ] **Step 5: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe manage.py test apps.accountability.tests.test_parsers_financeiro -v 2`
Expected: PASS (9 testes)

- [ ] **Step 6: Commit**

```bash
git add apps/accountability/parsers apps/accountability/tests/test_parsers_financeiro.py
git commit -m "feat(prestacao): parser do FINANCEIRO GERAL com mapas tabulares"
```

---

### Task 3: Parser de `Indicadores Gerais do Termo de Retificação do PE.xlsx`

**Files:**
- Create: `apps/accountability/parsers/indicadores_pe.py`
- Test: `apps/accountability/tests/test_parsers_indicadores.py`

**Interfaces:**
- Consumes: `comum.normalizar`, `comum.para_decimal`, `comum.PAYLOAD_VAZIO`.
- Produces: `indicadores_pe.parse_indicadores_pe(caminho) -> dict` (mesmo shape; preenche `kpis`).

- [ ] **Step 1: Write the failing test**

```python
from decimal import Decimal
from pathlib import Path

from apps.accountability.parsers.indicadores_pe import parse_indicadores_pe

ARQUIVO = (Path(__file__).resolve().parents[3] / "mockup" / "exemplos_arquivos"
           / "Indicadores Gerais do Termo de Retificação do PE.xlsx")


class ParseIndicadoresPeTestes:
    @classmethod
    def setup_class(cls):
        cls.p = parse_indicadores_pe(ARQUIVO)

    def test_dez_kpis_com_codigos_estaveis(self):
        assert [k["codigo"] for k in self.p["kpis"]] == [f"PE-{i:02d}" for i in range(1, 11)]

    def test_kpi1_valores_exatos(self):
        kpi = self.p["kpis"][0]
        assert kpi["nome"].startswith("Projetos de PD&I desenvolvidos")
        assert kpi["pilar"] == "PDI"
        assert kpi["unidade"] == "Número absoluto"
        assert [kpi[f"meta_{ano}"] for ano in (2024, 2025, 2026, 2027)] == [
            Decimal("5"), Decimal("5"), Decimal("5"), Decimal("3")]
        assert kpi["meta_total"] == Decimal("18")
        assert kpi["executado_2024"] == Decimal("5")
        assert kpi["executado_2025"] == Decimal("10")
        assert kpi["acumulado"] == Decimal("15")
        assert kpi["gap"] == Decimal("-3")
        assert kpi["projecao_2026"] == Decimal("2")
        assert kpi["projecao_2027"] == Decimal("0")

    def test_acoes_mapeadas_para_os_pilares_internos(self):
        por_pilar = {k["codigo"]: k["pilar"] for k in self.p["kpis"]}
        assert por_pilar["PE-01"] == "PDI"
        assert por_pilar["PE-02"] == "OUTRASFONTES"
        assert por_pilar["PE-03"] == "AT"
        assert por_pilar["PE-05"] == "STARTUPS"
        assert por_pilar["PE-07"] == "FORMACAO"
        assert por_pilar["PE-10"] == "INFRA"

    def test_arquivo_real_nao_gera_erro(self):
        assert self.p["erros"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe manage.py test apps.accountability.tests.test_parsers_indicadores -v 2`
Expected: FAIL com `ModuleNotFoundError: No module named 'apps.accountability.parsers.indicadores_pe'`

- [ ] **Step 3: Implement `parse_indicadores_pe(caminho)`**

Exige uma aba cujo `normalizar(title)` contenha `head - indicadores`. Localiza a
linha de cabeçalho procurando a célula `B` com `número`/`nº` e a célula
`INDICADORES`; dados começam 2 linhas abaixo (linha 4 no arquivo atual) e
terminam quando `B`/`C` estiverem vazios. Mapeia colunas `B..Q` conforme SDD §5.
`ACOES_PILAR` é dict normalizado→código de pilar; ação fora do dict ⇒
`erros.append(f"Indicadores: ação '{valor}' (linha {n}) sem pilar correspondente.")`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe manage.py test apps.accountability.tests.test_parsers_indicadores -v 2`
Expected: PASS (4 testes)

- [ ] **Step 5: Commit**

```bash
git add apps/accountability/parsers/indicadores_pe.py apps/accountability/tests/test_parsers_indicadores.py
git commit -m "feat(prestacao): parser dos indicadores do Termo de Retificacao"
```

---

### Task 4: Parser de `Acompanhamento Financeiro (v2).xlsx`

**Files:**
- Create: `apps/accountability/parsers/acompanhamento_v2.py`
- Test: `apps/accountability/tests/test_parsers_acompanhamento.py`
- Fixture (gerada no teste): workbook sintético com as 8 abas financeiras

**Interfaces:**
- Consumes: `comum.normalizar`, `comum.para_decimal`, `comum.abrir_workbook`, `comum.eh_erro_formula`, `PAYLOAD_VAZIO`.
- Produces:
  - `acompanhamento_v2.ABAS_DESPESA: dict[str, tuple[str, str]]` (aba → (pilar, tipo_recurso))
  - `acompanhamento_v2.parse_acompanhamento_v2(caminho) -> dict` — preenche `metadados` (centro, periodo_referencia, termo), `despesas` e `avisos`/`erros`.

- [ ] **Step 1: Write the failing test com fixture sintética**

```python
from decimal import Decimal
from pathlib import Path
import tempfile

from openpyxl import Workbook

from apps.accountability.parsers.acompanhamento_v2 import parse_acompanhamento_v2

RAIZ = Path(__file__).resolve().parents[3]
REAL = RAIZ / "Acompanhamento Financeiro (v2).xlsx"

def _cabecalho_metadados(ws, deslocamento=0):
    base = 5 + deslocamento
    ws.cell(base, 4, "Centro de Competência EMBRAPII:")
    ws.cell(base, 5, "Centro de Competência Embrapii CIMATEC em Tecnologias Quânticas - Quiin")
    ws.cell(base + 1, 4, "Termo de Cooperação N°:")
    ws.cell(base + 1, 5, "053/2023")
    ws.cell(base + 2, 4, "Período de Referência do Acompanhamento:")
    ws.cell(base + 2, 5, "2T/2024")


CABECALHOS = {
    "3. Conta Ação - AFCCT": (10, ["Linha", "Informação do código do projeto de AFCCT",
                                   "Conta do projeto", "Tipo de despesa", "Credor",
                                   "Data do pagamento", "Valor (R$)"],
                              [1, "PDI-01", "AFCCT-01", "Serviço", "Fornecedor X", "15/04/2024", 123.45]),
    "4. Conta Ação - FCRH": (9, ["Linha", "Informação do código do projeto de FCRH",
                                 "Tipo de despesa", "Credor", "Número da Nota Fiscal ou Invoice",
                                 "Data da Nota Fiscal ou Invoice", "Data do pagamento", "Valor (R$)"],
                             [1, "FCRH-01", "Bolsa", "Fornecedor Y", "NF-100", "01/04/2024",
                              "15/04/2024", 123.45]),
    "5. Conta Ação - ACS": (9, ["Linha", "Informação do código do projeto de ACS",
                                "Marco do projeto, se aplicável", "Credor",
                                "Data do pagamento", "Valor (R$)"],
                            [1, "ACS-01", "M1", "Fornecedor Z", "15/04/2024", 123.45]),
    "6. Conta Ação - AT": (10, ["Linha", "Informar a qual ação está relacionada",
                                "Informar o código do projeto/atividade", "Tipo de despesa",
                                "Entidade que realizou o aporte", "Descrição", "Data", "Valor (R$)"],
                           [1, "Associação", "AT-01", "Aporte", "Empresa A", "Aporte", "15/04/2024", 123.45]),
    "6.1 Conta Ação - AT (Lei TICs)": (10, ["Linha", "Informar a qual ação está relacionada",
                                            "Informar o código do projeto/atividade", "Tipo de despesa",
                                            "Entidade que realizou o aporte", "Descrição",
                                            "Data", "Valor (R$)"],
                                       [1, "Associação", "AT-02", "Aporte", "Empresa B", "Aporte",
                                        "15/04/2024", 123.45]),
    "7. Conta Ação - Outras Fontes": (10, ["Linha", "Informar a qual ação está relacionada",
                                           "Informar o código do projeto/atividade", "Tipo de despesa",
                                           "Entidade que realizou o aporte", "Descrição",
                                           "Data", "Valor (R$)"],
                                      [1, "Outra fonte", "OF-01", "Aporte", "Empresa C", "Aporte",
                                       "15/04/2024", 123.45]),
    "8. Conta Ação - Infraestrutura": (10, ["Linha", "Tipo de despesa", "Fornecedor – estrangeiro?",
                                            "Nome (Fornecedor)", "CNPJ (Fornecedor)",
                                            "Número da Nota ou Invoice", "Data da Nota Fiscal ou Invoice",
                                            "Data do pagamento",
                                            "Valor da Nota Fiscal ou Invoice (RS)", "Observações"],
                                       [1, "Equipamento", "Não", "Fornecedor D", "11.222.333/0001-44",
                                        "NF-200", "01/04/2024", "15/04/2024", 123.45, "ok"]),
    "9. Ampliação de Infraestrutura": (9, ["Linha", "Descrição do item", "Categoria do item",
                                           "Fonte Recurso", "Quantidade",
                                           "Valor unitário do item na Nota Fiscal ou Invoice (R$)",
                                           "Valor total dos itens na Nota Fiscal ou Invoice (R$)",
                                           "Número patrimonial do bem", "Observações"],
                                      [1, "Servidor", "TI", "EMBRAPII", 2, 61.725, 123.45, "PAT-9", "ok"]),
}


def _workbook_despesas():
    wb = Workbook()
    wb.remove(wb.active)
    ws0 = wb.create_sheet("0. Sumário")
    _cabecalho_metadados(ws0, deslocamento=14)
    for nome, (linha_cab, cabecalhos, dados) in CABECALHOS.items():
        aba = wb.create_sheet(nome)
        _cabecalho_metadados(aba)
        for i, texto in enumerate(cabecalhos, start=1):
            aba.cell(linha_cab, i, texto)
        for i, valor in enumerate(dados, start=1):
            aba.cell(linha_cab + 1, i, valor)
        aba.cell(linha_cab + 2, 1, 2)   # só o número sequencial: encerra a leitura
        aba.cell(40, 15, "#REF!")       # coluna não mapeada: vira aviso, nunca erro
    return wb


class ParseAcompanhamentoV2Testes:
    def test_metadados_do_arquivo_real(self):
        p = parse_acompanhamento_v2(REAL)
        assert p["erros"] == []
        assert p["metadados"]["centro"].startswith("Centro de Competência Embrapii CIMATEC")
        assert p["metadados"]["termo"] == "053/2023"
        assert p["metadados"]["periodo_referencia"] == "2T/2024"

    def test_arquivo_real_sem_lancamentos_nao_gera_erro(self):
        p = parse_acompanhamento_v2(REAL)
        assert p["despesas"] == []
        assert p["erros"] == []

    def test_fixture_gera_uma_despesa_por_aba(self, tmp_path):
        caminho = tmp_path / "v2.xlsx"
        _workbook_despesas().save(caminho)
        p = parse_acompanhamento_v2(caminho)
        assert p["erros"] == []
        assert len(p["despesas"]) == 8
        por_aba = {d["aba"]: d for d in p["despesas"]}
        assert por_aba["3. Conta Ação - AFCCT"]["pilar"] == "PDI"
        assert por_aba["3. Conta Ação - AFCCT"]["codigo_projeto"] == "PDI-01"
        assert por_aba["4. Conta Ação - FCRH"]["numero_nota"] == "NF-100"
        assert por_aba["4. Conta Ação - FCRH"]["data_nota"].isoformat() == "2024-04-01"
        assert por_aba["5. Conta Ação - ACS"]["pilar"] == "STARTUPS"
        assert por_aba["7. Conta Ação - Outras Fontes"]["pilar"] == "OUTRASFONTES"
        assert por_aba["8. Conta Ação - Infraestrutura"]["documento"] == "11.222.333/0001-44"
        assert por_aba["8. Conta Ação - Infraestrutura"]["credor"] == "Fornecedor D"
        assert por_aba["9. Ampliação de Infraestrutura"]["valor"] == Decimal("123.45")
        assert por_aba["9. Ampliação de Infraestrutura"]["valor_unitario"] == Decimal("61.725")
        assert por_aba["9. Ampliação de Infraestrutura"]["quantidade"] == Decimal("2")
        assert por_aba["9. Ampliação de Infraestrutura"]["numero_patrimonial"] == "PAT-9"
        assert all(d["valor"] == Decimal("123.45") for d in p["despesas"])
        assert not [d for d in p["despesas"] if d["linha"] > 11]

    def test_lei_tics_segregada_do_at(self, tmp_path):
        caminho = tmp_path / "v2.xlsx"
        _workbook_despesas().save(caminho)
        p = parse_acompanhamento_v2(caminho)
        tipos = {d["aba"]: d["tipo_recurso"] for d in p["despesas"]}
        assert tipos["6. Conta Ação - AT"] == "AT"
        assert tipos["6.1 Conta Ação - AT (Lei TICs)"] == "AT_LEI_TICS"

    def test_metadados_divergentes_entre_abas_rejeitam(self, tmp_path):
        caminho = tmp_path / "v2.xlsx"
        wb = _workbook_despesas()
        wb["3. Conta Ação - AFCCT"].cell(7, 5, "3T/2024")
        wb.save(caminho)
        p = parse_acompanhamento_v2(caminho)
        assert p["erros"], "divergência de metadado deve virar erro"
        assert any("AFCCT" in e for e in p["erros"])

    def test_aba_obrigatoria_ausente_gera_erro_amigavel(self, tmp_path):
        caminho = tmp_path / "v2.xlsx"
        wb = _workbook_despesas()
        wb.remove(wb["6.1 Conta Ação - AT (Lei TICs)"])
        wb.save(caminho)
        p = parse_acompanhamento_v2(caminho)
        assert any("6.1 Conta Ação - AT (Lei TICs)" in e for e in p["erros"])

    def test_celula_obrigatoria_invalida_aponta_linha_e_coluna(self, tmp_path):
        caminho = tmp_path / "v2.xlsx"
        wb = _workbook_despesas()
        wb["3. Conta Ação - AFCCT"].cell(11, 17, "#REF!")
        wb.save(caminho)
        p = parse_acompanhamento_v2(caminho)
        assert any("AFCCT" in e and "linha" in e.lower() for e in p["erros"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe manage.py test apps.accountability.tests.test_parsers_acompanhamento -v 2`
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 3: Implement metadados por rótulo**

`_ler_metadados(wb)`: para `0. Sumário` (fonte primária) e depois para cada aba
de `ABAS_DESPESA` presente, varre as 12 primeiras linhas procurando célula cujo
`normalizar` comece por `centro de competência`, `termo de cooperação` ou
`período de referência`; valor = próxima célula não vazia à direita. Divergência
entre a fonte primária e uma aba ⇒ `erros.append(f"Metadado divergente em '{aba}' ({coord}): ...")`.
Registro lido é anotado com `(aba, coordenada)` para a mensagem apontar a célula.

- [ ] **Step 4: Implement leitura das 8 abas de despesa**

1. Toda aba de `ABAS_DESPESA` ausente ⇒ `erros.append(f'A aba "{nome}" não foi encontrada. Verifique se é o template correto da EMBRAPII.')`.
2. Cabeçalho = linha com célula `Linha` (normalizada) nas 20 primeiras linhas;
   ausente ⇒ erro citando aba e linha esperada.
3. Monta `colunas: dict[campo, indice_zero_based]` aplicando as 23 regras
   **em ordem** do SDD §6 sobre o texto normalizado do cabeçalho.
4. Itera a partir de `cabecalho+1`; para cada linha monta o dict de despesa
   com `aba`, `linha` (número da linha da planilha), `pilar`, `tipo_recurso`
   (de `ABAS_DESPESA`) e os campos; **encerra** na primeira linha em que nenhum
   campo mapeado (além de `sequencia`) tenha valor.
5. `valor`/`quantidade`/`valor_unitario` usam `para_decimal`; datas usam
   `comum.parse_data` (novo em `comum.py`: `date | datetime | serial Excel |
   dd/mm/aaaa | aaaa-mm-dd`, retornando `None` para inválido).
6. Campo obrigatório (`valor`) com valor não convertível ⇒
   `erros.append(f"{aba}: linha {n}, coluna {coluna}: valor inválido ...")`.
   Campos opcionais vazios viram `None` sem gerar erro.
7. Nenhuma aba reconhecida como pertencente ao template v2 ⇒ erro de tipo
   ("não foi possível identificar o tipo de arquivo").

- [ ] **Step 5: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe manage.py test apps.accountability.tests.test_parsers_acompanhamento -v 2`
Expected: PASS (7 testes)

- [ ] **Step 6: Commit**

```bash
git add apps/accountability/parsers apps/accountability/tests/test_parsers_acompanhamento.py
git commit -m "feat(prestacao): parser do Acompanhamento Financeiro v2 com metadados por rotulo"
```

---

### Task 5: Serviço de ingestão atômica + `test_ingestion.py`

**Files:**
- Create: `apps/accountability/services.py`
- Test: `apps/accountability/tests/test_ingestion.py`

**Interfaces:**
- Consumes: parsers dos Tasks 2–4; modelos do Task 1; `apps.audit.services.registrar_auditoria`.
- Produces:
  - `services.IngestaoError(Exception)` — `message` amigável em pt-BR
  - `services.detejar_tipo_arquivo(sheetnames: list[str]) -> str | None` → um de `TIPOS_FONTE`
  - `services.ingestar(tipo_fonte: str, caminho, centro_nome: str, periodo_referencia: str, usuario) -> ImportacaoAcompanhamento`
  - `services.VALIDADORES: dict[str, tuple[str, ...]]` — tipo_fonte → abas obrigatórias (`FINANCEIRO_GERAL`→`("FINANCEIRO ",)`, `INDICADORES_PE`→`("HEAD - INDICADORES - EMBRAPII",)`, `ACOMPANHAMENTO_V2`→ as 8 abas de `ABAS_DESPESA`), usada pela UI do Task 6
  - `services.resumo_json(tipo_fonte, caminho, centro, referencia) -> dict` — só parse, sem banco; devolve `{"tipo_fonte", "centro", "periodo_referencia", "contagens", "exemplo_resumo", "avisos"}`, para inspeção manual e para o teste imprimir o resumo extraído

- [ ] **Step 1: Write the failing test**

`apps/accountability/tests/test_ingestion.py` — teste independente que carrega
os arquivos reais, executa o parse, imprime o resumo e compara com valores
esperados extraídos da leitura dos arquivos.

```python
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.pillars.models import Pilar
from . import services
from .models import (Acompanhamento, ImportacaoAcompanhamento, KpiAcompanhamento,
                     ProjetoFinanceiro, ResumoFinanceiro)

RAIZ = Path(__file__).resolve().parents[3]
FINANCEIRO = RAIZ / "mockup" / "exemplos_arquivos" / "FINANCEIRO GERAL.xlsx"
INDICADORES = RAIZ / "mockup" / "exemplos_arquivos" / "Indicadores Gerais do Termo de Retificação do PE.xlsx"
V2 = RAIZ / "Acompanhamento Financeiro (v2).xlsx"

CENTRO = "Centro de Competência Embrapii CIMATEC em Tecnologias Quânticas - Quiin"
REFERENCIA = "2T/2024"


class DeteccaoTipoTestes(TestCase):
    def test_identifica_os_tres_tipos_pelas_abas(self):
        assert services.detejar_tipo_arquivo(["HEAD - INDICADORES - EMBRAPII"]) == "INDICADORES_PE"
        assert services.detejar_tipo_arquivo(["FINANCEIRO "]) == "FINANCEIRO_GERAL"
        assert services.detejar_tipo_arquivo(
            ["0. Sumário", "3. Conta Ação - AFCCT"]) == "ACOMPANHAMENTO_V2"
        assert services.detejar_tipo_arquivo(["Qualquer coisa"]) is None

    def test_arquivo_nao_identificado_vira_erro_amigavel(self):
        with self.assertRaises(services.IngestaoError) as ctx:
            services.ingestar("inventado", V2, CENTRO, REFERENCIA, None)
        self.assertIn("não foi possível identificar", str(ctx.exception))


class IngestaoFinanceiroTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        garantir_grupos()
        User = get_user_model()
        cls.user = adicionar_grupo(
            User.objects.create_user(username="ingest", password="x"), "Master")
        for codigo, nome in (("PDI", "PDI"), ("FORMACAO", "Formação FCRH"),
                             ("STARTUPS", "ACS"), ("INFRA", "Infraestrutura"),
                             ("AT", "AT"), ("OUTRASFONTES", "Outras Fontes")):
            Pilar.objects.create(codigo=codigo, nome=nome)

    def test_extrai_e_grava_os_valores_esperados(self):
        imp = services.ingestar("FINANCEIRO_GERAL", FINANCEIRO, CENTRO, REFERENCIA, self.user)
        self.assertEqual(imp.status, "SUCESSO")
        self.assertEqual(imp.resumo, {"resumos": 9, "projetos": 33})
        pdi = ResumoFinanceiro.objects.get(origem="TAB. 1", pilar__codigo="PDI", ano=None)
        self.assertEqual(pdi.recurso_ou_meta, Decimal("29000000"))
        self.assertEqual(pdi.realizado, Decimal("17675109.56"))
        self.assertEqual(ProjetoFinanceiro.objects.filter(origem="TAB. 2").count(), 18)
        self.assertEqual(ProjetoFinanceiro.objects.filter(origem="TAB. 6").count(), 7)
        at = ResumoFinanceiro.objects.get(origem="TAB. 9", pilar__codigo="AT", ano=None)
        self.assertEqual(at.captado, Decimal("5616700"))
        self.assertNotIn("erro", imp.status.lower())

    def test_reenvio_do_mesmo_arquivo_nao_duplica(self):
        services.ingestar("FINANCEIRO_GERAL", FINANCEIRO, CENTRO, REFERENCIA, self.user)
        services.ingestar("FINANCEIRO_GERAL", FINANCEIRO, CENTRO, REFERENCIA, self.user)
        self.assertEqual(ResumoFinanceiro.objects.count(), 9)
        self.assertEqual(ProjetoFinanceiro.objects.count(), 33)
        self.assertEqual(ImportacaoAcompanhamento.objects.filter(status="SUCESSO").count(), 2)

    def test_reimportar_uma_fonte_preserva_as_demas(self):
        services.ingestar("FINANCEIRO_GERAL", FINANCEIRO, CENTRO, REFERENCIA, self.user)
        services.ingestar("INDICADORES_PE", INDICADORES, CENTRO, REFERENCIA, self.user)
        services.ingestar("FINANCEIRO_GERAL", FINANCEIRO, CENTRO, REFERENCIA, self.user)
        self.assertEqual(ResumoFinanceiro.objects.count(), 9)
        self.assertEqual(KpiAcompanhamento.objects.count(), 10)

    def test_v2_real_grava_acompanhamento_com_metadados(self):
        services.ingestar("ACOMPANHAMENTO_V2", V2, CENTRO, REFERENCIA, self.user)
        acomp = Acompanhamento.objects.get()
        self.assertEqual(acomp.periodo_referencia, REFERENCIA)
        self.assertEqual(acomp.termo_cooperacao, "053/2023")
        self.assertEqual(acomp.despesas.count(), 0)

    def test_imprime_resumo_json_do_que_foi_extraido(self):
        payload = services.resumo_json("FINANCEIRO_GERAL", FINANCEIRO, CENTRO, REFERENCIA)
        texto = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        assert payload["tipo_fonte"] == "FINANCEIRO_GERAL"
        assert payload["periodo_referencia"] == REFERENCIA
        assert payload["contagens"] == {"resumos": 9, "projetos": 33}
        assert str(payload["exemplo_resumo"]["realizado"]) == "17675109.56"
        assert '"realizado": "17675109.56"' in texto

    def test_falha_na_gravacao_faz_rollback_total(self):
        Pilar.objects.all().delete()
        with self.assertRaises(ValidationError):
            services.ingestar("FINANCEIRO_GERAL", FINANCEIRO, CENTRO, REFERENCIA, self.user)
        self.assertEqual(ResumoFinanceiro.objects.count(), 0)
        self.assertEqual(ProjetoFinanceiro.objects.count(), 0)
        self.assertEqual(ImportacaoAcompanhamento.objects.filter(status="ERRO").count(), 1)
        self.assertEqual(Acompanhamento.objects.count(), 1)  # histórico de erro é preservado
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe manage.py test apps.accountability.tests.test_ingestion -v 2`
Expected: FAIL com `ModuleNotFoundError: No module named 'apps.accountability.services'`

- [ ] **Step 3: Implement `services.py`**

Ordem de `ingestar()`: detectar tipo → parser → se `erros`,
registra `ImportacaoAcompanhamento(status="ERRO", log=" | ".join(erros))`,
audita `IMPORTAR_PRESTACAO_ERRO` e levanta `IngestaoError`; normaliza centro
(`comum.normalizar` sem espaços ⇒ `slug`), `get_or_create` de
`CentroCompetencia`/`Acompanhamento`; `transaction.atomic()` com
`filter(acompanhamento=..., <chave da fonte>).delete()` seguido de `bulk_create`
para a fonte enviada; cria `Importacao(status="SUCESSO", resumo=contagens)`
e audita `IMPORTAR_PRESTACAO`. Erro **dentro** da transação ⇒ log `ERRO`
gravado fora da transação e `IngestaoError` propagado (rollback garantido).

Chave de limpeza por fonte: `FINANCEIRO_GERAL`→ `ResumoFinanceiro`+`ProjetoFinanceiro`;
`INDICADORES_PE`→ `KpiAcompanhamento`; `ACOMPANHAMENTO_V2`→ `DespesaAcompanhamento`.

Pilar inexistente no banco durante a resolução ⇒ levantar
`django.core.exceptions.ValidationError(f"Pilar '{codigo}' não encontrado. Cadastre o pilar antes de aplicar.")`
(mesmo texto de `apps.finance.excel_mestre.aplicar_consolidado`) — é o que o teste
de rollback espera. `json` importado no teste serve para imprimir
`imp.resumo` na saída do parse quando um teste falhar.

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe manage.py test apps.accountability.tests.test_ingestion -v 2`
Expected: PASS (8 testes)

- [ ] **Step 5: Run the whole accountability suite**

Run: `.\.venv\Scripts\python.exe manage.py test apps.accountability -v 2`
Expected: PASS, 0 falhas

- [ ] **Step 6: Commit**

```bash
git add apps/accountability/services.py apps/accountability/tests/test_ingestion.py
git commit -m "feat(prestacao): ingestao atomica e idempotente por tipo de fonte"
```

---

### Task 6: Endpoint e UI de upload

**Files:**
- Create: `apps/accountability/forms.py`
- Create: `apps/accountability/views.py`
- Create: `apps/accountability/urls.py`
- Create: `templates/accountability/importar.html`
- Modify: `config/urls.py:13` (incluir `path("financeiro/prestacao/", include("apps.accountability.urls", namespace="accountability"))`)
- Modify: `templates/finance/importar.html:12` (link de entrada)
- Test: `apps/accountability/tests/test_views.py`

**Interfaces:**
- Consumes: `services.ingestar`, `services.IngestaoError`, `services.VALIDADORES`, `pode_importar_financeiro`, `registrar_auditoria` (já via services).
- Produces: rota nomeada `accountability:importar` em `GET|POST /financeiro/prestacao/importar/`.

- [ ] **Step 1: Write the failing test**

```python
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.core.permissions import adicionar_grupo, garantir_grupos


def _xlsx(bloco, nome="arquivo.xlsx"):
    return SimpleUploadedFile(nome, bloco, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


class UploadPermissaoTestes(TestCase):
    def test_anonimo_redireciona_para_login(self):
        self.assertEqual(self.client.get(reverse("accountability:importar")).status_code, 302)

    def test_pontofocal_recebe_403(self):
        garantir_grupos()
        pf = adicionar_grupo(get_user_model().objects.create_user(username="pf", password="x"), "PontoFocal")
        self.client.force_login(pf)
        self.assertEqual(self.client.get(reverse("accountability:importar")).status_code, 403)


class UploadValidacaoTestes(TestCase):
    def setUp(self):
        garantir_grupos()
        self.master = adicionar_grupo(get_user_model().objects.create_user(username="m", password="x"), "Master")
        self.client.force_login(self.master)

    def test_extensao_csv_e_rejeitada(self):
        resposta = self.client.post(reverse("accountability:importar"), {
            "arquivo": SimpleUploadedFile("dados.csv", b"a", content_type="text/csv"),
            "centro": "QuIIN", "periodo_referencia": "2T/2024"})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Envie um arquivo .xlsx")

    def test_centro_e_referencia_sao_obrigatorios(self):
        resposta = self.client.post(reverse("accountability:importar"), {
            "arquivo": _xlsx(b" "), "centro": "", "periodo_referencia": ""})
        self.assertContains(resposta, "obrigat")

    def test_sucesso_exibe_resumo_de_contagens(self):
        from pathlib import Path
        raiz = Path(__file__).resolve().parents[3]
        bloco = (raiz / "mockup" / "exemplos_arquivos" / "FINANCEIRO GERAL.xlsx").read_bytes()
        resposta = self.client.post(reverse("accountability:importar"), {
            "arquivo": _xlsx(bloco, "FINANCEIRO GERAL.xlsx"),
            "centro": "Centro de Competência Embrapii CIMATEC em Tecnologias Quânticas - Quiin",
            "periodo_referencia": "2T/2024"})
        self.assertContains(resposta, "33 projetos financeiros")
        self.assertContains(resposta, "2T/2024")

    def test_falha_de_parse_mostra_mensagem_amigavel(self):
        resposta = self.client.post(reverse("accountability:importar"), {
            "arquivo": _xlsx(b"PK\x03\x04lixo", "quebrado.xlsx"),
            "centro": "QuIIN", "periodo_referencia": "2T/2024"})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(response=resposta, text="Não foi possível ler")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe manage.py test apps.accountability.tests.test_views -v 2`
Expected: FAIL com `NoReverseMatch`/`ModuleNotFoundError`

- [ ] **Step 3: Implement form, view, urls e template**

`UploadPrestacaoForm`: `arquivo` (`FileField`, validação de extensão `.xlsx` e
tamanho máx. 25 MB), `centro` (`CharField`, required), `periodo_referencia`
(`CharField`, required; normaliza para maiúsculas e valida `^[1-4][TS]/\d{4}$`,
aceitando também o sufixo `S`/`s` de semestre; erro: `"Use o formato 2T/2024."`).

View `@login_required` (reaproveita `pode_importar_financeiro` + `sem_permissao`):
POST ⇒ grava o upload em `tempfile.NamedTemporaryFile(suffix=".xlsx")`,
`detejar_tipo_arquivo` lendo só os nomes de abas, `ingestar(...)`;
`IngestaoError` ⇒ `messages.error(request, str(exc))`; sucesso ⇒
`messages.success` com `"{n} projetos financeiros, {n} KPIs e {n} despesas importados para {referencia}."`.
GET ⇒ renderiza `accountability/importar.html` com `importacoes` (últimas 30,
`select_related("acompanhamento__centro")`).

Template no padrão de `templates/finance/importar.html`: form
`enctype="multipart/form-data"`, estados Alpine `enviando/processando` (o botão
fica `disabled` durante o POST), `data-testid="page-importar-prestacao"`,
mensagens `role="alert"`, tabela de histórico com status, contagens (`resumo`
JSON) e log.

- [ ] **Step 4: Registrar rota e link de entrada**

`config/urls.py`: incluir o app sob `financeiro/prestacao/`.
`templates/finance/importar.html`: adicionar botão
`<c-ui.button href="{% url 'accountability:importar' %}">Importar planilhas de prestação</c-ui.button>`.

- [ ] **Step 5: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe manage.py test apps.accountability.tests.test_views -v 2`
Expected: PASS (6 testes)

- [ ] **Step 6: Commit**

```bash
git add apps/accountability config/urls.py templates/accountability templates/finance/importar.html
git commit -m "feat(prestacao): endpoint e UI de upload dos arquivos Excel"
```

---

### Task 7: Painel anual substituído pelas bases importadas

**Files:**
- Create: `apps/accountability/panel.py`
- Modify: `apps/planning/views.py:31-59` (`contexto_painel` ganha `acompanhamento=None`)
- Modify: `apps/core/views.py:46-70` (`dashboard` resolve `?acompanhamento=`)
- Modify: `templates/dashboard/_controles.html` (seletor + propagação do parâmetro)
- Modify: `templates/dashboard/editor.html:19` (campo oculto)
- Test: `apps/accountability/tests/test_panel.py`

**Interfaces:**
- Consumes: modelos do Task 1; `planning.services.percentual/faixa/pct_inteiro/ANOS/PILARES_PPI/ROTULOS_PAINEL`; `planning.charts.geometria_*`.
- Produces:
  - `panel.acompanhamento_padrao() -> Acompanhamento | None` (mais recente)
  - `panel.painel_acompanhamento(ano: int | None, base: str, acomp) -> dict` — mesmo contrato de `planning.services.painel()`
  - `contexto_painel(ano_param, base_param, usuario, acompanhamento=None) -> dict` — acrescenta `acompanhamento`, `acompanhamentos`

- [ ] **Step 1: Write the failing test**

```python
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.planning.models import PlanoAnual
from apps.pillars.models import Pilar
from . import panel, services
from .models import Acompanhamento, CentroCompetencia, KpiAcompanhamento, ResumoFinanceiro

RAIZ = Path(__file__).resolve().parents[3]
FINANCEIRO = RAIZ / "mockup" / "exemplos_arquivos" / "FINANCEIRO GERAL.xlsx"
INDICADORES = RAIZ / "mockup" / "exemplos_arquivos" / "Indicadores Gerais do Termo de Retificação do PE.xlsx"
CENTRO = "Centro de Competência Embrapii CIMATEC em Tecnologias Quânticas - Quiin"


class BasePanelTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        garantir_grupos()
        User = get_user_model()
        cls.user = adicionar_grupo(User.objects.create_user(username="panel", password="x"), "Master")
        for codigo, nome in (("PDI", "PDI"), ("FORMACAO", "Formação FCRH"),
                             ("STARTUPS", "ACS"), ("INFRA", "Infraestrutura"),
                             ("AT", "AT"), ("OUTRASFONTES", "Outras Fontes")):
            Pilar.objects.create(codigo=codigo, nome=nome)
        services.ingestar("FINANCEIRO_GERAL", FINANCEIRO, CENTRO, "2T/2024", cls.user)
        services.ingestar("INDICADORES_PE", INDICADORES, CENTRO, "2T/2024", cls.user)
        cls.acomp = Acompanhamento.objects.get()


class PainelFinanceiroTestes(BasePanelTestes):
    def test_painel_e_alimentado_pelo_acompanhamento(self):
        p = panel.painel_acompanhamento(None, "financeiro", self.acomp)
        assert set(p) >= {"ano", "base", "unidade", "rotulo_periodo", "cards",
                          "graficos", "tabela", "consolidado"}
        assert set(p["graficos"]) == {"ppi", "at", "outras"}
        assert len(p["cards"]) == 4

    def test_card_ppi_usa_somente_os_quatro_pilares_ppi(self):
        p = panel.painel_acompanhamento(None, "financeiro", self.acomp)
        ppi = next(c for c in p["cards"] if c["chave"] == "ppi")
        assert ppi["executado"] == Decimal("34975229.95")
        assert ppi["previsto"] == Decimal("60000000")

    def test_card_at_usa_captado_como_denominador(self):
        p = panel.painel_acompanhamento(None, "financeiro", self.acomp)
        at = next(c for c in p["cards"] if c["chave"] == "at")
        assert at["executado"] == Decimal("220597")
        assert at["previsto"] == Decimal("5616700")

    def test_ano_sem_linha_importada_exibe_traco(self):
        p = panel.painel_acompanhamento(2024, "financeiro", self.acomp)
        linha = next(l for l in p["tabela"]["grupos"][0]["linhas"] if l["rotulo"] == "PDI")
        assert linha["executado"] is None
        assert linha["pct"] is None
        assert linha["faixa"] == "neutra"

    def test_totais_de_reconciliacao_nao_sao_somados(self):
        p = panel.painel_acompanhamento(None, "financeiro", self.acomp)
        ppi = next(c for c in p["cards"] if c["chave"] == "ppi")
        # TAB. 3 repete o realizado do PDI; somá-la dobraria o total.
        assert ppi["executado"] == Decimal("34975229.95")


class PainelFisicoTestes(BasePanelTestes):
    def test_fisico_vira_lista_de_kpis_por_unidade(self):
        p = panel.painel_acompanhamento(None, "fisico", self.acomp)
        rotulos = [l["rotulo"] for g in p["tabela"]["grupos"] for l in g["linhas"]]
        assert any("Número absoluto" in r for r in rotulos)
        assert any("Percentual" in r for r in rotulos)

    def test_kpi_sem_executado_no_ano_exibe_traco(self):
        p = panel.painel_acompanhamento(2026, "fisico", self.acomp)
        linha = next(l for l in p["tabela"]["grupos"][0]["linhas"]
                     if l["rotulo"].startswith("Projetos de PD&I"))
        assert linha["previsto"] == Decimal("5")
        assert linha["executado"] is None
        assert linha["pct"] is None
        assert linha["faixa"] == "neutra"

    def test_acumulado_usa_meta_total_e_acumulado(self):
        p = panel.painel_acompanhamento(None, "fisico", self.acomp)
        linha = next(l for l in p["tabela"]["grupos"][0]["linhas"]
                     if l["rotulo"].startswith("Projetos de PD&I"))
        assert linha["previsto"] == Decimal("18")
        assert linha["executado"] == Decimal("15")


class PainelLegadoTestes(TestCase):
    def test_painel_sem_acompanhamento_usa_plano_legado(self):
        from apps.planning.views import contexto_painel
        garantir_grupos()
        user = adicionar_grupo(get_user_model().objects.create_user(username="leg", password="x"), "Master")
        pilar = Pilar.objects.create(codigo="PDI", nome="PDI", ordem=1)
        PlanoAnual.objects.create(ano=2026, pilar=pilar, base="financeiro",
                                  previsto=10, executado=9)
        contexto = contexto_painel("2026", "fin", user)
        assert contexto["painel"] is not None
        assert contexto.get("acompanhamento") is None
        linha = next(l for l in contexto["painel"]["tabela"]["grupos"][0]["linhas"]
                     if l["rotulo"] == "PDI")
        assert linha["previsto"] == Decimal("10")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe manage.py test apps.accountability.tests.test_panel -v 2`
Expected: FAIL com `ModuleNotFoundError: No module named 'apps.accountability.panel'`

- [ ] **Step 3: Implement `panel.py`**

Duas funções construtoras de DTO, ambas devolvendo o contrato de `painel()`:

- `_linha(rotulo, previsto, executado, total=False)` → dict com
  `previsto/executado` possivelmente `None`, `saldo = None` se qualquer um for
  `None`, `pct = None` se qualquer um for `None`, senão `pct_inteiro(...)`,
  `faixa = "neutra"` se `pct is None` senão `faixa(percentual(...))`.
- `_serie_anos(lookup)` → 4 posições para `ANOS`, `None` quando não há linha.
- `base="financeiro"`: agregação por pilar a partir de
  `ResumoFinanceiro.filter(acompanhamento=..., origem__in=("TAB. 1","TAB. 9"), ano__isnull=True)`;
  anual a partir de `origem="TAB. 1.1"`. PPI (`PILARES_PPI`) usa
  `recurso_ou_meta`/`realizado`; AT/OUTRASFONTES usam `captado`/`realizado`.
  Cards `ppi|at|outras|total`; gráficos `serie_previsto/serie_executado` com 5
  pontos (4 anos + acumulado); `consolidado` com `anos=ANOS` e 3 séries.
  Totais de TAB. 3/5/8 **não** entram em nenhum agregado.
- `base="fisico"`: grupos por pilar com `KpiAcompanhamento`; rótulo
  `f"{nome} ({unidade})"`; por ano `meta_<ano>` × `executado_<2024|2025>`
  (`None` em 2026/2027); `todos` ⇒ `meta_total` × `acumulado`.
- **Duas representações do mesmo dado**, porque template e geometria têm
  contratos diferentes:
  - `tabela.grupos[*].linhas[*]` aceita `previsto/executado/saldo = None` e
    `pct = None`, `faixa = "neutra"` (renderiza `—`).
  - `graficos[*].serie_previsto/serie_executado` e `consolidado.series` são
    **sempre numéricos** (`Decimal(0)` para dado ausente), porque
    `contexto_painel` faz `float(v)` em `geometria_fonte`/`geometria_consolidado`
    e `None` quebraria o render. Barras sem dado aparecem vazias — mesmo
    comportamento do `PlanoAnual` legado com linha ausente.
  - Como as chaves de gráfico são fixas no template (`ppi`, `at`, `outras`),
    `base="fisico"` preenche esses três blocos agrupando os KPIs por pilar:
    `ppi` = KPIs de `PILARES_PPI`, `at` = KPIs de `AT`, `outras` = KPIs de
    `OUTRASFONTES`. Só entram na soma os KPIs de uma única unidade por bloco;
    havendo unidades mistas, o bloco usa a unidade majoritária e os demais KPIs
    ficam apenas na tabela.

- [ ] **Step 4: Wire em `contexto_painel` e na view `dashboard`**

`contexto_painel(ano_param, base_param, usuario, acompanhamento=None)`:
se `acompanhamento` não for passado, usa `panel.acompanhamento_padrao()`;
se houver, `painel = panel.painel_acompanhamento(...)` e
`grade_edicao = []` (Task 8 preenche); senão, fluxo legado inalterado.
Contexto ganha `acompanhamento` e `acompanhamentos` (lista para o seletor).

`core.views.dashboard`: lê `request.GET["acompanhamento"]`, valida pk
(`get_object_or_404`) e repassa; o parâmetro participa do deep-link.

- [ ] **Step 5: Templates**

`_controles.html`: no form GET existente, adicionar
`<input type="hidden" name="acompanhamento" ...>` condicional e um `<select
name="acompanhamento" data-testid="acompanhamento-select">` (renderizado só se
`acompanhamentos` não for vazio, opções `{{ a.pk }}" {{ a.centro.nome }} ·
{{ a.periodo_referencia }}`); acrescentar `&acompanhamento={{ acompanhamento.pk }}`
aos dois links de base (`fin`/`fis`) e aos links CSV/HTML quando definido.

O seletor só recebe `acompanhamentos` no contexto da view `/`, portanto aparece
apenas no painel anual. **Escopo decidido:** a página `/pilar/<pk>/` continua no
fluxo legado (`painel_pilar` lê `PlanoAnual`); ela não é migrada nesta entrega e
não recebe o seletor.

- [ ] **Step 6: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe manage.py test apps.accountability.tests.test_panel -v 2`
Expected: PASS (9 testes)

- [ ] **Step 7: Regression — suites existentes não podem quebrar**

Run: `.\.venv\Scripts\python.exe manage.py test apps.planning apps.core apps.finance -v 1`
Expected: PASS, 0 falhas (sem acompanhamento no banco ⇒ caminho legado)

- [ ] **Step 8: Commit**

```bash
git add apps/accountability apps/planning/views.py apps/core/views.py templates/dashboard
git commit -m "feat(prestacao): painel anual alimentado pelos snapshots importados"
```

---

### Task 8: Override manual por acompanhamento

**Files:**
- Create: `apps/accountability/overrides.py`
- Modify: `apps/planning/views.py:143-189` (`aplicar` desvia para overrides quando houver `acompanhamento` no POST)
- Modify: `templates/dashboard/editor.html` (campo oculto + botão restaurar)
- Test: `apps/accountability/tests/test_overrides.py`

**Interfaces:**
- Consumes: `OverrideAcompanhamento` (Task 1), `panel.painel_acompanhamento`, permissões `pode_editar_painel`/`pilares_editaveis_painel`.
- Produces:
  - `overrides.grade_edicao_overrides(acomp, base, codigos=None) -> list[dict]` — mesmo shape de `planning.services.grade_edicao`
  - `overrides.aplicar_overrides(acomp, base, itens, usuario) -> int` — `itens = [(ano, codigo, campo, valor|None)]`; `valor=None` remove a linha
  - `overrides.restaurar_tudo(acomp, usuario) -> int`
  - `overrides.chave(base, codigo, ano, campo) -> str`

- [ ] **Step 1: Write the failing test**

```python
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from apps.core.permissions import adicionar_grupo, garantir_grupos
from apps.pillars.models import Pilar
from . import overrides, panel, services
from .models import Acompanhamento, OverrideAcompanhamento
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
FINANCEIRO = RAIZ / "mockup" / "exemplos_arquivos" / "FINANCEIRO GERAL.xlsx"
INDICADORES = RAIZ / "mockup" / "exemplos_arquivos" / "Indicadores Gerais do Termo de Retificação do PE.xlsx"
CENTRO = "Centro de Competência Embrapii CIMATEC em Tecnologias Quânticas - Quiin"


class OverrideTestes(TestCase):
    @classmethod
    def setUpTestData(cls):
        garantir_grupos()
        User = get_user_model()
        cls.user = adicionar_grupo(User.objects.create_user(username="ovr", password="x"), "Master")
        for codigo, nome in (("PDI", "PDI"), ("FORMACAO", "Formação FCRH"),
                             ("STARTUPS", "ACS"), ("INFRA", "Infraestrutura"),
                             ("AT", "AT"), ("OUTRASFONTES", "Outras Fontes")):
            Pilar.objects.create(codigo=codigo, nome=nome)
        services.ingestar("FINANCEIRO_GERAL", FINANCEIRO, CENTRO, "2T/2024", cls.user)
        services.ingestar("INDICADORES_PE", INDICADORES, CENTRO, "2T/2024", cls.user)
        cls.acomp = Acompanhamento.objects.get()

    def test_override_tem_precedencia_sobre_o_importado(self):
        overrides.aplicar_overrides(self.acomp, "financeiro",
                                    [(2026, "PDI", "executado", Decimal("999"))], self.user)
        p = panel.painel_acompanhamento(2026, "financeiro", self.acomp)
        linha = next(l for l in p["tabela"]["grupos"][0]["linhas"] if l["rotulo"] == "PDI")
        assert linha["executado"] == Decimal("999")

    def test_override_fisico_por_kpi(self):
        kpi = self.acomp.kpis.get(codigo="PE-01")
        overrides.aplicar_overrides(self.acomp, "fisico",
                                    [(2025, kpi.codigo, "executado", Decimal("99"))], self.user)
        p = panel.painel_acompanhamento(2025, "fisico", self.acomp)
        linha = next(l for l in p["tabela"]["grupos"][0]["linhas"]
                     if l["rotulo"].startswith("Projetos de PD&I"))
        assert linha["executado"] == Decimal("99")

    def test_valor_vazio_remove_o_override_e_restaura_o_importado(self):
        overrides.aplicar_overrides(self.acomp, "financeiro",
                                    [(2026, "PDI", "executado", Decimal("999"))], self.user)
        overrides.aplicar_overrides(self.acomp, "financeiro",
                                    [(2026, "PDI", "executado", None)], self.user)
        assert not OverrideAcompanhamento.objects.filter(acompanhamento=self.acomp).exists()

    def test_restaurar_tudo_limpa_a_base_inteira(self):
        overrides.aplicar_overrides(self.acomp, "financeiro",
                                    [(2026, "PDI", "executado", Decimal("1"))], self.user)
        overrides.aplicar_overrides(self.acomp, "fisico",
                                    [(2026, "PE-01", "previsto", Decimal("2"))], self.user)
        assert overrides.restaurar_tudo(self.acomp, self.user) == 2
        assert not OverrideAcompanhamento.objects.filter(acompanhamento=self.acomp).exists()

    def test_ponto_focal_nao_edita_pilar_alheio(self):
        Pilar.objects.create(codigo="OUTRASFONTES", nome="Outras Fontes", ordem=6)
        pf = adicionar_grupo(get_user_model().objects.create_user(username="pf2", password="x"), "PontoFocal")
        with self.assertRaises(PermissionDenied):
            overrides.aplicar_overrides(self.acomp, "financeiro",
                                        [(2026, "AT", "executado", Decimal("1"))], pf)

    def test_ano_fora_do_intervalo_e_rejeitado(self):
        with self.assertRaises(ValidationError):
            overrides.aplicar_overrides(self.acomp, "financeiro",
                                        [(2030, "PDI", "executado", Decimal("1"))], self.user)

    def test_grade_de_edicao_espelha_os_valores_efetivos(self):
        grade = overrides.grade_edicao_overrides(self.acomp, "financeiro")
        assert grade and grade[0]["linhas"][0]["codigo"] == "PDI"
        fisica = overrides.grade_edicao_overrides(self.acomp, "fisico")
        assert fisica and fisica[0]["linhas"][0]["codigo"] == "PE-01"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe manage.py test apps.accountability.tests.test_overrides -v 2`
Expected: FAIL com `ModuleNotFoundError: No module named 'apps.accountability.overrides'`

- [ ] **Step 3: Implement `overrides.py`**

`chave(base, codigo, ano, campo)` → `f"{base}|{codigo}|{ano}|{campo}"`
(`base` abreviado: `fin`/`fis`). `aplicar_overrides` valida ano em `ANOS`,
campo em `("previsto","executado")`, valor `>= 0` e, para `fisico`, inteiro;
valida escopo com `pode_editar_painel` e, para `financeiro`, que o pilar está em
`pilares_editaveis_painel(usuario)` (para `fisico`, o pilar do KPI);
`PermissionError` ⇒ `PermissionDenied`. Grava com `update_or_create`/`delete`
em `transaction.atomic()` e audita `EDITAR_OVERRIDE_PRESTACAO` com
`valor_anterior`/`valor_novo`. `restaurar_tudo` apaga todos os overrides do
acompanhamento e audita `RESTAURAR_OVERRIDE_PRESTACAO`.

`grade_edicao_overrides` devolve blocos no shape de `grade_edicao`
(`titulo`, `cabecalho`, `linhas[{codigo, rotulo, campo, celulas[{ano, valor}], total}]`)
com os valores **efetivos** (override quando existir, senão importado, senão `None`).

- [ ] **Step 4: Wire em `planning.views.aplicar`**

No topo de `aplicar`, se `request.POST.get("acompanhamento")`: resolve o objeto,
converte as chaves `v__{ano}__{base}__{codigo}__{campo}` em `itens`
(valor vazio ⇒ `None`), despacha para `aplicar_overrides`; se
`request.POST.get("acao") == "restaurar"` chama `restaurar_tudo`.
Fluxo legado sem `acompanhamento` permanece byte a byte igual.

- [ ] **Step 5: Template do editor**

`editor.html`: adicionar `<input type="hidden" name="acompanhamento"
value="{{ acompanhamento.pk }}">` quando `acompanhamento` existir, e um botão
`<c-ui.button ... name="acao" value="restaurar">Restaurar valores importados</c-ui.button>`
visível só com acompanhamento. `contexto_painel` passa a preencher
`grade_edicao` com `overrides.grade_edicao_overrides(...)` quando houver
acompanhamento. `contexto_pilar` **não** muda (página em fluxo legado, ver
Task 7 Step 5).

- [ ] **Step 6: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe manage.py test apps.accountability.tests.test_overrides -v 2`
Expected: PASS (7 testes)

- [ ] **Step 7: Full suite**

Run: `.\.venv\Scripts\python.exe manage.py test -v 1`
Expected: PASS, 0 falhas

- [ ] **Step 8: Commit**

```bash
git add apps/accountability apps/planning/views.py templates/dashboard/editor.html
git commit -m "feat(prestacao): override manual auditado por acompanhamento"
```
