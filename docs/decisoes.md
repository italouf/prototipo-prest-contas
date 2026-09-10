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
