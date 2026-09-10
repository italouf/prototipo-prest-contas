# Portal QuIIN — SDD (Software Design Document)

Versão local (protótipo demonstrativo) · SQLite + Django 5.2 LTS · Python 3.11+

## 1. Nome do projeto

Portal QuIIN — Gestão e Prestação de Contas Mensal do Programa QuIIN.

## 2. Objetivo

Protótipo local que apoia a coordenação do Programa QuIIN no ciclo mensal de
prestação de contas com a Embrapii: coleta de indicadores por pilar, metas,
lançamentos aprovados, dashboards, fechamento mensal, auditoria, financeiro
consolidado (importação CSV) e relatório mensal HTML imprimível.

## 3. Escopo da versão local

- Login local com perfis: Master, Admin, PontoFocal, Lideranca, Auditor.
- Pilares, indicadores (QTD/MON/PER/TXT), metas (MENSAL/ANUAL/ACUMULADA) e períodos mensais.
- Lançamentos com fluxo Rascunho → Enviado → Aprovado/Devolvido.
- Dashboard consolidado e por pilar, com meta × realizado × percentual e pendências.
- Fechamento/reabertura de período com snapshot lógico.
- Importação CSV atômica de financeiro consolidado.
- Relatório mensal HTML imprimível (Imprimir → Salvar como PDF).
- Auditoria das ações relevantes.
- Comando `seed_demo` idempotente.

## 4. Fora de escopo

Cloud, deploy, Docker, Kubernetes, Nginx, Gunicorn, Redis, Celery, filas,
PostgreSQL, MySQL, SSO, OAuth, e-mail, notificações, APIs externas, PDF gerado
por biblioteca, ERP financeiro, módulo completo de AT (contratos/pipeline),
kanban, talentos e playbooks. Dados reais/sensíveis.

## 5. Personas e perfis

| Perfil | Permissões |
|---|---|
| Master | Tudo: gerencia períodos, aprova, importa financeiro, vê auditoria, vê todos os pilares |
| Admin | Apoio operacional: aprova, devolve, importa, cadastra, vê auditoria |
| PontoFocal | Lança apenas indicadores dos pilares vinculados; salva rascunho e envia |
| Lideranca | Visualiza dashboards e relatórios; não edita |
| Auditor | Visualiza auditoria e histórico; não edita |

## 6. Fluxos principais

1. Master/Admin cria e abre o período de competência.
2. Pontos focais lançam indicadores dos seus pilares (rascunho ou envio).
3. Master/Admin aprova ou devolve os lançamentos enviados.
4. Dashboards consolidam apenas lançamentos aprovados.
5. Importação CSV de financeiro consolidado (atômica).
6. Fechamento gera snapshot lógico e bloqueia edições.
7. Relatório mensal HTML consolidado para impressão/PDF.

## 7. Requisitos

Ver `docs/requisitos.md` (RF-001 a RF-106, RNF-001 a RNF-010, RN-001 a RN-015, US).

## 8. Regras de negócio

- RN-001: a prestação considera o mês de competência anterior.
- RN-002: comparar meta, realizado e percentual.
- RN-003: execução financeira = valor efetivamente gasto/comprovado.
- RN-004: captação ≠ execução.
- RN-005/006: visão segregada e consolidada.
- RN-007: renovações não contam para a meta de CNPJs novos.
- RN-008/009: apenas dados financeiros consolidados.
- RN-010: períodos fechados preservam snapshot lógico.
- RN-011: toda alteração relevante é auditável.
- RN-012: acesso compatível com papel e pilar.
- RN-013/014: metas e indicadores configuráveis.
- RN-015: plurianuais diferenciam captado e executado.

## 9. Premissas

- Competência armazenada como primeiro dia do mês (`YYYY-MM-01`).
- Período demo: `2026-06` (aberto), `2026-05` (fechado) e `2026-07` (planejado).
- Dashboards usam lançamentos aprovados.
- Meta ANUAL/ACUMULADA usa somatório YTD (jan/ano → período).
- Erro de digitação `EMBRAPPI` é normalizado para `EMBRAPII` na importação.
- `relatorio.html` é somente contexto de engenharia; não é template nem referência visual obrigatória.
- Front-end: Tailwind CSS v4 (build via django-tailwind-cli, sem Node em
  runtime), componentes django-cotton, fragmentos django-template-partials,
  HTMX + Alpine.js vendorizados e Chart.js sob demanda. Retrofit visual em
  `docs/retrofit/loops.md` (R0–R6).

## 10. Rastreabilidade

Implementação organizada em loops (ver `docs/loops.md`); cada loop referencia
requisitos RF/RNF/RN e critérios de aceite AC (ver `docs/requisitos.md`).
