# L7 — Footer + edição + ações (evidência)

Data: 2026-09-17 · Commit: `feat(painel)` (LOOP 7)

## Entregas
- Footer institucional (`app_footer`, Anexo C): `logos-quiin.png` vendorizado
  (recorte 4277×651 → 1700×259, 398 KB) + textos + copyright + Salvador;
  imprime junto com a folha A4.
- Edição: `POST /plano-anual/aplicar/` — grade ano×pilar da base em edição,
  validação integral no backend (≥ 0, físico inteiro, ano/base/pilar válidos),
  Master/Admin tudo, PontoFocal só vinculados (403 fora), atômico, auditoria
  por campo (`EDITAR_PLANO_ANUAL`), recálculo imediato; `acao=baixar` aplica
  e devolve o HTML. Editor só com linhas editáveis; Cancelar descarta no
  cliente; trocar de filtro descarta não-salvos (documentado).
- CSV `GET /plano-anual/dados.csv`: visão corrente, `;`, BOM, UTF-8, colunas
  `Bloco;Item;Indicador;Unidade;Período;Valor`, unidade ASCII.
- Download `GET /plano-anual/dashboard.html`: standalone da visão corrente
  (CSS + sprite inline; fontes degradam; editor fora; farol expandido).
- Impressão: bloco `.print-only` com filtros; controles/editor/modal ocultos.
- Toolbar final: Editar (toggle), Baixar dashboard, CSV, Imprimir, Restaurar.

## Verificação
- Django: 12 testes novos (edição/auditoria/permissões/validação/baixar +
  CSV/filename/filtro/inválido/login) ✅; planning+core 49/49 ✅.
- e2e T12 (CSV 2026/fis), T13 (print), T14 (liderança sem botão + 403 real
  com CSRF), T15 (focal vê só PDI), T16 (edita 8→9, recalcula, audita,
  restaura 8) ✅; spec anual 25/25 ✅.
- Correções no loop: `collectstatic` p/ manifest do logo; `tailwind --force`;
  asserções Django robustas a strings do JS (`btn-editar-dados`,
  `<section id="editor-dados"`, sidebar fatiada).
- DoD L7: CSV/impressão refletem filtro ✅; edição auditada ✅; sem permissão sem edição ✅.
- Evidência visual: `footer.png`, `editor.png`.
