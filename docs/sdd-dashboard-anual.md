# SDD — Dashboard Anual QuIIN (filtro por ano + base Financeiro/Físico)

Data: 2026-09-17 · Status: implementado (loops L0–L8 concluídos)
Fonte de verdade visual: `mockup/gestao_quiin_dashboard_17092026.html` (+ `mockup/logos.png`)
Matriz de estados validada no L0: `docs/retrofit/evidencias/dashboard-anual/loop-0/matriz-estados.md`
Plano de teste: `specs/dashboard-anual.md`

## 1. Escopo e delta

**Estado atual:** dashboard executivo mensal em `/` (`templates/home.html` + `apps/core/views.py:dashboard`),
filtro por mês (`?periodo=`), KPIs por pilar (média de %), heatmap, destaques, gráficos Chart.js,
distribuição de status, consolidado por pilar. Banco sem conceito de ano-safra e sem "projetado".

**Estado alvo:** `/` passa a ser o painel anual do mockup — filtro ANO (Todos/2024–2027) + seletor
de BASE (Financeiro/Físico), 4 cards KPI, 3 gráficos por fonte, tabela gerencial com farol,
gráfico consolidado, modal de metodologia, modo de edição auditado, CSV/impressão/download
refletindo os filtros, app-header global, sidebar reagrupada, footer institucional com logos.
O dashboard mensal atual migra intacto para `/prestacao/mensal/` (e no L20 é
reformulado no padrão do painel anual — ver `specs/prestacao-mensal.md`).

**Fora de escopo:** alterar fluxos mensais (lançamentos, períodos, CSV financeiro, relatório A4,
kanban, CRM, talentos, destaques, auditoria); novas dependências; novas cores fora dos tokens.

## 2. Requisitos (continuação da numeração vigente)

### RF (RF-107+)
| ID | Requisito | Onde |
|---|---|---|
| RF-107 | Filtro ANO no painel: Todos os anos / Ano 1: 2024 … Ano 4: 2027 | app-header + view |
| RF-108 | Seletor de base de análise: Financeiro (padrão) / Físico | app-header |
| RF-109 | 4 cards KPI reativos a ano+base (PPI, AT, Outras, Consolidado) | `planning.services` |
| RF-110 | 3 gráficos por fonte + gráfico consolidado, com destaque do ano | SVG server-side |
| RF-111 | Tabela gerencial por pilar com farol (faixas 90/50) | `planning.services` |
| RF-112 | Modal "Farol de execução: metodologia e leitura" (Anexo B) | componente + Alpine |
| RF-113 | Edição dos valores anuais com permissão por papel/pilar e auditoria | `planning.views` |
| RF-114 | Baixar dashboard (HTML standalone) e Baixar dados (CSV) da visão corrente | `planning.views` |
| RF-115 | Impressão A4 refletindo os filtros correntes | print CSS |
| RF-116 | Footer institucional com logos + textos do Anexo C | `app_footer` |
| RF-117 | Sidebar com IA do mockup + grupos Operação/Gestão, colapsável | `c-layout.sidebar` |
| RF-118 | Deep-link `?ano=&base=`, validação backend, redirects 301/302 | views |
| RF-119 | Dashboard mensal preservado em `/prestacao/mensal/` + visão semestral mínima | `core.views` |

### RNF (RNF-011+)
| ID | Requisito |
|---|---|
| RNF-011 | Somente tokens de cor existentes; nenhum hex novo (REGRA DE OURO); mapeamento §7 |
| RNF-012 | Gráficos do painel anual em SVG server-side (paridade, impressão, export, testabilidade) |
| RNF-013 | Render do painel em ≤ ~20 queries (alvo real: ≤ 5) |
| RNF-014 | axe-core sem violações critical/serious nos 3 estados de referência |
| RNF-015 | `seed_demo` idempotente reproduzindo o Anexo A nos 10 estados |

### RN (RN-016+)
- **RN-016:** todo o painel (cards, gráficos, tabela, chips, rodapés, CSV, impressão, download)
  reage aos dois filtros (ano + base).
- **RN-017:** "Todos os anos" = acumulado 2024–2027 (soma dos anos 1–4).
- **RN-018:** % PPI = executado ÷ **projetado**; % AT e Outras = executado ÷ **captado**;
  consolidado = (exec PPI+AT+OF) ÷ (proj PPI + capt AT + capt OF).
- **RN-019:** farol ≥ 90% "Meta atingida" · 50–89% "Execução parcial" · < 50% "Execução crítica",
  sempre dot + rótulo textual.
- **RN-020:** denominador zero ⇒ exibir "—" com `aria-label="sem meta no período"`; nunca
  dividir por zero nem exibir exceção.
- **RN-021:** edição do plano: Master/Admin tudo; PontoFocal só pilares vinculados (RN-012);
  Liderança/Auditor somente leitura (POST ⇒ 403); toda alteração auditada (RN-011).
- **RN-022:** filtro por mês permanece só nos fluxos mensais; o header usa ano+base.

### US (US-006+)
| ID | História |
|---|---|
| US-006 | Como Liderança, quero filtrar o painel por ano e base para acompanhar a execução do plano |
| US-007 | Como Master, quero editar os valores anuais com auditoria e ver o recálculo imediato |
| US-008 | Como Auditor, quero exportar CSV e imprimir refletindo exatamente os filtros correntes |
| US-009 | Como PontoFocal, quero editar apenas os valores dos meus pilares |

### AC (AC-039+)
| ID | Critério (Gherkin em `specs/dashboard-anual.md`) |
|---|---|
| AC-039 | Estado padrão: chips + card PPI "R$ 40 mi de R$ 60 mi · 67%" |
| AC-040 | Filtro por ano reage em todo o painel + chip + destaque da categoria |
| AC-041 | Base Físico: unidades "metas", cabeçalhos "(METAS)", consolidado 34/68 (50%) |
| AC-042 | Deep-link `?ano=2025&base=fis` renderiza Ano 2 + Físico (inclusive reload) |
| AC-043 | Farol: Infraestrutura 90% ⇒ dot + "Meta atingida" |
| AC-044 | Modal abre com foco interno, fecha por ESC retornando o foco |
| AC-045 | CSV e impressão refletem Ano 3: 2026 + Físico |
| AC-046 | Sem permissão: sem botão Editar e POST ⇒ 403 |
| AC-047 | axe-core limpo nos estados padrão, Ano 3+Fin, Todos+Fis |
| AC-048 | URL inválida (`?ano=2030`, `?base=x`) ⇒ 302 para o default, sem exceção |
| AC-049 | URL mensal antiga (`?periodo=2026-06-01`) ⇒ 301 para o ano equivalente |
| AC-050 | Seed reproduz o Anexo A nos 10 estados; render em ≤ 20 queries |

## 3. Modelo de dados

Novo app `apps/planning` (domínio: plano plurianual). Registro canônico em `docs/modelo-dados.md`.

```python
class PlanoAnual(models.Model):
    ANOS  = [(2024, "Ano 1: 2024"), (2025, "Ano 2: 2025"),
             (2026, "Ano 3: 2026"), (2027, "Ano 4: 2027")]
    BASES = [("financeiro", "Financeiro"), ("fisico", "Físico")]

    ano            = PositiveSmallIntegerField(choices=ANOS)
    pilar          = FK("pillars.Pilar", related_name="plano_anual")
    base           = CharField(max_length=12, choices=BASES)
    previsto       = DecimalField(12, 2, default=0)  # projetado (PPI) | captado (AT/Outras)
    executado      = DecimalField(12, 2, default=0)
    atualizado_em  = DateTimeField(auto_now=True)
    atualizado_por = FK(AUTH_USER_MODEL, null=True, on_delete=SET_NULL)
    # Meta: unique_together(ano, pilar, base) + CheckConstraints previsto/executado >= 0
```

48 linhas (6 pilares × 4 anos × 2 bases), seed idempotente no `seed_demo`.
Campo único `previsto` com rótulo derivado: "Projetado" se pilar em
`PILARES_PPI = (PDI, FORMACAO, STARTUPS, INFRA)`, "Captado" se AT/OUTRASFONTES.
**Decisão (ver `docs/decisoes.md`):** execução é *snapshot de plano*, não derivada do
operacional — garante o Anexo A exato sem reescalar os fluxos mensais (blast radius mínimo).
Migração: apenas `planning/0001_initial.py` (sempre `makemigrations planning` — ver risco §9).

## 4. Contrato de URLs / views / forms

| Rota | View | Comportamento |
|---|---|---|
| `GET /` | `core.views.dashboard` (reescrita) | `?ano=todos\|2024..2027&base=fin\|fis`; `Form` próprio com `clean()`; inválido ⇒ 302 default; `?periodo=` legado ⇒ 301; `HX-Request` ⇒ partial `#dashboard-panel` |
| `GET /prestacao/mensal/` | `core.views.mensal` | prestação mensal no padrão do anual (L20: `?periodo=` canônico, controles no header, SVG, farol; ver `specs/prestacao-mensal.md`) |
| `GET /prestacao/semestral/` | `core.views.semestral` | visão mínima (agrega 6 meses) |
| `POST /plano-anual/aplicar/` | `planning.views.aplicar` | grid ano×pilar×base, validação backend, atômico, auditoria por linha; `acao=baixar` ⇒ responde o HTML standalone |
| `GET /plano-anual/dados.csv` | `planning.views.csv` | visão corrente; `;`, BOM, UTF-8; colunas `Bloco;Item;Indicador;Unidade;Período;Valor` |
| `GET /plano-anual/dashboard.html` | `planning.views.export_html` | HTML standalone da visão corrente (CSS inline + sprite inline; fontes degradam p/ sistema) |
| pilar/AT/talentos/reports | existentes | itens da sidebar passam `?ano=&base=`; views de pilar exibem o contexto anual |

Cálculos só em `planning/services.py` (+ `planning/charts.py` p/ geometria SVG); templates apresentam.

## 5. Componentes cotton (novos, em `templates/components/` + catálogo `/dev/design-system/`)

`layout/app_header` (global, substitui `topbar`), `layout/app_footer`, `dashboard/panel`
(`#dashboard-panel`, alvo do swap htmx), `dashboard/kpi_card`, `dashboard/chart_fonte`,
`dashboard/chart_consolidado`, `dashboard/pilares_table`, `dashboard/farol_badge`,
`dashboard/context_chips`, `dashboard/modal_farol`, `dashboard/editor`.
Páginas: `templates/dashboard/anual.html` (novo `/`), `templates/dashboard/mensal.html`
(conteúdo atual do `home.html`), `templates/dashboard/semestral.html`.

## 6. Matriz de estados

Canônica no L0 (`docs/retrofit/evidencias/dashboard-anual/loop-0/matriz-estados.md`):
**Anexo A confirmado sem correções.** Resumo: FIN acumulado 40/60 (67%), AT 2/7,75 (26%),
Outras 0/7,75 (0%), consolidado 42/75,5 (56%); FIS acumulado 32/52 (62%), AT 2/8 (25%),
Outras 0/8 (0%), consolidado 34/68 (50%). Per-ano e por pilar conforme tabelas do §2 do L0.

## 7. Mapeamento mockup → token (REGRA DE OURO)

| Mockup | Token existente |
|---|---|
| barras "Projetado ou captado" `#004691` | `quiin-royal` |
| barras "Executado" `#29abe2`, série AT, card 2 | `quiin-sky` |
| série Outras fontes `#7c3aed`, card 3 | `quiin-violet` (não o `pillar-outrasfontes` verde — decisão registrada) |
| card 1 | `quiin-blue`; card 4 | `quiin-deep-purple` |
| farol ok `#059669/#10b981` | `status-aprovado` + `status-aprovado-texto` |
| farol parcial `#b45309/#f59e0b` | `status-pendente` + `status-pendente-texto` / `amber-400` |
| farol crítica `#c2410c/#f97316` | `red-500`/`red-600` — **sem token laranja no projeto**; usa a convenção de crítico já presente em `home.html` |
| fundos/hover `#f1f5f9`, bordas `#e2e8f0` | `bg-quiin-mist/50`, `border-border` |
| Inter | Montserrat (UI) + JetBrains Mono (`.numerico`, todos os valores) |
| botão em edição `#e30613` | `variant="danger"` do `c-ui.button` |

## 8. Riscos e divergências assumidas

1. Modal do mockup sem `role="dialog"`/focus trap ⇒ implementar acessível (AC-044).
2. "Restaurar padrão" reseta **filtros** (o mockup também zera os dados — destrutivo; não reproduzir).
3. Edição persiste no banco com auditoria (mockup usa localStorage).
4. `tailwind.css` é commitado ⇒ rebuild a cada loop com classes novas.
5. `db.sqlite3` local tem `talentos.0002` fantasma ⇒ `makemigrations planning` sempre.
6. `logos.png` (4420×960, fundo `#E9E9E9`): vendorizar recorte 4277×651 reduzido.
7. Specs e2e atuais de `/` serão re-apontadas p/ `/prestacao/mensal/` (L4/L8).
8. Tooltips das barras: `<title>` nativo no SVG (acessível, sem JS) em vez do `#tip` mouse-only.
9. Sidebar (L9, diverge da IA do mockup por decisão do usuário): **Pilares só com os
   4 pilares PPI** (PDI, Formação FCRH, ACS, Infraestrutura); **Associação Tecnológica
   e Talentos em Gestão** (não são pilares). Gestão segue restrita
   (`pode_ver_auditoria` ou Master/Admin); AT/Talentos mantêm o gate
   `pode_lancar or pode_aprovar` — PontoFocal perde o link direto (acesso por URL
   preservado), Liderança inalterada.
10. Render numérico (L9): geometria SVG e `value` de `<input type="number">` saem
    **sem localização** (`{% localize off %}` / `|unlocalize`) — pt-BR insere
    vírgula e invalida os atributos; rótulos visíveis seguem em pt-BR
    (`numero_curto`).
11. Shell (L10, paridade com o mockup): topbar full-width acima de tudo; sidebar
    abaixo do header sem scroll exclusivo (acompanha a página; drawer mobile
    mantém scroll próprio); marca mantida na sidebar; controles do painel em
    três faixas à direita (filtros Ano+Base acima, chips, ações em linha
    própria); só "Editar dados" é primário, demais botões brancos como
    "Restaurar padrão" (L18); a barra pode ser ocultada por botão-ícone no
    topbar, com estado persistido (L19); rodapé full width.

## 9. Painel por pilar (L12–L16)

Mesmo visual do painel geral, recortado por pilar, reagindo a `?ano=&base=`.
Pilares com painel: **PDI, Formação FCRH, ACS, Infraestrutura, Associação
Tecnológica** (Outras Fontes fica fora). Sem mudança de schema — reuso de
`planning.PlanoAnual` (ver `docs/modelo-dados.md`).

### 9.1 Requisitos (continuação)

**RF-120..127**

| ID | Requisito | Onde |
|---|---|---|
| RF-120 | Painel anual por pilar na página do pilar: 4 cards (Previsto/Captado, Executado, Saldo, % + farol), gráfico previsto×executado por ano + acumulado, tabela por ANO (Ano 1..4 + Total) | `painel_pilar` + componentes |
| RF-121 | Filtros ANO + base no header do pilar reagindo a todo o painel (chips incluídos) | `_controles_pilar` + fragmento htmx |
| RF-122 | Seção mensal atual preservada abaixo ("Prestação mensal do pilar") | `core.views.pilar` |
| RF-123 | Sidebar: os 5 pilares clicáveis em Pilares; Funil AT em Gestão | `c-layout.sidebar` |
| RF-124 | Edição escopada ao pilar (Master/Admin tudo; PontoFocal só o seu) | `planning:aplicar` com `pilar=` |
| RF-125 | CSV do pilar refletindo ano+base | `planning:csv` com `pilar=` |
| RF-126 | HTML standalone do pilar | `planning:export_html` com `pilar=` |
| RF-127 | Impressão A4 do pilar com cabeçalho do pilar + filtros; Restaurar volta a `/pilar/<pk>/` | print CSS + `_controles_pilar` |

**RNF-016..019**

| ID | Requisito |
|---|---|
| RNF-016 | Reuso dos componentes do painel geral (`kpi-card`, `chart-fonte`, `farol-badge`, `geometria_fonte`); sem CSS/cores paralelos |
| RNF-017 | Render do pilar em ≤ ~25 queries |
| RNF-018 | axe-core sem critical/serious em `/pilar/1/` e `/pilar/4/?ano=2026&base=fis` |
| RNF-019 | Paridade absoluta com o Anexo A por pilar/ano/base (fixture + matriz L0) |

**RN-023..026**
- **RN-023:** % do pilar usa **projetado** (PPI) ou **captado** (AT) — extensão da RN-018.
- **RN-024:** farol pelas faixas 90/50 (RN-019); **RN-025:** denominador zero ⇒ "—" (RN-020).
- **RN-026:** edição por pilar só para quem edita aquele pilar (RN-021); POST fora do escopo ⇒ 403.

**US-010..012**

| ID | História |
|---|---|
| US-010 | Como Liderança, quero ver o painel anual de cada pilar filtrado por ano e base |
| US-011 | Como PontoFocal, quero editar somente os valores do meu pilar |
| US-012 | Como Auditor, quero baixar CSV/HTML do pilar refletindo os filtros |

**AC-051..060** (Gherkin em `specs/painel-pilar.md`): AC-051 PDI acumulado FIN (29×21, 72% parcial);
AC-052 Ano 3:2026 recalcula (PDI 10×8); AC-053 base Físico (PDI 18×13, "metas");
AC-054 deep-link `/pilar/1/?ano=2025&base=fis`; AC-055 AT usa **Captado** (7,75×2, 26%);
AC-056 sidebar (5 em Pilares; Funil AT em Gestão); AC-057 CSV do pilar; AC-058 impressão
com cabeçalho do pilar; AC-059 editor escopado + 403; AC-060 axe nos dois estados.

### 9.2 Contrato de URL

| Rota | Comportamento |
|---|---|
| `GET /pilar/<pk>/?ano=todos\|2024..2027&base=fin\|fis` | Painel anual do pilar + seção mensal abaixo; inválido ⇒ **302** para `/pilar/<pk>/?ano=todos&base=fin` (preservando `periodo`) |
| `GET /plano-anual/dados.csv?ano&base&pilar=<pk>` | CSV do pilar (`Pilar;Ano;Previsto;Executado;Saldo;% Executado`; valida visibilidade ⇒ 403) |
| `GET /plano-anual/dashboard.html?ano&base&pilar=<pk>` | HTML standalone do pilar |
| `POST /plano-anual/aplicar/` com `pilar=<pk>` | Edição escopada; redireciona ao painel do pilar |

### 9.3 Componentes e reuso

Novos: `dashboard/tabela-anual-pilar` (linhas por ano + Total), `dashboard/painel-pilar.html`
(`#painel-pilar`), `_controles_pilar.html`, `_fragmento_pilar.html`,
`standalone_pilar.html`. Reusados sem alteração: `kpi-card`, `chart-fonte`,
`farol-badge`, `modal-farol`, `geometria_fonte`, `PainelFiltroForm`, chips.
Helper compartilhado de filtros/redirect com o painel geral; `contexto_pilar()`
para painel + HTML. Banner `contexto-anual` sai (chips assumem o contexto).

### 9.4 Matriz por pilar (derivada do Anexo A — fonte de verdade p/ testes)

FIN acumulado: PDI 29×21 (72% parcial); FCRH 14×7 (50%); ACS 7×3 (43% crítica);
Infra 10×9 (90% atingida); AT 7,75×2 (26% crítica).
FIS acumulado: PDI 18×13 (72%); FCRH 15×7 (47% crítica); ACS 9×3 (33% crítica);
Infra 10×9 (90%); AT 8×2 (25% crítica).
Ano 3:2026 FIN: PDI 10×8 (80%); FCRH 4×2 (50%); ACS 2×1 (50%); Infra 4×4 (100%);
AT 3×1 (33%). FIS: PDI 6×5 (83%); AT 3×1 (33%).

### 9.5 Loops

| Loop | Entrega | DoD |
|---|---|---|
| **L12** | `painel_pilar` + testes (10 estados × 5 pilares, rótulo Projetado/Captado, faixas, zero, ≤2 queries) | unit verdes; `loop-12/` |
| **L13** | componentes + view/redirects + filtros/chips/fragmento | deep-link/troca de estado; axe; screenshots |
| **L14** | AT em Pilares, Funil AT em Gestão, testes de navegação | e2e sidebar; acessos preservados |
| **L15** | edição escopada, CSV, HTML, impressão, restaurar | e2e + evidências |
| **L16** | regressão total, paridade por pilar, docs finais | tudo verde + relatório |
