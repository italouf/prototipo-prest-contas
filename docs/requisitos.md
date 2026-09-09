# Requisitos — Portal QuIIN (versão local)

## Requisitos funcionais (RF)

| ID | Requisito | Onde |
|---|---|---|
| RF-001 | Login local | `apps/accounts` |
| RF-002 | Usuários com permissões diferentes | `apps/core/permissions.py` |
| RF-003 | Grupos Master, Admin, PontoFocal, Lideranca, Auditor | seed + permissions |
| RF-004 | Master vê todos os pilares | `pilares_visiveis` |
| RF-005 | PontoFocal vê apenas pilares vinculados | `UsuarioPilar` |
| RF-006 | Liderança vê dashboards/relatórios sem editar | permissions + views |
| RF-007 | Auditor vê auditoria sem editar | `pode_ver_auditoria` |
| RF-010..012 | CRUD de pilares (nome, descrição, ordem, ativo) | admin + model `Pilar` |
| RF-020..024 | CRUD de indicadores por pilar (código, unidade, tipo, ativo) | admin + model `Indicador` |
| RF-030..033 | Metas com vigência, versão e periodicidade | model `Meta` + `meta_aplicavel` |
| RF-040..042 | Períodos mensais com competência única e status | model `Periodo` |
| RF-043..045 | Abrir/fechar (Master/Admin); reabrir com justificativa | `periods/services.py` |
| RF-050..058 | Lançamentos: valores, comentário, status, usuários, duplicidade, escopo por pilar | `entries/services.py` |
| RF-060..065 | Dashboard geral: consolidado, meta×realizado, filtro, destaque, pendências | `core/views.py` |
| RF-070..073 | Dashboard por pilar com permissões e comentários | `core/views.pilar` |
| RF-080..087 | Importação CSV atômica com validação e log | `finance/services.py` |
| RF-090..097 | Relatório mensal HTML imprimível | `reports/views.py` |
| RF-100..106 | Auditoria com usuário, data, entidade, ação, valores e justificativa | `audit/` |

## Requisitos não funcionais (RNF)

| ID | Requisito |
|---|---|
| RNF-001 | Executa localmente com SQLite e Django runserver |
| RNF-002 | Sem serviços externos (cloud, filas, e-mail, APIs) |
| RNF-003 | Interface via Django Templates + CSS local, sem build |
| RNF-004 | Permissões validadas nas views (backend), não só no template |
| RNF-005 | Restrições no banco (unique_together) + transações atômicas |
| RNF-006 | Auditoria de ações relevantes |
| RNF-007 | Interface responsiva e relatório imprimível |
| RNF-008 | Código organizado por domínio (apps) |
| RNF-009 | `seed_demo` idempotente |
| RNF-010 | Somente dados fictícios/consolidados |

## Regras de negócio (RN)

RN-001..RN-015 — ver `docs/sdd.md` seção 8 e `relatorio.html` (contexto).

## User stories (US)

| ID | História |
|---|---|
| US-001 | Como PontoFocal, quero lançar os indicadores do meu pilar e enviar para validação. |
| US-002 | Como Master, quero aprovar ou devolver lançamentos e fechar o mês. |
| US-003 | Como Liderança, quero ver o dashboard e o relatório mensal sem editar. |
| US-004 | Como Auditor, quero consultar o histórico de alterações. |
| US-005 | Como Master/Admin, quero importar o CSV financeiro consolidado com validação. |

## Critérios de aceite (AC)

| ID | Critério |
|---|---|
| AC-001..AC-016 | Critérios gerais do prompt (rodar local, seed, login, dashboards, lançar, aprovar, fechar, bloquear, auditar, CSV, relatório, docs, sem cloud). |
| AC-017..AC-024 | Validações E2E via Playwright (fluxos, permissões, CSV, relatório, mobile, diagnóstico). |
| AC-025..AC-030 | `/impeccable init` antes de frontend; UI validada; responsividade; impressão; sem CDN; decisões registradas. |
| AC-031..AC-038 | `relatorio.html` é só contexto; app independe dele; templates próprios; skill impecável tentada; Playwright opcional; app roda só com Python+Django+SQLite. |
