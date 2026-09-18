# L10 — Shell full-width (evidência)

Data: 2026-09-17 · Paridade de layout com o mockup.

## Entregas
- `base.html`: topbar acima de tudo (full width); linha do shell
  (`div.lg:flex` com sidebar + coluna de conteúdo); rodapé full width;
  skeleton `top-0`; `<main>` único (bloco `content` sem duplicar).
- Sidebar: sem `lg:h-screen`, `lg:overflow-visible` (scroll único da página);
  marca mantida (decisão do usuário); drawer mobile inalterado.
- `_controles.html`: faixa filtros+chips e faixa de ações, ambas `justify-end`
  (botões em linha própria à direita, como no mockup).

## Verificação
- Django: ordem header→sidebar no HTML + classes (`tests_frontend`) ✅.
- e2e L10: header `x=0`/largura=viewport, sidebar abaixo do header,
  `overflow-y: visible`, toolbar em linha própria à direita ✅.
- Evidência visual: `shell-topo.png`, `shell-rolado.png`, `shell-recolhida.png`.
