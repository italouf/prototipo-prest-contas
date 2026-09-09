# Report LOOP 3 — Parser Excel mestre (`apps/finance`)

## O que foi feito
- Implementado o parser do Excel financeiro mestre seguindo TDD (teste escrito primeiro, falha `ModuleNotFoundError` confirmada, depois implementação mínima até o verde).
- `apps/finance/excel_mestre.py` (novo): lógica pura e testável.
  - `INCLUIR_LEI_TICS_NO_AT = False` (constante explícita; REGRA DURA).
  - `normalizar()`: minúsculas, sem acento (NFKD), espaços colapsados.
  - `mapear_aba()`: mapa explícito aba → (pilar, tipo_recurso) por substring normalizada; 6.1 checada antes da regra genérica do AT; `acs` exige `conta` e exclui `venture`/`equipe`; `infraestrutura` exclui `ampliacao`; AT genérico usa fronteira de dígito (`(^|[^0-9])6\.`) para não casar `16. Eventos`, e exclui `tic(s)`/`lei`.
  - `descobrir_colunas()`: varre as primeiras 30 linhas; data = header com `data` + (`pagamento`|`pgto`|`pagto`); valor = header com `valor` ou `vlr`; mesma linha de cabeçalho para ambas.
  - `parse_data()`: datetime/date, serial numérico (`from_excel`), `dd/mm/aaaa`, `aaaa-mm-dd`; erro → linha ignorada com contador.
  - `para_decimal()`: int/float/Decimal/texto BR (`1.234,56`); erro/`#REF!`/`#VALUE!` → linha ignorada com contador; vazias ignoradas.
  - `consolidar_excel(caminho, periodo)`: `load_workbook(caminho, read_only=True, data_only=True)`, nunca escreve; soma `valor_executado` por (pilar, tipo_recurso), `valor_captado = 0`, `observacao = "Origem: <aba> — consolidado automático"`; retorna `{linhas, avisos, estatisticas}`; não toca o banco.
  - `aplicar_consolidado()`: bloqueia período fechado via `permite_edicao` (`ValidationError` PT-BR idêntico ao `importar_csv`); `update_or_create(periodo, pilar, tipo_recurso)`; `ImportacaoFinanceira(status, log)`; auditoria via `registrar_auditoria` (ação `IMPORTAR_FINANCEIRO`, campo `excel`); pilar ausente → `ValidationError` PT-BR.
- `apps/finance/management/commands/processar_excel_mestre.py` (novo, CLI fina): `--arquivo --periodo "YYYY-MM" [--aplicar]`; dry-run imprime JSON (chaves `competencia, pilar, tipo_recurso, valor_captado, valor_executado, observacao`) no stdout e não toca o banco; avisos no stderr; `--aplicar` exige `Periodo(competencia=YYYY-MM-01)` (erro PT-BR) e período aberto.
- `apps/finance/models.py` + migração `0002_alter_financeiroconsolidado_tipo_recurso`: `TIPOS += ("AT_LEI_TICS", "AT – Lei de TICs")` (10 chars, dentro do `max_length=15`).
- `apps/finance/tests_excel_mestre.py` (novo, 8 testes, descoberto via `manage.py test apps.finance`).
- `requirements.txt`: apenas `openpyxl==3.1.5` adicionado (sem pandas/numpy).

## Arquivos (commit seletivo; `.gitignore` modificado pré-existente NÃO commitado)
- `apps/finance/excel_mestre.py`, `apps/finance/tests_excel_mestre.py`
- `apps/finance/management/__init__.py`, `apps/finance/management/commands/__init__.py`, `apps/finance/management/commands/processar_excel_mestre.py`
- `apps/finance/models.py`, `apps/finance/migrations/0002_alter_financeiroconsolidado_tipo_recurso.py`
- `requirements.txt`

## Comandos + saídas
- `pip install openpyxl` → `Successfully installed et-xmlfile-2.0.0 openpyxl-3.1.5` (venv `.\.venv\Scripts\python.exe`).
- RED (TDD): `manage.py test apps.finance.tests_excel_mestre` → `ModuleNotFoundError: No module named 'apps.finance.excel_mestre'` (1 erro, esperado).
- GREEN: `manage.py test apps.finance.tests_excel_mestre -v 2` → `Ran 8 tests ... OK` (agregação/filtro, outro mês, segregação 6.1, aviso de aba fora do mapa, dry-run sem tocar banco, aplicar aberto, bloqueio fechado, período ausente).
- Regressão: `manage.py test apps.indicators apps.finance apps.seed` → `Ran 20 tests in ~109s ... OK`; `manage.py check` → `System check identified no issues (0 silenced)`.
- Descoberta: `manage.py test apps.finance` inclui os 8 testes novos (padrão `test*.py` casa `tests_excel_mestre.py`) — confirmado via run direcionado + suíte `apps.finance` dentro da regressão.

## Excel real (`Acompanhamento Financeiro (v2).xlsx`, só inspeção local, NÃO commitado)
- `load_workbook(caminho, read_only=True, data_only=True)`: **abriu OK** (único warning inofensivo do openpyxl: `Data Validation extension is not supported`; links SharePoint/`lockStructure` ignorados sem erro).
- **7 de 23 abas reconhecidas**: `3. AFCCT→(PDI,EMBRAPII)`, `4. FCRH→(FORMACAO,EMBRAPII)`, `5. ACS→(STARTUPS,EMBRAPII)`, `6. AT→(AT,AT)`, `6.1→(AT,AT_LEI_TICS)`, `7. Outras Fontes→(OUTRASFONTES,OUTRAS_FONTES)`, `8. Infraestrutura→(INFRA,EMBRAPII)`; 16 ignoradas com aviso (`9. Ampliação…`, `10. Equipe`, `16. Eventos` etc. corretamente excluídas).
- Consolidação `2026-04` no arquivo real: 0 linhas somadas (arquivo é um **template vazio** — 23.656 células data/valor vazias ignoradas, 0 erros de parse); cabeçalhos achados nas 7 abas.

## Self-review
- Valores verbatim conferidos: `load_workbook(..., read_only=True, data_only=True)`, `INCLUIR_LEI_TICS_NO_AT = False`, `("AT_LEI_TICS", "AT – Lei de TICs")`, observacao `"Origem: … — consolidado automático"`, chaves do dict, mensagens de bloqueio/fechado.
- Segregação 6.1: map-order + teste dedicado (`AT==30`, `AT_LEI_TICS==60`); `apps/core/views.py:47` filtra `tipo_recurso="AT"` → cards existentes ficam corretos automaticamente (verificado por grep; nenhum outro ponto soma AT).
- CLI nunca escreve no workbook; dry-run puro (teste assert `count()==0` em ambas as tabelas).
- Migração 0002 gerada via `makemigrations`, aplicada na suíte; `max_length` comporta o novo tipo.
- Nenhum subagente/reviewer disparado, conforme instrução.

## Concerns
1. **Cabeçalho `Data` genérico nas abas 6/6.1/7**: a regra literal do brief (data + pagamento/pgto/pagto) não casa o header real dessas abas (só `"Data"`). Implementei contingência documentada (fallback para primeiro header contendo `data`, com aviso `"cabeçalho de data genérico"` no stderr). Sem isso, 3 das 7 abas mapeadas seriam ignoradas no arquivo real. Decisão intencional, flagged aqui.
2. **Arquivo real é template vazio**: agregação real retorna `[]` hoje; parser validado via workbook mock (todos os formatos de data: datetime, serial, `dd/mm/aaaa`, `aaaa-mm-dd`).
3. **`valor_captado = 0` sempre** (conforme brief), mesmo nas abas 6/6.1/7 que distinguem entradas (`Entidade que realizou o aporte`) de saídas — se um dia for preciso separar captação vs execução nessas abas, será preciso estender o parser (coluna de tipo/ação), fora do escopo atual.
