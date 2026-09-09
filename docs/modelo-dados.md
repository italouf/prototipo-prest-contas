# Modelo de dados — Portal QuIIN (SQLite)

## Entidades

### accounts.User (AUTH_USER_MODEL)
- Herda `AbstractUser` + `nome`.
- Papéis via grupos: Master, Admin, PontoFocal, Lideranca, Auditor.

### pillars.Pilar
- `codigo` (unique), `nome`, `descricao`, `ordem`, `ativo`.

### pillars.UsuarioPilar
- `usuario` FK → User, `pilar` FK → Pilar.
- `unique_together(usuario, pilar)`.

### indicators.Indicador
- `pilar` FK, `codigo`, `nome`, `descricao`, `unidade`, `tipo`
  (QTD/MON/PER/TXT), `acumulado` (YTD), `ativo`.
- `unique_together(pilar, codigo)`.

### indicators.Meta
- `indicador` FK, `competencia_inicio`, `competencia_fim`,
  `periodicidade` (MENSAL/ANUAL/ACUMULADA), `valor` (Decimal),
  `versao`, `ativo`, `observacao`.

### periods.Periodo
- `competencia` (Date, unique — primeiro dia do mês), `status`
  (PLANEJADO/ABERTO/FECHADO/REABERTO), `aberto_por`, `fechado_por`,
  `reaberto_por`, `justificativa_reabertura`, `snapshot_json`,
  `snapshot_gerado_em`, timestamps.
- `permite_edicao` = status em (ABERTO, REABERTO).

### entries.Lancamento
- `periodo` FK, `indicador` FK, `valor_numerico` (Decimal),
  `valor_texto`, `comentario`, `comentario_revisao`, `status`
  (RASCUNHO/ENVIADO/APROVADO/DEVOLVIDO), `usuario_criacao`,
  `usuario_aprovacao`, timestamps.
- `unique_together(periodo, indicador)` — impede duplicidade (RF-057).

### finance.FinanceiroConsolidado
- `periodo` FK, `pilar` FK, `tipo_recurso` (EMBRAPII/AT/OUTRAS_FONTES),
  `valor_captado`, `valor_executado`, `observacao`.
- `unique_together(periodo, pilar, tipo_recurso)`.

### finance.ImportacaoFinanceira
- `periodo` FK, `arquivo_nome`, `status` (SUCESSO/ERRO), `log`,
  `usuario`, `criado_em`.

### audit.AuditLog
- `usuario` FK (SET_NULL), `acao`, `entidade`, `registro_id`,
  `campo`, `valor_anterior`, `valor_novo`, `justificativa`, `data_hora`.

## Estados

### Periodo
```
PLANEJADO → ABERTO → FECHADO
FECHADO → REABERTO → FECHADO
```
Reabertura exige justificativa (RF-045). Fechamento grava snapshot_json (RN-010).

### Lancamento
```
RASCUNHO → ENVIADO → APROVADO
        ↘ DEVOLVIDO → (reenvio → ENVIADO)
```
Apenas lançamentos APROVADOS alimentam dashboards (RF-060).

### ImportacaoFinanceira
`SUCESSO` ou `ERRO`; a importação é atômica (tudo ou nada).

## Relacionamentos principais

```
User 1—* UsuarioPilar *—1 Pilar 1—* Indicador 1—* Meta
Periodo 1—* Lancamento *—1 Indicador
Periodo 1—* FinanceiroConsolidado *—1 Pilar
Periodo 1—* ImportacaoFinanceira
User 1—* AuditLog
```
