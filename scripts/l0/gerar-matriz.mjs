import * as fs from 'node:fs';
import * as path from 'node:path';

/**
 * L0 — Valida a extração do mockup e publica matriz-estados.md.
 * 1) Confronta data-store.json com o Anexo A (literais esperados).
 * 2) Recomputa todos os valores exibidos (cards, rodapés, tabela) e
 *    confronta com o DOM extraído em matriz-estados.json.
 * Uso: node scripts/l0/gerar-matriz.mjs
 */
const EVID = 'docs/retrofit/evidencias/dashboard-anual/loop-0';
const PILARES = ['PDI', 'Formação FCRH', 'ACS', 'Infraestrutura'];
const ANOS = ['todos', '0', '1', '2', '3'];
const ROT_ANO = { todos: 'Acumulado 2024 a 2027', 0: 'Ano 1: 2024', 1: 'Ano 2: 2025', 2: 'Ano 3: 2026', 3: 'Ano 4: 2027' };

// Literais do Anexo A do prompt — fonte de verdade para validar o data-store.
const ANEXO_A = {
  financeiro: {
    ppi: {
      PDI: { proj: [7, 10, 10, 2], exec: [5, 8, 8, 0] },
      'Formação FCRH': { proj: [4, 5, 4, 1], exec: [2, 3, 2, 0] },
      ACS: { proj: [2, 2, 2, 1], exec: [1, 1, 1, 0] },
      Infraestrutura: { proj: [2, 3, 4, 1], exec: [2, 3, 4, 0] },
    },
    at: { proj: [1, 2, 3, 1.75], exec: [0, 1, 1, 0] },
    outras: { proj: [1, 2, 3, 1.75], exec: [0, 0, 0, 0] },
  },
  fisico: {
    ppi: {
      PDI: { proj: [4, 6, 6, 2], exec: [3, 5, 5, 0] },
      'Formação FCRH': { proj: [3, 5, 5, 2], exec: [2, 3, 2, 0] },
      ACS: { proj: [2, 3, 3, 1], exec: [1, 1, 1, 0] },
      Infraestrutura: { proj: [2, 3, 4, 1], exec: [2, 3, 4, 0] },
    },
    at: { proj: [1, 2, 3, 2], exec: [0, 1, 1, 0] },
    outras: { proj: [1, 2, 3, 2], exec: [0, 0, 0, 0] },
  },
};

const sum = (a) => a.reduce((x, y) => x + Number(y || 0), 0);
const vp = (vals, ano) => (ano === 'todos' ? sum(vals) : Number(vals[Number(ano)]));
const fmt = (v) =>
  (Math.round(Number(v) * 100) / 100).toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
const pct = (e, p) => (Number(p) <= 0 ? 0 : (Number(e) / Number(p)) * 100);
const pctTxt = (e, p) => `${pct(e, p).toFixed(0)}%`;
const farol = (p) => (p >= 90 ? 'Meta atingida' : p >= 50 ? 'Execução parcial' : 'Execução crítica');
const norm = (s) => (s ?? '').replace(/\s+/g, ' ').trim();

const falhas = [];
const check = (onde, obtido, esperado) => {
  if (norm(obtido) !== norm(esperado)) falhas.push(`${onde}\n  obtido:   ${norm(obtido)}\n  esperado: ${norm(esperado)}`);
};

const store = JSON.parse(fs.readFileSync(path.join(EVID, 'data-store.json'), 'utf8'));
for (const base of ['financeiro', 'fisico']) {
  for (const p of PILARES) {
    check(`data-store ${base}.ppi.${p}.proj`, JSON.stringify(store[base].ppi[p].proj), JSON.stringify(ANEXO_A[base].ppi[p].proj));
    check(`data-store ${base}.ppi.${p}.exec`, JSON.stringify(store[base].ppi[p].exec), JSON.stringify(ANEXO_A[base].ppi[p].exec));
  }
  for (const k of ['at', 'outras']) {
    check(`data-store ${base}.${k}`, JSON.stringify([store[base][k].proj, store[base][k].exec]),
      JSON.stringify([ANEXO_A[base][k].proj, ANEXO_A[base][k].exec]));
  }
}
check('data-store.anos', JSON.stringify(store.anos), JSON.stringify(['2024', '2025', '2026', '2027']));

const matriz = JSON.parse(fs.readFileSync(path.join(EVID, 'matriz-estados.json'), 'utf8'));

const linhasMd = [];
for (const modo of ['financeiro', 'fisico']) {
  const base = store[modo];
  const fin = modo === 'financeiro';
  const baseRot = fin ? 'Financeiro' : 'Físico';
  const unChip = fin ? 'R$ milhões' : 'quantidade de metas';
  const baseKey = fin ? 'fin' : 'fis';
  for (const ano of ANOS) {
    const chave = `ano-${ano === 'todos' ? 'todos' : ['2024', '2025', '2026', '2027'][Number(ano)]}_base-${baseKey}`;
    const dom = matriz[chave];
    const per = PILARES.map((p) => ({ nome: p, prev: vp(base.ppi[p].proj, ano), exec: vp(base.ppi[p].exec, ano) }));
    const ppiP = sum(per.map((r) => r.prev)), ppiE = sum(per.map((r) => r.exec));
    const atP = vp(base.at.proj, ano), atE = vp(base.at.exec, ano);
    const ouP = vp(base.outras.proj, ano), ouE = vp(base.outras.exec, ano);
    const totP = ppiP + atP + ouP, totE = ppiE + atE + ouE;

    // chips
    check(`${chave} chip periodo`, dom.chips[0], `Período: ${ROT_ANO[ano]}`);
    check(`${chave} chip base`, dom.chips[1], `Base: ${baseRot}`);
    check(`${chave} chip unidade`, dom.chips[2], `Unidade: ${unChip}`);

    // cards
    const valFmt = (v) => (fin ? `R$ ${fmt(v)} mi` : `${fmt(v)} metas`);
    const espCards = [
      { rot: 'Recursos PPI executados', val: valFmt(ppiE), sub: `de ${valFmt(ppiP)} projetados`, badge: pctTxt(ppiE, ppiP) },
      { rot: 'Captação AT executada', val: valFmt(atE), sub: `de ${valFmt(atP)} captados`, badge: pctTxt(atE, atP) },
      { rot: 'Outras fontes executadas', val: valFmt(ouE), sub: `de ${valFmt(ouP)} captados`, badge: pctTxt(ouE, ouP) },
      { rot: 'Execução consolidada', val: valFmt(totE), sub: `de ${valFmt(totP)} previstos`, badge: pctTxt(totE, totP) },
    ];
    espCards.forEach((e, i) => {
      check(`${chave} card${i + 1} val`, dom.cards[i].val, e.val);
      check(`${chave} card${i + 1} sub`, dom.cards[i].sub, e.sub);
      check(`${chave} card${i + 1} badge`, dom.cards[i].badge, e.badge);
    });

    // tabela
    const espLinhas = [
      ...per.map((r) => ({ pilar: r.nome, prev: fmt(r.prev), exec: fmt(r.exec), saldo: fmt(r.prev - r.exec), pct: pctTxt(r.exec, r.prev), farol: farol(pct(r.exec, r.prev)) })),
      { pilar: 'Total PPI', prev: fmt(ppiP), exec: fmt(ppiE), saldo: fmt(ppiP - ppiE), pct: pctTxt(ppiE, ppiP), farol: farol(pct(ppiE, ppiP)) },
      { pilar: 'Associação Tecnológica (AT)', prev: fmt(atP), exec: fmt(atE), saldo: fmt(atP - atE), pct: pctTxt(atE, atP), farol: farol(pct(atE, atP)) },
      { pilar: 'Outras fontes', prev: fmt(ouP), exec: fmt(ouE), saldo: fmt(ouP - ouE), pct: pctTxt(ouE, ouP), farol: farol(pct(ouE, ouP)) },
    ];
    const dados = dom.tabela.filter((r) => r.tipo === 'dado');
    check(`${chave} tabela qtd linhas`, String(dados.length), '7');
    espLinhas.forEach((e, i) => {
      const d = dados[i] || {};
      check(`${chave} tab[${e.pilar}] previsto`, d.previsto, e.prev);
      check(`${chave} tab[${e.pilar}] executado`, d.executado, e.exec);
      check(`${chave} tab[${e.pilar}] saldo`, d.saldo, e.saldo);
      check(`${chave} tab[${e.pilar}] pct`, d.pct, e.pct);
      check(`${chave} tab[${e.pilar}] farol`, d.farol, e.farol);
    });

    // rodapés
    check(`${chave} rodape ppi`, dom.rodapePpi.badge, pctTxt(ppiE, ppiP));
    check(`${chave} rodape at`, dom.rodapeAt.badge, pctTxt(atE, atP));
    check(`${chave} rodape outras`, dom.rodapeOutras.badge, pctTxt(ouE, ouP));

    linhasMd.push(`| ${fin ? 'FIN' : 'FIS'} · ${ROT_ANO[ano]} | ${valFmt(ppiE)} / ${valFmt(ppiP)} (${pctTxt(ppiE, ppiP)}) | ${valFmt(atE)} / ${valFmt(atP)} (${pctTxt(atE, atP)}) | ${valFmt(ouE)} / ${valFmt(ouP)} (${pctTxt(ouE, ouP)}) | ${valFmt(totE)} / ${valFmt(totP)} (${pctTxt(totE, totP)}) |`);
  }
}

const veredito = falhas.length === 0
  ? '**ANEXO A CONFIRMADO** — data-store e DOM extraído batem 100% com os literais do prompt. Nenhuma correção necessária; o Anexo A vira a matriz canônica de seed/testes (L2).'
  : `**DIVERGÊNCIAS (${falhas.length})**:\n\n${falhas.map((f) => `- ${f}`).join('\n')}`;

const md = `# L0 — Matriz de estados do mockup (extraída via Playwright)

Data: 2026-09-17 · Fonte: \`mockup/gestao_quiin_dashboard_17092026.html\` · Harness: \`scripts/l0/\`
Estados percorridos: 5 opções de ano × 2 bases = **10 estados**.

## 1. Veredito

${veredito}

## 2. Cards por estado (valores exibidos no DOM)

| Estado | PPI exec / proj (%) | AT exec / capt (%) | Outras exec / capt (%) | Consolidado exec / prev (%) |
|---|---|---|---|---|
${linhasMd.join('\n')}

## 3. Tabela gerencial — acumulado (Todos os anos)

Financeiro: PDI 29/21/8/72% parcial; FCRH 14/7/7/50% parcial; ACS 7/3/4/43% crítica;
Infra 10/9/1/90% atingida; Total PPI 60/40/20/67% parcial; AT 7,75/2/5,75/26% crítica;
Outras 7,75/0/7,75/0% crítica.
Físico: PDI 18/13/5/72% parcial; FCRH 15/7/8/47% crítica; ACS 9/3/6/33% crítica;
Infra 10/9/1/90% atingida; Total PPI 52/32/20/62% parcial; AT 8/2/6/25% crítica;
Outras 8/0/8/0% crítica.
(Detalhe por estado em \`matriz-estados.json\` + \`estado-*.json\`.)

## 4. Comportamentos observados (testes verdes)

- **Sticky**: \`#topbar\` permanece com \`top=0\` após scroll de 900px; \`--topbar-h\`
  é calculado em JS (\`ajustarTopbar\`) para o offset da sidebar.
- **Sidebar**: grupos Pilares/Prestação de contas alternam \`.nav-sub.open\` +
  \`aria-expanded\`; sem persistência (estado ativo hardcoded em "Geral").
- **Modal**: abre no botão (i), fecha por X, clique no backdrop e ESC.
  Sem focus trap, sem \`role="dialog"\`, sem retorno de foco (a implementar no L6).
- **Edição**: abre grade com 4 blocos (PPI projetado, PPI executado, AT, Outras fontes)
  × anos; inputs \`number step=0.25 min=0\`; Aplicar regrava DATA + localStorage e
  re-renderiza; Restaurar padrão volta aos DEFAULTS.
- **Tooltips**: \`data-tip\` por barra, tooltip global \`#tip\` no hover (mouse-only).

## 5. logos.png — inspeção

- Original: 4420×960 RGBA, fundo cinza \`#E9E9E9\` (igual ao footer do mockup).
- Conteúdo útil: bbox x 54–4330 × y 114–764 → **4277×651, aspecto 6,57:1**,
  idêntico ao aspecto da imagem embutida no mockup (1200×183 = 6,557:1).
- Decisão L7: vendorizar o recorte 4277×651 reduzido (largura ~1700px) em
  \`static/img/\`; preview em \`logos-recorte-preview.png\`.

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

\`data-store.json\`, \`matriz-estados.json\`, \`estado-*.json/png\` (10),
\`comportamento-*.png\` (4), \`logos-recorte-preview.png\`.
`;

fs.writeFileSync(path.join(EVID, 'matriz-estados.md'), md);
console.log(falhas.length === 0 ? 'OK: 0 divergências' : `FALHAS: ${falhas.length}`);
falhas.slice(0, 20).forEach((f) => console.log(`- ${f}`));
process.exit(falhas.length === 0 ? 0 : 1);
