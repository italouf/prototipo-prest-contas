# L11 — Botões e ícones na escala do mockup (evidência)

Data: 2026-09-17 · "Barras de rolagem" do pedido = tamanho dos ícones (esclarecido).

## Entregas
- `c-ui.button` com `size="toolbar"` (`rounded-lg px-4 py-2 text-xs`;
  `rounded-md` movido para os ramos de size — saída dos tamanhos atuais idêntica).
- 5 botões da toolbar em `size="toolbar"` (≈ `.btn` do mockup: 12px/16px/8px/raio 8px).
- Utilitários do header (`menu`, `dark-toggle`, sair) em 32px com ícones 16px.
- Sidebar: sem mudança (já acompanha a rolagem desde o L10) + verificação.

## Verificação
- e2e L11: métricas dos 5 botões (fonte/padding/raio/altura/linha),
  icon-buttons 32px com SVG 16px, sidebar sem scroll exclusivo ✅.
- Evidência visual: `header-escala.png` (comparar com o mockup).
