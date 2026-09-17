# L0 — Matriz de estados do mockup (extraída via Playwright)

Data: 2026-09-17 · Fonte: `mockup/gestao_quiin_dashboard_17092026.html` · Harness: `scripts/l0/`
Estados percorridos: 5 opções de ano × 2 bases = **10 estados**.

## 1. Veredito

**ANEXO A CONFIRMADO** — data-store e DOM extraído batem 100% com os literais do prompt. Nenhuma correção necessária; o Anexo A vira a matriz canônica de seed/testes (L2).

## 2. Cards por estado (valores exibidos no DOM)

| Estado | PPI exec / proj (%) | AT exec / capt (%) | Outras exec / capt (%) | Consolidado exec / prev (%) |
|---|---|---|---|---|
| FIN · Acumulado 2024 a 2027 | R$ 40 mi / R$ 60 mi (67%) | R$ 2 mi / R$ 7,75 mi (26%) | R$ 0 mi / R$ 7,75 mi (0%) | R$ 42 mi / R$ 75,5 mi (56%) |
| FIN · Ano 1: 2024 | R$ 10 mi / R$ 15 mi (67%) | R$ 0 mi / R$ 1 mi (0%) | R$ 0 mi / R$ 1 mi (0%) | R$ 10 mi / R$ 17 mi (59%) |
| FIN · Ano 2: 2025 | R$ 15 mi / R$ 20 mi (75%) | R$ 1 mi / R$ 2 mi (50%) | R$ 0 mi / R$ 2 mi (0%) | R$ 16 mi / R$ 24 mi (67%) |
| FIN · Ano 3: 2026 | R$ 15 mi / R$ 20 mi (75%) | R$ 1 mi / R$ 3 mi (33%) | R$ 0 mi / R$ 3 mi (0%) | R$ 16 mi / R$ 26 mi (62%) |
| FIN · Ano 4: 2027 | R$ 0 mi / R$ 5 mi (0%) | R$ 0 mi / R$ 1,75 mi (0%) | R$ 0 mi / R$ 1,75 mi (0%) | R$ 0 mi / R$ 8,5 mi (0%) |
| FIS · Acumulado 2024 a 2027 | 32 metas / 52 metas (62%) | 2 metas / 8 metas (25%) | 0 metas / 8 metas (0%) | 34 metas / 68 metas (50%) |
| FIS · Ano 1: 2024 | 8 metas / 11 metas (73%) | 0 metas / 1 metas (0%) | 0 metas / 1 metas (0%) | 8 metas / 13 metas (62%) |
| FIS · Ano 2: 2025 | 12 metas / 17 metas (71%) | 1 metas / 2 metas (50%) | 0 metas / 2 metas (0%) | 13 metas / 21 metas (62%) |
| FIS · Ano 3: 2026 | 12 metas / 18 metas (67%) | 1 metas / 3 metas (33%) | 0 metas / 3 metas (0%) | 13 metas / 24 metas (54%) |
| FIS · Ano 4: 2027 | 0 metas / 6 metas (0%) | 0 metas / 2 metas (0%) | 0 metas / 2 metas (0%) | 0 metas / 10 metas (0%) |

## 3. Tabela gerencial — acumulado (Todos os anos)

Financeiro: PDI 29/21/8/72% parcial; FCRH 14/7/7/50% parcial; ACS 7/3/4/43% crítica;
Infra 10/9/1/90% atingida; Total PPI 60/40/20/67% parcial; AT 7,75/2/5,75/26% crítica;
Outras 7,75/0/7,75/0% crítica.
Físico: PDI 18/13/5/72% parcial; FCRH 15/7/8/47% crítica; ACS 9/3/6/33% crítica;
Infra 10/9/1/90% atingida; Total PPI 52/32/20/62% parcial; AT 8/2/6/25% crítica;
Outras 8/0/8/0% crítica.
(Detalhe por estado em `matriz-estados.json` + `estado-*.json`.)

## 4. Comportamentos observados (testes verdes)

- **Sticky**: `#topbar` permanece com `top=0` após scroll de 900px; `--topbar-h`
  é calculado em JS (`ajustarTopbar`) para o offset da sidebar.
- **Sidebar**: grupos Pilares/Prestação de contas alternam `.nav-sub.open` +
  `aria-expanded`; sem persistência (estado ativo hardcoded em "Geral").
- **Modal**: abre no botão (i), fecha por X, clique no backdrop e ESC.
  Sem focus trap, sem `role="dialog"`, sem retorno de foco (a implementar no L6).
- **Edição**: abre grade com 4 blocos (PPI projetado, PPI executado, AT, Outras fontes)
  × anos; inputs `number step=0.25 min=0`; Aplicar regrava DATA + localStorage e
  re-renderiza; Restaurar padrão volta aos DEFAULTS.
- **Tooltips**: `data-tip` por barra, tooltip global `#tip` no hover (mouse-only).

## 5. logos.png — inspeção

- Original: 4420×960 RGBA, fundo cinza `#E9E9E9` (igual ao footer do mockup).
- Conteúdo útil: bbox x 54–4330 × y 114–764 → **4277×651, aspecto 6,57:1**,
  idêntico ao aspecto da imagem embutida no mockup (1200×183 = 6,557:1).
- Decisão L7: vendorizar o recorte 4277×651 reduzido (largura ~1700px) em
  `static/img/`; preview em `logos-recorte-preview.png`.

## 6. Textos canônicos capturados

- Chips: "Período: Acumulado 2024 a 2027 | Ano N: YYYY" · "Base: Financeiro|Físico" ·
  "Unidade: R$ milhões | quantidade de metas".
- Legenda global: "Projetado ou captado" + "Executado".
- Tabela: cabeçalhos "Projetado (R$ mi) / Executado (R$ mi)" e "Projetado (metas) /
  Executado (metas)"; grupos "4.1 PPI: projetado x executado",
  "4.2 Captação de recursos: captado x executado", "4.3 Outras fontes: captado x executado".
- Rodapés de gráfico: "Execução no período selecionado" + badge.
- Modal: título "Farol de execução: metodologia e leitura" (corpo integral no Anexo B do prompt).

## 7. Arquivos deste loop

`data-store.json`, `matriz-estados.json`, `estado-*.json/png` (10),
`comportamento-*.png` (4), `logos-recorte-preview.png`.
