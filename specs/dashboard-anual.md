# Plano de teste Playwright — Dashboard Anual (L1)

Suite nova: `tests/e2e/dashboard_anual.spec.ts` (Chromium, serial, baseURL `http://127.0.0.1:8000`).
Pré-condição: `seed_demo` aplicado. Login como Master (exceto onde indicado).
`data-testid` a implementar nos templates: `app-header`, `year-select`, `base-toggle`,
`context-chips`, `dashboard-panel`, `kpi-ppi`, `kpi-at`, `kpi-outras`, `kpi-total`,
`chart-fonte-ppi|at|outras`, `chart-rodape-ppi|at|outras`, `pilares-table`,
`farol-modal`, `farol-abrir`, `editor-dados`, `btn-toolbar-*`, `sidebar`, `app-footer`.

## Casos por AC

| # | AC | Passos | Asserções |
|---|---|---|---|
| T01 | AC-039 | GET `/` sem params | chips "Acumulado 2024 a 2027 / Financeiro / R$ milhões"; `kpi-ppi` "R$ 40 mi", "de R$ 60 mi projetados", badge 67% |
| T02 | AC-040 | select `Ano 3: 2026` | cards/tabela/rodapés com valores 2026; chip "Ano 3: 2026"; categoria "Ano 3 2026" com destaque (atributo/classe) |
| T03 | AC-040 | percorrer Anos 1,2,4 + voltar a "Todos os anos" | valores = matriz L0 por ano; sem erro de console |
| T04 | AC-041 | ativar base "Físico" | unidades "metas"; `th-1/th-2` "(METAS)"; chip "quantidade de metas"; consolidado 34/68 (50%) |
| T05 | AC-041 | voltar a "Financeiro" | R$ mi restaurado em todo o painel |
| T06 | AC-042 | GET `/?ano=2025&base=fis` + reload | painel = Ano 2 + Físico; select/segmentado refletem; back/forward preserva |
| T07 | AC-048 | GET `?ano=2030`, `?base=x`, `?ano=abc` | 302 para `/?ano=todos&base=fin`; status 200 final sem exceção |
| T08 | AC-049 | GET `/?periodo=2026-06-01` | 301 para `/?ano=2026&base=fin`; ano fora de 2024–2027 ⇒ `todos` |
| T09 | AC-043 | estado padrão, linha Infraestrutura | dot + "Meta atingida"; PDI "Execução parcial"; ACS "Execução crítica" |
| T10 | AC-043 | `?ano=2024&base=fis`, linha FCRH (47%) | "Execução crítica" (valida faixa por estado) |
| T11 | AC-044 | clique em `farol-abrir` | modal visível, foco dentro; ESC fecha e devolve o foco ao gatilho; X e backdrop também fecham |
| T12 | AC-045 | `?ano=2026&base=fis` + download CSV | arquivo com `Bloco;Item;…;Período;Valor`, BOM, só base física e período 2026 |
| T13 | AC-045 | mesmo estado + `emulateMedia print` | header de impressão com "Ano 3: 2026 · Físico" visível; sidebar/toolbar/editor ocultos |
| T14 | AC-046 | login Liderança | sem `editor-dados`/botão Editar; POST direto ⇒ 403 |
| T15 | AC-046 | login PontoFocal (1 pilar) | edita o próprio pilar (200); pilar alheio ⇒ 403 |
| T16 | AC-046 | login Master edita PDI 2026 fin | recálculo imediato + registro em `/auditoria/` |
| T17 | AC-047 | axe-core em `/`, `?ano=2026&base=fin`, `?ano=todos&base=fis` | 0 violações critical/serious |
| T18 | AC-050 | `seed_demo` 2× + GET 10 estados | valores = matriz L0; `assertNumQueries` ≤ 20 (Django) |
| T19 | RF-117 | sidebar | grupos Pilares/Prestação de contas/Operação/Gestão colapsam com `aria-expanded`; item ativo correto; off-canvas < lg |
| T20 | RF-119 | `/prestacao/mensal/` | heatmap, avisos, destaques, status e gráficos mensais intactos |

## Reapontamento (L4/L8)

`dashboard.spec.ts`, `dashboard_r2.spec.ts`, `shell.spec.ts`, `a11y_r6.spec.ts`,
`fixes_r7.spec.ts`, `screenshots.spec.ts`: trocar base `/` por `/prestacao/mensal/`
preservando asserções; nada do comportamento mensal pode mudar.
