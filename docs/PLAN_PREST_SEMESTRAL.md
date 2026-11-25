# Plano de Implementação Atômico — Prestação de Contas SEMESTRAL (QuIIN / EMBRAPII v3.1)

Baseado estritamente em [`docs/SPEC_PREST_SEMESTRAL.md`](SPEC_PREST_SEMESTRAL.md), executando o ciclo **Loop-Engineering (Implementar -> Verificar -> Corrigir)** em 5 tarefas ordenadas.

---

## T1 — Setup dos Templates v3.1, App `apps.semestral`, Schema de Banco, Migrations e Seed Oficial
- **Objetivos:**
  1. Copiar (nunca mover/modificar) os 5 templates oficiais de `mockup/exemplos_arquivos/PREST_SEMESTRAL/` para `templates_embrapii/v3_1/` com nomes padronizados e manifest SHA-256 de referência.
  2. Criar app Django `apps.semestral` e registrá-lo em `config/settings.py`.
  3. Modelar `CicloSemestral`, `ConfiguracaoPilarSemestral`, `CompetenciaMensalPilar`, `ListaDominioEmbrapii`, `LogNotificacaoSLA` e os 21 models tipados de registros das abas QuIIN (cobrindo todas as 24 abas em escopo).
  4. Gerar migrations iniciais e aplicar `migrate`.
  5. Implementar serviço/comando idempotente `seed_semestral_v31` que lê programaticamente `Listas`, `PIs`, `Projetos` e validações de `templates_embrapii/v3_1/` para popular `ListaDominioEmbrapii`, cria pilares QuIIN (`FCRH`, `ACS`, `AFCCT`, `AT`, `FIN_QUIIN`), ciclo padrão e competências mensais.
- **Critério de Aceite T1:** `manage.py check`, `makemigrations --check` sem pendências, `seed_semestral_v31` idempotente, hashes originais em `mockup/` intactos, tabelas e listas oficiais populadas.

## T2 — Motor de Exportação `.xlsx` Lossless (SHA-512, Fórmulas, `<extLst>`)
- **Objetivos:**
  1. Implementar `apps/semestral/xlsx_schema.py` (mapeamento declarativo validado contra os templates v3.1) e `apps/semestral/xlsx_exporter.py` (pipeline OOXML lossless preservando `<sheetProtection>`, `<extLst>`, `<dataValidations>`, `<tableParts>`, `<comments>`, `<drawing>` e fórmulas).
  2. Implementar preenchimento de parâmetros no `0. Sumário` (`J21:J23`) e `1. Sumário` (`J15:J17`), além da escrita consolidada de todas as 24 abas do escopo QuIIN nos 5 arquivos e geração de pacote `.zip`.
  3. Criar utilitário de verificação `validar_integridade_xlsx(template_path, output_bytes)`.
- **Critério de Aceite T2 (Teste Automatizado Round-Trip Excel Integrity):**
  - Inserir dados fictícios em **TODAS** as 24 abas do escopo QuIIN nos 5 arquivos.
  - Gerar os 5 `.xlsx` de saída.
  - Validar via Python + XML que:
    - 100% dos blocos `<sheetProtection>` (hashes SHA-512) permanecem idênticos aos templates originais;
    - 0 fórmulas (`=B11+1`, `_xlfn.CONCAT`, `SUM`, `IF`, `Tabela1`) foram apagadas ou sobrescritas;
    - 100% dos blocos `<extLst>` (`x14:dataValidations`) continuam idênticos;
    - Todos os dados inseridos estão nas coordenadas esperadas.

## T3 — Motor de SLA Mensal, Links Diretos e Advertência `ITS1` + Coordenação
- **Objetivos:**
  1. Implementar `apps/semestral/sla.py` com `disparar_alertas_mensais`, `verificar_sla_e_emitir_its1` e `submeter_competencia`.
  2. Construir gerador de links diretos contextualizados (`/prestacao/semestral/acesso/<token>/`) e templates formais de mensagem/e-mail para **Alerta Mensal**, **Advertência `ITS1`** (ao responsável do pilar) e **Comunicado Automático em Cópia para Coordenação (Mabel / gestão QuIIN)**.
  3. Criar management command `verificar_sla_semestral` (com flag `--simular-atraso` ou data de referência) e integração completa com `AuditLog` (`registrar_auditoria`).
- **Critério de Aceite T3:** Teste automatizado simulando vencimento de prazo de um pilar inadimplente validando: transição para `ATRASADO_ITS1_EMITIDA`, emissão da advertência `ITS1`, disparo para a Coordenação (Mabel), registro em `LogNotificacaoSLA` e `AuditLog`, e subsequente transição para `REGULARIZADO` após submissão.

## T4 — Backend Views, Forms e Validações de Coleta Mensal + RBAC
- **Objetivos:**
  1. Implementar catálogo dinâmico de formulários (`apps/semestral/registry.py` + `forms.py`) com validação de listas oficiais (`ListaDominioEmbrapii`), obrigatoriedade por coluna, tipos/datas/valores monetários e geração determinística de preview dos códigos de projeto (`QIN-...`).
  2. Implementar endpoints/views em `apps/semestral/views.py` e rotas em `apps/semestral/urls.py` + wiring em `apps/core/views.py` (`/prestacao/semestral/` e `/prestacao/semestral/dados.csv`).
  3. Garantir RBAC rigoroso (`Master`/`Admin` completo, `PontoFocal` restrito aos seus pilares, `Lideranca`/`Auditor` leitura) e trilha de auditoria em criações/exclusões/submissões.
- **Critério de Aceite T4:** Testes de integração Django cobrindo RBAC, validação de selects oficiais, criação/edição/exclusão de registros mensais, submissão, acesso via link direto tokenizado e compatibilidade com `SemestralViewTestes`.

## T5 — Frontend da Aba Prestação de Contas SEMESTRAL & Verificação Final
- **Objetivos:**
  1. Criar templates no design system QuIIN (`templates/semestral/painel.html`, `templates/semestral/competencia_form.html`, parciais de semáforo, notificações SLA/ITS1, configuração e exportação).
  2. Suportar navegação HTMX (`#main` / `#app-header`), filtro de Ano/Semestre, exibição de semáforo mensal por pilar, painel de alertas/advertências `ITS1`, formulários dinâmicos por aba com dropdowns oficiais, simulação/disparo de SLA e download dos 5 arquivos `.xlsx` (individual e `.zip`).
  3. Executar suíte completa de testes (`apps/semestral`, `apps/core/tests_navegacao.py`, e verificação regressiva do projeto).
- **Critério de Aceite T5:** Todos os testes automatizados passando, zero erros no `manage.py check`, compatibilidade com navegação sidebar/HTMX confirmada.
