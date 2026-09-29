# SDD — Upload e Ingestão de Arquivos de Prestação de Contas QuIIN

Data: 2026-09-29 · Status: aprovado
Branch: `ajuste-pos-reu` · Django 5.2 + openpyxl + SQLite/Postgres

## 1. Contexto e decisões aprovadas

O objetivo é eliminar a digitação manual: o usuário envia os Excel oficiais e o
sistema extrai, valida e grava os dados, alimentando os dashboards.

Decisões aprovadas na revisão:

1. **Chave lógica** — `(centro_competencia, periodo_referencia)` é única. O
   template v2 traz Centro/Termo/Referência nas próprias células; os dois
   arquivos sem metadados recebem Centro e Referência obrigatórios no formulário
   de upload e são conferidos contra o v2 quando ele já existe.
2. **Pilares** — vêm do rótulo da linha nas tabelas consolidadas e do título da
   seção nas tabelas por projeto (ex.: `TAB. 2 → AFCCT/PD&I`).
3. **Escopo do v2** — abas financeiras 3–9. A aba `10. Equipe` **não** é
   importada (dados pessoais/CPF fora do escopo); validação estrutural apenas.
4. **TAB. 7 ausente** — gera aviso, não rejeita o arquivo.
5. **Dashboards** — o painel anual `/` é **substituído** como destino: base
   financeira vem de `FINANCEIRO GERAL`, base física vira lista de KPIs do PE por
   indicador/unidade. `PlanoAnual` vira legado (mantido no banco, deixa de
   alimentar o painel quando há acompanhamento importado).
6. **Override manual** — continua existindo, cobre **ambas** as bases
   (financeiro por pilar/ano; físico por KPI/ano), fica vinculado ao mesmo
   acompanhamento, tem precedência sobre o importado e é auditado.
7. **Sem agregação inválida** — unidades diferentes não são somadas; campos sem
   correspondência exata no Excel aparecem como `—`.

## 2. Arquitetura

Novo app `apps/accountability`. Os fluxos mensais (`Periodo`,
`FinanceiroConsolidado`, `Lancamento`) permanecem intactos.

```
upload (.xlsx)
  → detectar tipo de arquivo pela assinatura das abas
  → parse openpyxl read-only → payload tipado em memória (erros/avisos)
  → validar estrutura + metadados
  → buscar/criar CentroCompetencia + Acompanhamento
  → transaction.atomic(): apagar somente os fatos daquele tipo_fonte e recriar
  → gravar ImportacaoAcompanhamento (SUCESSO|ERRO) + AuditLog
```

Idempotência: reenviar o mesmo arquivo substitui os fatos daquela fonte para o
mesmo acompanhamento; nunca duplica. Falha ⇒ rollback total + log de erro.

## 3. Schema

```python
TIPOS_FONTE = [("FINANCEIRO_GERAL", ...), ("INDICADORES_PE", ...), ("ACOMPANHAMENTO_V2", ...)]

class CentroCompetencia:
    codigo  SlugField unique          # nome normalizado (minúsculas, sem acento/espaço colapsado)
    nome    CharField(200)
    ativo   BooleanField default True

class Acompanhamento:
    centro               FK CentroCompetencia, related_name="acompanhamentos"
    periodo_referencia   CharField(20)          # ex.: "2T/2024"
    termo_cooperacao     CharField(50) blank
    criado_em / atualizado_em
    Meta.constraints = [UniqueConstraint(centro, periodo_referencia,
                                         name="uniq_centro_periodo_acompanhamento")]

class ImportacaoAcompanhamento:
    acompanhamento FK null=True, related_name="importacoes"
    tipo_fonte  CharField(choices=TIPOS_FONTE)
    arquivo_nome CharField(255)
    status       CharField choices SUCESSO|ERRO
    log          TextField blank          # erros unidos por " | "
    avisos       TextField blank          # avisos unidos por " | "
    resumo       JSONField null           # {"resumos": 9, "projetos": 33}
    usuario FK null=True
    criado_em

class ResumoFinanceiro:                    # valores consolidados
    acompanhamento FK related_name="resumos"
    origem CharField(32)                   # "TAB. 1" | "TAB. 1.1" | "TAB. 3" | "TAB. 5" | "TAB. 8" | "TAB. 9"
    pilar  FK pillars.Pilar
    ano    PositiveSmallIntegerField null  # None = consolidado geral
    recurso_ou_meta, captado_anos_1_2, captado_ano3_ytd, captado,
    realizado, projetado, realizado_mais_projetado, diferenca,
    percentual, percentual_meta, percentual_captado   # DecimalField null
    farol CharField(20) blank
    UniqueConstraint(acompanhamento, origem, pilar, ano)

class ProjetoFinanceiro:
    acompanhamento FK related_name="projetos"
    origem CharField(32)                   # "TAB. 2" | "TAB. 4" | "TAB. 6"
    pilar  FK
    sequencia PositiveIntegerField null
    nome CharField(255)
    status CharField(120) blank
    inicio, fim Date null
    orcado, realizado, projetado_2026, projetado_2027,
    realizado_mais_projetado, diferenca, percentual   # DecimalField null
    UniqueConstraint(acompanhamento, origem, nome)

class KpiAcompanhamento:
    acompanhamento FK related_name="kpis"
    codigo CharField(40)                   # "PE-01".."PE-10"
    sequencia PositiveIntegerField
    nome CharField(255)
    pilar FK                               # de "AÇÃO"
    descricao Text blank
    unidade CharField(50) blank
    meta_2024..meta_2027, meta_total,
    executado_2024, executado_2025, acumulado, gap,
    projecao_2026, projecao_2027           # DecimalField null
    UniqueConstraint(acompanhamento, codigo)

class DespesaAcompanhamento:
    acompanhamento FK related_name="despesas"
    aba CharField(80), linha PositiveIntegerField
    pilar FK, tipo_recurso CharField(15)    # EMBRAPII|AT|AT_LEI_TICS|OUTRAS_FONTES
    acao_relacionada, codigo_projeto, conta_projeto, marco,
    tipo_despesa, credor, documento,
    numero_nota, link_documento, numero_patrimonial,
    descricao, descricao_atividade, observacao, fonte_recurso   # Char/Text blank
    data_nota, data_pagamento, data_movimento Date null
    quantidade, valor_unitario, valor       # DecimalField null
    UniqueConstraint(acompanhamento, aba, linha)

class OverrideAcompanhamento:
    acompanhamento FK related_name="overrides"
    base   CharField(12) choices financeiro|fisico
    pilar  FK null                          # base=financeiro
    kpi    FK KpiAcompanhamento null        # base=fisico
    ano    PositiveSmallIntegerField
    campo  CharField(20)                    # previsto|executado
    valor  DecimalField(18,2)
    chave  CharField(120)                   # "fin|PDI|2026|executado" / "fis|PE-01|2025|previsto"
    usuario FK null, atualizado_em
    UniqueConstraint(acompanhamento, chave)
    clean(): financeiro ⇒ pilar preenchido e kpi vazio; fisico ⇒ o inverso
```

`ResumoFinanceiro` e `KpiAcompanhamento` nunca são somados entre si. O painel
usa apenas `origem in ("TAB. 1", "TAB. 9")` para o consolidado; TAB. 3/5/8 são
linhas de reconciliação armazenadas, não agregadas.

## 4. Mapeamento — `FINANCEIRO GERAL.xlsx`

Aba única `FINANCEIRO ` (com espaço final). Todas as células abaixo são
posicionais; a validação confere o rótulo do cabeçalho antes de ler.

| Bloco | Linhas | Pilar | Colunas |
|---|---|---|---|
| TAB. 1 `C1:J9` | dados 5–8, para em 9 (`TOTAL`) | da célula `C` | `C` pilar · `D` recurso · `E` realizado · `F` projetado · `G` realizado+projetado · `H` diferença · `I` % · `J` farol |
| TAB. 1.1 `M1:W9` | dados 5–8, para em 9 | da célula `M` | `M` pilar · `N` recurso · `O` 2024 · `P` 2025 · `Q` 2026 YTD · `R` projetado 2026 · `S` projetado total · `T` r+p · `U` diferença · `V` % · `W` farol |
| TAB. 3 `C35:H38` | linha 38 | do título `C35`/`J35` (PDI) | `D` recurso · `E` realizado · `F` projetado · `G` r+p · `H` diferença |
| TAB. 5 `C55:H58` | linha 58 | do título `C55`/`I55` (FCRH) | idem |
| TAB. 8 `C76:H79` | linha 79 | do título `C76`/`I76` (ACS) | idem |
| TAB. 9 `C84:J87` | dados 86–87, para em 88 (`TOTAL`) | da célula `C` | `C` pilar · `D` meta · `E` captado Ano 1+2 · `F` captado Ano 3 YTD · `G` captado total · `H` realizado · `I` % captado/meta · `J` % realizado/captado |

Projetos (cabeçalho na linha indicada, dados a partir de `cabeçalho+2`, param na
linha `C` iniciada por `TOTAL`):

| Bloco | Cabeçalho | Pilar | Layout |
|---|---|---|---|
| TAB. 2 | 13 (`C13='PROJETO'`) | PDI | `C` projeto · `D` status · `E` início · `F` fim · `G` orçado · `H` realizado · `I` projetado 2026 · `J` projetado 2027 · `K` r+p · `L` diferença · `M` % |
| TAB. 4 | 43 (`C43='PROJETO'`) | FCRH | idem |
| TAB. 6 | 64 (`C64='PROJETO'`) | ACS | `C` projeto · `D` status · `E` data final · `F` orçado · `G` realizado · `H` projetado 2026 · `I` projetado 2027 · `J` r+p · `K` diferença · `L` % |

Rótulos de pilar aceitos (normalizados): `AFCCT / PD&I`→PDI · `FCRH`→FORMACAO ·
`ACS`→STARTUPS · `INFRAESTRUTURA`→INFRA · `ASSOCIAÇÃO TECNOLÓGICA`→AT ·
`OUTRAS FONTES`→OUTRASFONTES.

Se os valores anuais de TAB. 1.1 (`O:S`) estiverem todos vazios, nenhuma linha
`ano` é gerada e emite-se o aviso
`TAB. 1.1 sem valores anuais por pilar; a visão anual exibirá —`.

Valores esperados do arquivo atual: PDI `D5=29000000`, `E5=17675109.56`,
`I5=0.6094865365517241`; FCRH `E6=7749636.72`; ACS `E7=2251069.32`;
INFRA `E8=7299414.35`; projetos 18 (TAB. 2) + 8 (TAB. 4) + 7 (TAB. 6) = 33;
TAB. 9 AT `D86=7750000`, `G86=5616700`, `H86=220597`.

## 5. Mapeamento — `Indicadores Gerais do Termo de Retificação do PE.xlsx`

Aba `HEAD - INDICADORES - EMBRAPII`, cabeçalho nas linhas 2–3, dados 4–13 (10 KPIs):

`B` número → `codigo="PE-<NN>"` · `C` título · `D` ação → pilar · `E` descrição ·
`F` unidade · `G:J` meta 2024–2027 · `K` meta total · `L` executado ano 1 (2024) ·
`M` executado ano 2 (2025) · `N` acumulado (até nov/25) · `O` gap ·
`P` projeção ano 3 (2026) · `Q` projeção ano 4 (2027).

Ação→pilar: `PD&I`→PDI · `OUTRAS FONTES`→OUTRASFONTES · `AT`→AT ·
`ACS`→STARTUPS · `FCRH`→FORMACAO · `INFRAESTRUTURA`→INFRA.

Esperado no arquivo atual: KPI 1 `nome='Projetos de PD&I desenvolvidos pelo
Centro de Competência'`, metas `5,5,5,3`, meta total `18`, executado `5/10`,
acumulado `15`, gap `-3`, projeções `2/0`.

## 6. Mapeamento — `Acompanhamento Financeiro (v2).xlsx`

**Metadados** — ler por *rótulo* (não por coordenada fixa): nas primeiras 12
linhas de cada aba, localizar a célula cujo texto normalizado inicia com
`centro de competência`, `termo de cooperação` ou `período de referência`, e
pegar o valor da próxima célula preenchida à direita. A aba `0. Sumário`
(`J19:J21`) é a fonte primária; os valores lidos nas abas 3–9 são conferidos
com ela. Divergência ⇒ erro nomeando aba e célula.

**Abas financeiras** — linha de cabeçalho = linha que contém célula `Linha`
(normalizada); dados a partir da seguinte. Regras de coluna aplicadas **por
ordem** (primeira casa vence) sobre o texto normalizado do cabeçalho:

1. `== linha` → `sequencia`
2. contém `código do projeto` → `codigo_projeto` (checado **antes** da regra
     de `conta`, para `Informar o código do projeto/atividade` das abas 6/6.1/7
     continuar caindo aqui) · contém `conta do projeto` → `conta_projeto` —
     são colunas distintas na aba 3 (`C` e `D`) e o modelo §3 tem os dois campos
3. contém `data do pagamento` → `data_pagamento`
4. começa com `data da nota` → `data_nota`
5. `== data` → `data_movimento`
6. contém `valor unit` → `valor_unitario`
7. contém `quantidade` → `quantidade`
8. contém `número patrimonial` → `numero_patrimonial`
9. contém `número da nota` → `numero_nota`
10. começa com `valor` → `valor`
11. contém `link` → `link_documento`
12. contém `cnpj` ou `cpf` → `documento`
13. contém `fornecedor` e não `estrangeiro` → `credor`
14. contém `entidade que realizou` → `credor`
15. contém `credor` e não `estrangeiro` → `credor`
16. contém `tipo de despesa` → `tipo_despesa`
17. contém `marco` → `marco`
18. contém `ação está relacionad` (radical: casa `relacionada`/`relacionado`;
     o template real usa `Informar a qual ação está relacionado`) → `acao_relacionada`
19. contém `fonte recurso` → `fonte_recurso`
20. contém `breve descritivo` → `descricao_atividade`
21. contém `breve descrição` → `descricao`
22. contém `descrição` → `descricao`
23. contém `observa` → `observacao`

Cabeçalhos não mapeados (ex.: `Fornecedor – estrangeiro?`, `Ano` com `#REF!`)
são ignorados. Percorre até a primeira linha em que nenhum campo mapeado tenha
valor (a linha com só o número sequencial encerra a leitura).

Aba → `(pilar, tipo_recurso)`:

| Aba | pilar | tipo_recurso |
|---|---|---|
| `3. Conta Ação - AFCCT` | PDI | EMBRAPII |
| `4. Conta Ação - FCRH` | FORMACAO | EMBRAPII |
| `5. Conta Ação - ACS` | STARTUPS | EMBRAPII |
| `6. Conta Ação - AT` | AT | AT |
| `6.1 Conta Ação - AT (Lei TICs)` | AT | AT_LEI_TICS |
| `7. Conta Ação - Outras Fontes` | OUTRASFONTES | OUTRAS_FONTES |
| `8. Conta Ação - Infraestrutura` | INFRA | EMBRAPII |
| `9. Ampliação de Infraestrutura` | INFRA | EMBRAPII |

REGRA DURA: `6.1` é segregada como `AT_LEI_TICS` e nunca soma em `AT`.
`9. Ampliação` é aquisição patrimonial (sem data de pagamento).

Ausência de uma das 8 abas obrigatórias ⇒ erro amigável citando o nome esperado.

## 7. Tratamento de erros

| Situação | Comportamento |
|---|---|
| extensão ≠ `.xlsx`, zip/ole inválido, openpyxl falha | rejeita upload, sem gravação |
| tipo de arquivo não identificado pela assinatura das abas | rejeita citando abas exigidas |
| aba obrigatória ausente | erro citando nome exato da aba |
| cabeçalho esperado não encontrado | erro citando aba/linha esperada |
| Centro/Referência ausentes no formulário (arquivos 1 e 2) | erro de validação do formulário |
| metadados divergentes entre abas do v2 | erro citando aba e célula |
| célula obrigatória com texto não numérico ou `#REF!`/`#VALUE!` | erro citando aba, linha e coluna |
| célula opcional vazia | grava `NULL`; nunca `0` implícito |
| linha totalmente vazia | ignorada |
| erro de fórmula em célula não mapeada | aviso, não bloqueia |
| falha em qualquer gravação | rollback total; log `ERRO` persistido |

Mensagens no padrão já usado no projeto (pt-BR), ex.:
`A aba "3. Conta Ação - AFCCT" não foi encontrada. Verifique se é o template correto da EMBRAPII.`

Sucesso retorna contagem por tipo:
`33 projetos financeiros e 10 KPIs importados para 2T/2024.`

## 8. Painel anual substituído

`apps/accountability/panel.py` devolve **o mesmo DTO** de
`planning.services.painel()` — chaves `ano, base, unidade, rotulo_periodo,
cards[4], graficos{ppi,at,outras}, tabela{grupos}, consolidado` — para que
`_panel.html`, `pilares-table.html` e os filtros de SVG continuem sem mudança.

Seleção: `?acompanhamento=<pk>`; sem parâmetro usa o acompanhamento mais
recente; **sem nenhum acompanhamento no banco, cai no fluxo legado
`PlanoAnual`** (assim os testes e a seed existentes seguem verdes).

- `base=financeiro` — por pilar a partir de `origem in ("TAB. 1","TAB. 9")`;
  por ano a partir de `origem="TAB. 1.1"` quando existir. PPI: previsto =
  `recurso_ou_meta`, executado = `realizado`. AT/Outras: previsto = `captado`,
  executado = `realizado` (RN-018). Sem linha anual ⇒ `None`.
- `base=fisico` — uma linha por KPI, agrupada por pilar, exibindo a unidade no
  rótulo. Ano: previsto = `meta_<ano>`; executado = `executado_2024/2025`, e
  `None` para 2026/2027 (só há projeção). `todos`: previsto = `meta_total`,
  executado = `acumulado`.
- Linhas com valor `None` renderizam `—` (`numero_curto(None)` já faz isso) e
  recebem `pct=None`, `faixa="neutra"`, `saldo=None`.
- Nenhuma soma entre unidades diferentes; percentuais/projeções KPI nunca entram
  como "executado".

## 9. Override manual

- Mesmo formulário e mesmo nome de campo `v__{ano}__{base}__{codigo}__{campo}`;
  `codigo` = pilar (financeiro) ou código do KPI (físico).
- Campo oculto `acompanhamento=<pk>` no `editor.html` altera o destino do POST.
- Valor vazio ⇒ **remove** o override (restaura o importado).
- Ação `restaurar` ⇒ remove todos os overrides do acompanhamento.
- Precedência: override > importado. Percentual/saldo/farol recalculados.
- Permissões: `pode_editar_painel` + `pilares_editaveis_painel` (pilar do KPI
  entra no escopo do PontoFocal).
- Auditoria: `EDITAR_OVERRIDE_PRESTACAO` / `RESTAURAR_OVERRIDE_PRESTACAO`.

## 10. Upload

- Rota `POST/GET /financeiro/prestacao/importar/`
  (`config/urls.py` → `path("financeiro/prestacao/", include("apps.accountability.urls"))`).
- Permissão `pode_importar_financeiro` (Master/Admin).
- Campos: `arquivo` (`.xlsx`), `centro`, `periodo_referencia`, submit.
- Detecção de tipo pela assinatura das abas (não pelo nome do arquivo).
- UI no padrão do projeto: Django templates + HTMX/Alpine, estados
  `enviando/processando/sucesso/erro`, histórico de importações.
- Ponto de entrada linkado na página existente `finance:importar`.

## 11. Validação e testes

- Arquivos reais: `mockup/exemplos_arquivos/FINANCEIRO GERAL.xlsx`,
  `mockup/exemplos_arquivos/Indicadores Gerais do Termo de Retificação do PE.xlsx`
  e `Acompanhamento Financeiro (v2).xlsx` (raiz).
- `apps/accountability/tests/test_ingestion.py` compara valores extraídos com
  valores esperados hardcoded a partir da leitura dos arquivos (acima).
- O v2 real **não tem lançamentos** nas abas 3–9 ⇒ fixtures sintéticas de linha
  cobrem o parsing de despesas (uma por layout: pessoal, NF, AT/entrada-saída,
  infraestrutura, ampliação).
- Cobrir ainda: reenvio idempotente, rollback sem gravação parcial,
  atualização isolada por tipo de fonte, permissão 403, arquivo `.csv`
  rejeitado, mensagens de erro amigáveis, divergência de metadado, precedência e
  remoção de override, painel legado sem acompanhamento.

## 12. Fora de escopo

Aba `10. Equipe` e demais abas não financeiras do v2 (11–18); pandas, FastAPI,
Pydantic, filas, jobs assíncronos; alteração dos fluxos mensais; recálculo de
fórmulas do Excel; remoção/alteração de `PlanoAnual` e seus registros;
**migração da página `/pilar/<pk>/`**, que permanece no fluxo legado
(`painel_pilar` lê `PlanoAnual`) nesta entrega.
