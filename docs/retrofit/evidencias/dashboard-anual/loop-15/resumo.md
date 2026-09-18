# L15 — Toolbar por pilar (evidência)

Data: 2026-09-17 · TDD: 13 testes Django antes.

## Entregas
- `aplicar` com `pilar=<pk>`: 404 se inexistente, 403 se invisível/não-editável,
  interseção com pilares editáveis, redirect de volta ao pilar, `acao=baixar`
  devolve o HTML do pilar.
- `exportar_csv` com `pilar=`: layout `Pilar;Ano;Previsto;Executado;Saldo;% Executado`
  (anos + Total), filename com o código do pilar.
- `exportar_html`/`download_html` com `pilar=`: `standalone_pilar.html`
  (título/cabeçalho do pilar + painel recortado, sem editor).
- `contexto_pilar()` compartilhado (view + exports); view do pilar refatorada.
- Toolbar no `_controles_pilar` (Editar escopado, Baixar/CSV com pilar,
  Imprimir, Restaurar → `/pilar/<pk>/`); editor com hidden `pilar`;
  `print-cabecalho` com nome do pilar no `pilar.html`.

## Verificação
- Django: 13/13 (escopo, 403/404, auditoria, CSV/HTML, toolbar, editor).
- e2e pilar_anual: 12/12 (P08 CSV, P09 print, P10/P10b edição + restore).
- Evidência visual: `editor-pdi.png`.
