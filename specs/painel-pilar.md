# Plano de teste Playwright — Painel por pilar (L13–L16)

Suite nova: `tests/e2e/pilar_anual.spec.ts` (Chromium, serial, baseURL `http://127.0.0.1:8000`).
Pré-condição: `seed_demo` aplicado (pilares 1=PDI, 2=FORMACAO, 3=STARTUPS, 4=AT, 5=INFRA).
Login como Master (exceto onde indicado).
`data-testid` nos templates: `painel-pilar`, `pilar-cards`, `pilar-chart`, `pilar-tabela`,
`contexto-impressao`; header reaproveita `year-select`, `base-toggle`, `context-chips`.

## Casos por AC

| # | AC | Passos | Asserções |
|---|---|---|---|
| P01 | AC-051 | GET `/pilar/1/` sem params | chips "Acumulado 2024 a 2027 / Financeiro / R$ milhões"; cards Previsto 29, Executado 21, Saldo 8, 72% "Execução parcial"; gráfico com acumulado 29×21 |
| P02 | AC-052 | select `Ano 3: 2026` | cards/tabela 10×8 (80%); URL `?ano=2026&base=fin`; sem reload (swap `#painel-pilar`) |
| P03 | AC-053 | ativar base "Físico" | 18×13 (72%), unidade "metas"; chip "quantidade de metas" |
| P04 | AC-054 | GET `/pilar/1/?ano=2025&base=fis` + reload | painel = Ano 2 + Físico; filtros refletem o estado |
| P05 | AC-055 | GET `/pilar/4/` (AT) | rótulo **Captado** (não Projetado): 7,75×2, 26% crítica; em Físico 8×2 (25%) |
| P06 | AC-055 | Tabela do PDI: linhas Ano 1..4 + Total | 2026 = 10×8 (80%); Total = 29×21 (72%); Infra 4×4 (100%, atingida) |
| P07 | AC-056 | Sidebar como Master | Pilares com PDI, Formação FCRH, ACS, Associação Tecnológica, Infraestrutura; Gestão com Funil AT, Talentos, Auditoria, Admin |
| P08 | AC-057 | `/pilar/4/?ano=2026&base=fis` + download CSV | `Pilar;Ano;Previsto;Executado;Saldo;% Executado`, só AT, BOM, `;` |
| P09 | AC-058 | Mesmo estado + `emulateMedia print` | cabeçalho "Associação Tecnológica · Ano 3: 2026 · Físico"; controles ocultos |
| P10 | AC-059 | login PontoFocal do PDI: editor só com PDI; POST em Infra ⇒ 403; Liderança sem botão Editar | recálculo + auditoria no escopo |
| P11 | AC-060 | axe em `/pilar/1/` e `/pilar/4/?ano=2026&base=fis` | 0 critical/serious |
| P12 | AC-051 | URL inválida (`?ano=2030`) | 302 para `/pilar/<pk>/?ano=todos&base=fin` (preserva `periodo`) |
| P13 | AC-056 | Pilar 1 → AT pela sidebar, trocar base; AT → Geral, trocar base; Geral → Mensal | toggle mira `/pilar/4/` e URL vira `/pilar/4/?ano=todos&base=fis`; no Geral o toggle volta a `/?ano=todos&base=fis`; na Mensal não há `base-toggle` (header OOB via `hx-select-oob`) |
| P14 | AC-056 | Header do pilar (Master): filtros acima dos chips; toolbar | `context-chips` abaixo de Ano/Base; só "Editar dados" navy, demais botões brancos (L18, `shell.spec.ts`) |

## Regressão a revalidar
`portal.spec.ts` (heading do pilar), `shell.spec.ts` (teste L9: AT sai de Gestão),
`apps/core/tests_navegacao.py`, `a11y_r6.spec.ts` (`/pilar/1/`), seção mensal intacta.
