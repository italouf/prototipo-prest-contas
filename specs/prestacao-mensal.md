# Spec — Prestação mensal no padrão Geral/Pilares (L20)

Suite: `tests/e2e/dashboard_r2.spec.ts` (reescrita) + `apps/core/tests_prestacao.py` (novo).
Pré-condição: `seed_demo` (períodos 2026-05 fechado, 2026-06 aberto, 2026-07 planejado;
financeiro jan–jun/2026; lançamentos aprovados em maio, pendências em junho).

## 1. Contrato de URL (`core:mensal`, path inalterado)

| # | Entrada | Saída |
|---|---|---|
| U01 | GET `/prestacao/mensal/` | 200, período padrão (aberto/reaberto mais recente; senão mais recente) |
| U02 | GET `/prestacao/mensal/?periodo=2026-05-01` (+ `&destaque_pilar=<pk>` opcional) | 200, deep-link com push-url |
| U03 | `?periodo=` inválido ou sem `Periodo` | **302** para `/prestacao/mensal/?periodo=<padrão>` (sem `destaque_pilar`) |
| U04 | `destaque_pilar` inválido | ignorado (mostra todos) |
| U05 | `HX-Request` sem `HX-Boosted` | fragmento `_fragmento_mensal.html`; com boost, página completa (reuso de `_hx_parcial`) |

`periodo_selecionado()` (utils) e `periods:acao` (`next=core:dashboard`) **inalterados**.

## 2. Serviço `apps/core/prestacao.py::contexto_mensal(periodo, usuario, destaque_pilar="")`

Chaves (superset legado — `cards`, `chart_financeiro`, `chart_mensal`, `linhas`,
`periodo`, `periodos`, `destaques`, `kpis`, `heatmap`, `avisos`, `status_counts`
permanecem para os testes atuais):
- `painel_mensal`: `{rotulo_periodo, status, n_pilares, n_indicadores}` (ramo do header).
- `kpis`/`heatmap`: `nivel` passa a usar as faixas do anual
  (`ok ≥90 · parcial ≥50 · crítica <50 · neutra`, via `planning.services.faixa`);
  atualiza `test_heatmap_classifica_niveis`.
- YTD/ANUAL sem lançamento aprovado no ano ⇒ `realizado/percentual = None`
  (sem dado ≠ zero; conta como pendente); heatmap `resumo` = "N/M com
  execução ≥ 90%" com M = indicadores com meta.
- `status_counts`: migrado para `prestacao.py` (1 query agregada; RBAC por `pilares_visiveis`).
- `geo_mensal`/`geo_pilares`: geometria via `apps/core/charts.py` (séries em **R$ mi**, `numero_curto`).
- `chart_mensal_json`/`chart_financeiro_json`: **removidos** do contexto
  (atualiza `test_dashboard_expoe_kpis_heatmap_e_avisos` → asserts `geo_mensal`/`geo_pilares`).
- Orçamento: página mensal ≤ 30 queries (`test_dashboard_dentro_do_orcamento_de_queries` mantido).

## 3. Geometria genérica (`apps/core/charts.py`)

`geometria_barras(eixos, serie_a, serie_b, destaque, dimensoes)` — N grupos,
`divisor` opcional; `apps/planning/charts.py::geometria_fonte` delega com os
5 eixos + divisor=4 (**saída idêntica**; guardas: `GeometriaGraficosTestes` +
paridade e2e das 10 combinações). `geometria_consolidado` inalterado.
`chart-fonte.html` ganha `eixo_rotulo` (default `"por ano"`),
`legenda_a` (default `"Projetado ou captado"`), `legenda_b` (default `"Executado"`).

## 4. Header (`app_header` + `_controles_mensal.html` + `_fragmento_mensal.html`)

- Ramo `{% elif painel_mensal %}`; `barra-toggle` passa a existir no mensal
  (atualiza `test_toggle_da_barra_so_existe_com_painel`).
- Faixa 1: form período (`hx-target="#painel-mensal"`, `hx-select`, push-url,
  indicator; hidden `destaque_pilar`; mantém `data-testid="period-selector-dashboard"`
  e `period-option-<rótulo>`) + bloco Status (badge).
- Faixa 2: chips Período / Status / Pilares (`data-testid="context-chips"`).
- Faixa 3 (`role="toolbar"`): `Aprovar N pendentes` (**primary**, só se
  `pode_aprovar` e ENVIADO>0) → `entries:aprovacao`; ações de período
  (Abrir/Fechar/Reabrir, forms POST, ghost); `Relatório mensal` (ghost →
  `reports:mensal`); `Imprimir` (ghost).
- Alvo do swap `#painel-mensal` (`data-testid="painel-mensal"`); OOB
  `#dashboard-controls` com classe+testid espelhados do header (lição L19).
- Filtro de destaques vira swap do painel inteiro com push-url
  (`?periodo=&destaque_pilar=`); mantém `destaques-filtros`/`feed-destaques`.

## 5. Conteúdo (`mensal.html` casca + `_painel_mensal.html`)

- `print-cabecalho` (Período · Status); controles ocultos no print (regra vigente).
- `page-dashboard` + drawer **fora** do `#painel-mensal` (Alpine intacto).
- `avisos` (mantido, após o título).
- 6 KPI cards por pilar: mesma estrutura/DOM (`data-testid="kpi-<codigo>"`,
  `[data-kpi-card]`, `anim-entrada`, drawer via `pilar_drawer?periodo=`),
  com `farol-badge` + barra por faixa.
- 3 cards financeiros (`escala_ptbr`/`moeda_ptbr`).
- 2 SVG `chart-fonte`: "Captação × execução por mês — {ano}" (12 grupos,
  destaque no mês, `chart-mensal`, unidade R$ mi) e "Captação × execução
  por pilar — acumulado {ano}" (`chart-financeiro`).
- `status-distribuicao` (título "Lançamentos — {rótulo}" mantido; botão
  Aprovar move para a toolbar).
- Tabela consolidada por pilar/indicador + coluna **Farol** (badge) e Status
  do lançamento (mantido).
- Destaques + filtros (swap de painel).
- **Remove**: canvases `#grafico-mensal/#grafico-financeiro` e scripts JSON
  (`charts.js` e `meta chart-url` permanecem no base para o relatório).

## 6. Casos e2e (dashboard_r2 reescrito)

| # | Passos | Asserções |
|---|---|---|
| M01 | GET `/prestacao/mensal/` | 6 `[data-kpi-card]`, `kpi-pdi/at`, `heatmap`, `avisos`, `chart-mensal`, `status-distribuicao`; heading "Dashboard Executivo"; seção "Evolução financeira mensal"; farol visível nos cards |
| M02 | select `2026-05 — Fechado` (+ `__marcador`) | "Lançamentos — 2026-05", URL `periodo=2026-05-01`, sem reload |
| M03 | clica `kpi-pdi` | drawer + `drawer-pilar` com PDI-PROJ-INI; fecha |
| M04 | filtros AT/PDI nos destaques | `destaque_pilar=4` → "renovações"+"Arena QuIIN"; `=1` → "Arena QuIIN" sem "renovações" |
| M05 | timing | servidor < 1000ms |
| M06 | header | `dashboard-controls` com período/chips; toggle `barra-toggle` oculta/exibe; filtro pelo header faz swap |
| M07 | toolbar | "Aprovar N pendentes" → `/aprovacao/`; "Relatório mensal"; "Imprimir" |
| M08 | print | `print-cabecalho` visível, controles ocultos |
| M09 | axe | 0 critical/serious em `/prestacao/mensal/` |

## 7. Regressão a revalidar

`dashboard.spec.ts` (mantém títulos/seções/testids — sem mudança esperada),
`polish_r6.spec.ts` (skeleton, `quiin-entrada` em `kpi-pdi`, view transitions),
`shell.spec.ts` (navegação mensal/semestral, seletor de período, L19 —
toggle agora existe no mensal), `a11y_r6` (+ rota `/prestacao/mensal/`),
`portal.spec.ts`, `dashboard_anual.spec.ts`, `apps/{core,planning,entries,highlights,periods,reports}`.
