# Decisões e premissas assumidas

## Premissas

1. Competência = primeiro dia do mês (`2026-06-01`); rotulo `2026-06`.
2. Períodos demo: `2026-05` (fechado), `2026-06` (aberto), `2026-07` (planejado).
   Os períodos `2026-01` a `2026-04` existem apenas para o financeiro YTD.
3. Dashboards consolidam apenas lançamentos **APROVADOS**.
4. Meta MENSAL compara o valor do mês; meta ANUAL/ACUMULADA compara o
   somatório YTD (jan/ano até o período).
5. Indicador TXT não possui percentual de execução.
6. `EMBRAPPI` (erro de digitação do exemplo) é normalizado para `EMBRAPII`.
7. Importação CSV é **atômica**: qualquer linha inválida rejeita o arquivo inteiro.
8. Renovações (indicador `AT-RENOVACOES`) ficam separadas de `AT-CNPJ-NOVOS`
   e não entram no cálculo da meta de CNPJs novos (RN-007).
9. `relatorio.html` é **somente contexto textual/engenharia**. Não é template,
   não é fonte de CSS e não é dependência de execução do Django.
10. Os dados do relatório executivo (valores de R$ 60 mi etc.) foram recriados
    como dados fictícios de demonstração, sem cópia de dados reais.

## Decisões técnicas

1. Django 5.2 LTS (instalado: 5.2.17) com Python 3.14 (ambiente local).
2. Apps por domínio: `accounts, core, pillars, indicators, periods, entries,
   finance, reports, audit, seed` (conforme estrutura sugerida no prompt).
3. Usuário customizado (`AUTH_USER_MODEL = accounts.User`) para evolução futura.
4. Permissões centralizadas em `apps/core/permissions.py`, validadas nas views.
5. Snapshot lógico do fechamento em `Periodo.snapshot_json` (JSONField).
6. Formatação monetária/número via filtros Django (l10n pt-BR), sem libs extras.
7. `LocaleMiddleware` + `pt-br` para mensagens traduzidas do Django.
8. Playwright é ferramenta de QA opcional (CLI); a app roda apenas com Python + Django.

## Pontos adiados (fases futuras)

- Módulo completo de Associação Tecnológica (empresas, contratos, pipeline).
- Kanban estratégico, banco de talentos, playbooks.
- Destaques mensais e foco de próximos 30 dias.
- Notificações e pendências por e-mail.
- API REST (DRF) e integração com BI da Embrapii.
- Exportação Excel avançada e PDF gerado por biblioteca.
- Backup, autenticação SSO, produção e hardening.

## Registros da sessão de implementação

### Skill impeccable
- A skill está no projeto em `.opencode/skills/impeccable/` (e `.github/skills/impeccable/`).
  As buscas iniciais por glob não alcançavam diretórios ocultos, então o Frontend
  Gate foi registrado como contrato e o frontend inicial seguiu o fallback.
- Após localizar a skill, o workflow foi executado: `context.mjs` → entrevista
  `init` (question tool) → `PRODUCT.md` criado (perfis, propósito, princípios,
  sem compromisso de marca) → playbooks `init.md`, `audit.md` e `craft-floor.md`
  carregados → detector mecânico `detect.mjs` executado.
- O detector encontrou 4 violações do craft-floor (side-tab accents: `border-left:
  4px` em alerts e título de pilar; borda de topo 3px em cards; borda inferior 3px
  no topbar), todas corrigidas em um único lote: accents removidos, alerts com
  borda fina + background tonal, cards sem borda colorida de topo, `:focus-visible`
  adicionado e touch targets aumentados (min-height 40px).
- Reexecução do detector: **0 findings**. Testes Django (26) e E2E Playwright (8) verdes.

### MCP Playwright
- `opencode.json` define o MCP `playwright-test` e agentes
  `playwright-test-planner/generator/healer`, que referenciam
  `.opencode/prompts/*.md` (agora presentes no projeto).
- Os agentes MCP não estavam expostos nesta sessão; a validação E2E foi
  executada via CLI Playwright em `tests/e2e/` (8 testes verdes em Chromium).

## Retrofit visual (R0 — 2026-09-10)

- Stack: Tailwind CSS v4 via `django-tailwind-cli` 4.8.0 (binário standalone
  pinado em 4.3.3, sem Node em runtime), `django-cotton` 2.7.2 (componentes),
  `django-template-partials` 25.3 (fragmentos HTMX) e `django-htmx` 1.29.0;
  HTMX 2.0.10, Alpine 3.17.2 e Chart.js 4.5.1 vendorizados em
  `static/js/vendor/` (sem CDN).
- `django_cotton` e `template_partials` usam `SimpleAppConfig` com **loaders
  explícitos** em `TEMPLATES` (partials → cached → cotton → filesystem/app_dirs):
  as auto-configurações dos dois pacotes não são composáveis entre si.
- Tailwind com `source(none)`: sem varredura automática do projeto (evitava
  capturar classes em `docs/`), apenas `@source` para `templates/` e `apps/`.
- Source CSS em `assets/styles/` (fora de `static/`) para evitar o check
  `django_tailwind_cli.W001`; `@font-face` em `static/css/fonts.css` servido
  diretamente e resolvido tanto em `static/` quanto em `staticfiles/`.
- Fontes: Panton **trial** aceita explicitamente para protótipo local não
  publicado (risco registrado); Myriad Pro convertida OTF→woff2 por script;
  JetBrains Mono (OFL) versionada. `font/` e `static/fonts/{panton,myriad-pro}`
  ficam fora do git.
- CSS legado isolado em `static/css/legado.css` via `@import ... layer(legado)`
  enquanto as telas antigas não migram (remoção prevista no R6).
- Testes Django passam a exigir `collectstatic` antes (manifest do Whitenoise),
  documentado em `docs/como-rodar.md`.
- Contraste AA corrigido nos badges (tokens `*-texto` escurecidos para tintas
  de 15%); gate automatizado com `@axe-core/playwright` (0 violações sérias).
- Loops do retrofit documentados em `docs/retrofit/loops.md` (R0–R6), sem
  colidir com os LOOP 0–6 do back-end em `docs/loops.md`.

## Retrofit visual (R6 — 2026-09-10)

- CSS legado eliminado por completo: `static/css/local.css` e `legado.css`
  removidos; telas finais migradas (pilar, financeiro consolidado, formulários,
  auditoria) e componentes remanescentes definidos em `assets/styles/input.css`.
- Polish: skeleton global em requisições HTMX, tooltips em botões de ícone,
  animações de entrada com `prefers-reduced-motion`, view transitions do htmx.
- A11y: `axe-core` em 12 páginas (0 critical/serious); Lighthouse no design
  system com Performance 100 / A11y 95 / Best Practices 96.
- Bundles gzip: CSS 7,76 KB; JS base 37,27 KB/página; Chart.js 68,97 KB
  sob demanda.
- Incidente e regra: edições em massa com PowerShell corromperam UTF-8 de 9
  arquivos (cp1252 no round-trip) e causaram flakiness no E2E. Correção aplicada
  e regra adotada: **nunca usar `Get-Content`/`Set-Content` para editar fontes
  com acentos; usar as ferramentas de edição nativas**; varredura automática de
  mojibake (`Ã`/`Â`) passou a fazer parte da verificação final.

## Correções e evoluções (R7 — 2026-09-10)

- **Tipografia**: Panton trial substituída por **Montserrat variável (OFL)**
  self-hosted. Causa dos artefatos: os glifos acentuados da trial
  (`ccedilla`/`atilde`) são glifos-marca d'água com 12 contornos e caixa fora do
  normal, comprovado com `fontTools`; a Montserrat usa compostos legítimos
  (`c`+`uni0327`, `a`+`tildecomb`). Download no `scripts/convert_fonts.py`
  (google/fonts → `font/`), conversão TTF→woff2 e `@font-face` variável
  (`font-weight: 100 900`).
- **Robustez da navegação hx-boost**: componentes Alpine passaram a ser
  registrados globalmente em `static/js/components.js` (antes, scripts por página
  não eram reexecutados após boost, quebrando timeline, modal de devolução,
  filtros e preview CSV); Chart.js virou lazy-load em `static/js/charts.js`
  (meta `chart-url` + evento `quiin:chart-pronto`); `x-cloak` foi trocado por
  `style="display:none"` em conteúdo trocado (o Alpine remove `x-cloak` só uma
  vez, no start); `OrganogramaView` só devolve o partial quando o
  `HX-Target` é o filtro (`talentos-lista`), corrigindo o primeiro clique em
  Talentos.
- **Kanban drag-and-drop**: endpoint `POST /aprovacao/lancamento/<pk>/mover/`
  com serviço `mover_lancamento` (Rascunho/Devolvido→Enviado, Enviado→Aprovado,
  Enviado→Devolvido com justificativa via modal; Aprovado é imutável), partial
  `_kanban.html` atualizado via HTMX e toasts client-side (`HX-Trigger` +
  `window.quiinToast`). Botão “Enviar” mantém a alternativa acessível.
- **Financeiro**: rota `finance:modelo_csv` baixa `modelo_financeiro.csv`
  compatível com o importador (competência do período selecionado, uma linha
  por pilar, tipos válidos).
- **CRM**: `OportunidadeForm` usa **empresa como texto com `<datalist>`**
  resolvendo por nome exato (case-insensitive) e erro orientando o cadastro;
  oportunidades perdidas ganharam link “editar / reabrir”.
- **Fontes no deploy (Render)**: Myriad Pro saiu dos `@font-face` e dos tokens
  (`--font-sans`/`--font-display`) — a UI usa só Montserrat + JetBrains Mono,
  ambas versionadas. Causa da falha de build: `fonts.css` referenciava arquivos
  ignorados pelo git, e o `CompressedManifestStaticFilesStorage` do Whitenoise
  abortava o `collectstatic`. Defesa extra: `WHITENOISE_MANIFEST_STRICT = False`
  (asset ausente vira warning, não derruba o deploy).
- Testes: **190 Django / 62 E2E** verdes; E2E de regressão específico em
  `tests/e2e/fixes_r7.spec.ts` (timeline e modal após boost, primeiro clique em
  Talentos, drag nos dois sentidos, devolução por drag, download do CSV,
  empresa texto/datalist, reabrir perdida).

## Decisões — Dashboard anual (L0/L1, 2026-09-17)

1. **Anexo A confirmado sem correções** (L0, 0 divergências DOM × data-store × Anexo A);
   vira a matriz canônica de seed/testes em `docs/retrofit/evidencias/dashboard-anual/loop-0/`.
2. **Execução anual = snapshot de plano** (`planning.PlanoAnual`), não derivada do operacional:
   garante o Anexo A exato sem reescalar fluxos mensais, CSV, relatório e e2e existentes.
3. **`previsto` = projetado (PPI) ou captado (AT/Outras)** por construção; rótulo derivado por pilar.
4. **Gráficos do painel anual em SVG server-side** (paridade, impressão, export standalone,
   asserções DOM); Chart.js fica restrito ao dashboard mensal.
5. **Farol crítico ⇒ `red-500/red-600`** (convenção já usada): não há token laranja no projeto.
6. **Série "Outras fontes" ⇒ `quiin-violet`** (Anexo D), não o `pillar-outrasfontes` verde.
7. **"Restaurar padrão" reseta filtros** (não os dados — o mockup zerava o dataset, destrutivo).
8. **Edição persiste no banco com auditoria** (mockup usava localStorage).
9. **app-header global** substitui o topbar em todas as páginas (decisão do usuário);
   o seletor mensal migra para os fluxos mensais.
10. **Grupos da sidebar em `localStorage`** (mesmo mecanismo do recolher), não sessionStorage.
11. **Tooltips via `<title>` nativo no SVG** (acessível), não `#tip` mouse-only.
12. **Evidências em `docs/retrofit/evidencias/dashboard-anual/`** (padrão vigente do repo).
13. **`makemigrations planning` sempre** (`talentos.0002` fantasma no `db.sqlite3` local).
14. **Modal do farol acessível** (`role="dialog"`, focus trap, ESC, retorno de foco) —
    o mockup não implementa.

## Decisões — Dashboard anual (L2–L8, 2026-09-17)

15. **Swap htmx com OOB**: trocar o filtro devolve `#dashboard-panel` + controles
    (`#dashboard-controls`) via `hx-swap-oob`, mantendo header, painel e URL coerentes.
16. **Segmento ativo usa `aria-current`** (links não suportam `aria-pressed` — axe exigiu).
17. **`numero_curto`**: até 2 decimais sem zeros à direita (75,5 · 7,75 · 40), paridade com o `fmt` do mockup.
18. **`tailwind build --force` sempre**: o cache do CLI ignora mudanças só de template.
19. **`collectstatic` após novo asset estático** (manifest estrito quebra render/tests).
20. **Grupos da sidebar abertos por padrão** (mockup renderiza fechados; abertura favorece
    descoberta; grupo do item ativo sempre abre).
21. **Trocar de filtro descarta edição não salva** (o swap re-renderiza o painel).
22. **Standalone**: CSS + sprite inline, fontes degradam, editor fora, farol expandido.
23. **Render do painel em 9 queries** (teto de teste: 20; RNF-013).
24. **E2E que muta o banco (T16) restaura o valor** ao final (banco local compartilhado).
25. **`data-categoria` sem dois-pontos** nos dois tipos de gráfico (seletor único no e2e).
