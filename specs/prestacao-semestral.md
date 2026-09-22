# Spec — Visão geral semestral no padrão Geral/Pilares (L21)

Suite: `tests/e2e/semestral.spec.ts` (nova) + `apps/core/tests_prestacao.py` (classe `SemestreTestes`).
Pré-condição: `seed_demo` (financeiro jan–mai/2026; lançamentos maio/junho; S1 = jan–jun, S2 = jul–dez).

## 1. Contrato de URL (`core:semestral`, path inalterado; nova `core:semestral_csv`)

| # | Entrada | Saída |
|---|---|---|
| S-U01 | GET `/prestacao/semestral/` | 200, default = semestre do período padrão (mesma regra do mensal: aberto mais recente) |
| S-U02 | GET `/prestacao/semestral/?ano=2026&semestre=1` | 200, deep-link com push-url |
| S-U03 | `ano` inválido/inexistente ou `semestre` ∉ {1,2} (incl. legado `?ano=` sem semestre) | **302** para `/prestacao/semestral/?ano=<ano>&semestre=<sem>` canônicos (ano válido preservado; senão ano do período padrão) |
| S-U04 | `HX-Request` sem `HX-Boosted` | fragmento `_fragmento_semestral.html`; com boost, página completa |
| S-U05 | GET `/prestacao/semestral/dados.csv?ano=&semestre=` | CSV `;` + BOM (`Mês;Pilar;Indicador;Meta;Realizado;% Executado`), recorte RBAC; inválido ⇒ 302 para o CSV canônico |

## 2. Serviço `apps/core/prestacao.py::painel_semestral(ano, semestre, usuario)`

- `apps/core/calculos.py::itens_por_periodo(indicadores, periodos)` → `{pk: [itens]}` em **3 queries** (metas/lançamentos/somas YTD), mesma semântica de `itens_do_periodo`.
- Por pilar: só entram meses **com lançamento aprovado**; **YTD** usa o valor do
  **mês mais recente com lançamento** (não média de meses); **MENSAL** usa a
  média dos meses com lançamento; `pct` = média dos valores usados;
  `atingidos` = valores usados ≥100; `pendentes` = indicadores com meta no
  **último mês** do semestre sem lançamento aprovado; `meses` = meses do
  pilar com lançamento; `faixa` do anual. YTD sem lançamento no ano ⇒
  `realizado/percentual = None` (sem dado ≠ zero).
- Tabela por indicador usa `itens_do_periodo` do **último mês do semestre** (YTD p/ metas anuais).
- Financeiro somado no semestre (por mês e por pilar); séries em R$ mi; geometria `core.charts` (6 grupos; destaque = último mês com dados, senão None).
- Status = contagens agregadas no semestre; destaques = `DestaqueMensal` dos períodos (`[:6]`); `meses` = períodos do intervalo p/ drill-down.
- `painel_semestral`: `{rotulo_periodo: "1º semestre de 2026", ano, semestre, n_meses, n_pilares}`.
- Orçamento: página semestral ≤ **40** queries.

## 3. Header (`app_header` + `_controles_semestral.html` + `_fragmento_semestral.html`)

- Ramo `{% elif painel_semestral %}`; `barra-toggle` passa a existir (atualiza o guard Django).
- Faixa 1: Ano (select `data-testid="semestre-ano"`) + Semestre (segmentado 1º/2º, `data-testid="semestre-toggle"`, links `?ano=&semestre=` com hx para `#painel-semestral`).
- Faixa 2: chips Período (`1º semestre de 2026`) / Meses com dados (`N de 6`) / Pilares.
- Faixa 3 (`role="toolbar"`, `aria-label="Ações do semestre"`): `Baixar dados (CSV)` (ghost → `semestral_csv`) + `Imprimir` (ghost) + `Restaurar padrão` (ghost → `/prestacao/semestral/`). Sem primary (nada editável).
- Alvo `#painel-semestral` (`data-testid="painel-semestral"`); OOB espelhado (lição L19).
- Mensal ganha na toolbar `Ver semestre` (ghost → `semestral?ano=&semestre=` do período).

## 4. Conteúdo (`semestral.html` casca + `_painel_semestral.html`)

- `print-cabecalho`; 6 KPI cards por pilar (média do semestre + farol + meses) com `data-testid="kpi-sem-<codigo>"`; 3 cards financeiros do semestre; 2 SVG (`chart-fonte-meses`, `chart-fonte-pilares`); status agregado (`status-semestre`); tabela por pilar com farol (`tabela-semestre`); destaques (`feed-semestre`); **meses do semestre** (`meses-semestre`: rótulo + badge de status + link `core:mensal?periodo=`); empty states ("Sem dados neste semestre").
- `semestral.html` mantém o h1 "Prestação de contas — Semestral" (navegação e2e vigente).

## 5. Casos e2e (`semestral.spec.ts`, S01–S10)

S01 default Deep-link e chips · S02 troca ano/semestre sem reload + URL · S03 KPIs/farol/tabela · S04 SVG por mês e por pilar · S05 drill-down mês → mensal e "Ver semestre" de volta · S06 CSV (header + BOM + só escopo) · S07 print · S08 axe · S09 header (controles + barra-toggle) · S10 RBAC focal (só próprio pilar).
S01 não fixa o semestre default (banco e2e compartilhado sofre mutação de outros fluxos; o default = semestre do período padrão é travado no Django `test_padrao_eh_semestre_do_periodo_aberto`).

## 6. Regressão a revalidar

`shell.spec.ts` (navegação + L19), `dashboard_r2` (M01–M09), `a11y_r6` (+ rota semestral), `tests_navegacao.py` (reescrever `SemestralViewTestes`), demais suites Django/e2e intactas.
