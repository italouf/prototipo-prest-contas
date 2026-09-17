import { expect, test } from '@playwright/test';
import * as fs from 'node:fs';
import * as path from 'node:path';

/**
 * L0 — Extração automatizada da matriz de estados do mockup.
 * Percorre 5 anos × 2 bases e extrai chips, cards, gráficos, tabela e rodapés.
 * Depois testa comportamentos: sticky, colapsáveis, modal, edição, tooltips.
 */
const EVID = 'docs/retrofit/evidencias/dashboard-anual/loop-0';
const PAGINA = '/gestao_quiin_dashboard_17092026.html';
const ANOS = [
  { valor: 'todos', rotulo: 'todos' },
  { valor: '0', rotulo: '2024' },
  { valor: '1', rotulo: '2025' },
  { valor: '2', rotulo: '2026' },
  { valor: '3', rotulo: '2027' },
];
const BASES = [
  { modo: 'financeiro', rotulo: 'fin' },
  { modo: 'fisico', rotulo: 'fis' },
];

const EXTRAIR_ESTADO = `() => {
  const texto = (el) => (el ? el.textContent.trim().replace(/\\s+/g, ' ') : null);
  const chips = [...document.querySelectorAll('#context-chips .chip')].map(texto);
  const cards = [...document.querySelectorAll('#kpi-grid .kpi')].map((c) => {
    const fill = c.querySelector('.bar-fill');
    const badge = c.querySelector('.badge');
    return {
      rot: texto(c.querySelector('h5')),
      val: texto(c.querySelector('.val')),
      sub: texto(c.querySelector('.sub')),
      badge: texto(badge),
      badgeClasse: badge ? badge.className : null,
      barraLargura: fill ? fill.style.width : null,
      barraCor: fill ? fill.style.background : null,
    };
  });
  const grafico = (id) => {
    const el = document.getElementById(id);
    if (!el) return null;
    const barras = [...el.querySelectorAll('svg rect[data-tip]')].map((r) => ({
      tip: r.getAttribute('data-tip'),
      opacidade: r.getAttribute('opacity'),
      cor: r.getAttribute('fill'),
    }));
    const rotulos = [...el.querySelectorAll('svg text')].map((t) => ({
      texto: t.textContent.trim(),
      tamanho: t.getAttribute('font-size'),
      peso: t.getAttribute('font-weight'),
      cor: t.getAttribute('fill'),
      opacidade: t.getAttribute('opacity'),
    }));
    return { barras, rotulos };
  };
  const rodape = (id) => {
    const el = document.getElementById(id);
    const badge = el ? el.querySelector('.badge') : null;
    return { texto: texto(el), badge: texto(badge), badgeClasse: badge ? badge.className : null };
  };
  const linhas = [...document.querySelectorAll('#tabela-body tr')].map((tr) => {
    if (tr.classList.contains('group')) return { tipo: 'grupo', texto: texto(tr) };
    const tds = [...tr.querySelectorAll('td')].map(texto);
    const badge = tr.querySelector('.badge');
    return {
      tipo: 'dado', total: tr.classList.contains('total'),
      pilar: tds[0], previsto: tds[1], executado: tds[2],
      saldo: tds[3], pct: tds[4],
      farol: texto(badge), farolClasse: badge ? badge.className : null,
    };
  });
  return {
    chips,
    legendaProj: texto(document.getElementById('lg-proj')),
    cards,
    ppi: grafico('chart-ppi'), rodapePpi: rodape('foot-ppi'),
    at: grafico('chart-at'), rodapeAt: rodape('foot-at'),
    outras: grafico('chart-outras'), rodapeOutras: rodape('foot-outras'),
    th1: texto(document.getElementById('th-1')),
    th2: texto(document.getElementById('th-2')),
    tabela: linhas,
    consolidado: grafico('chart-consolidado'),
    consolLegenda: texto(document.getElementById('consol-legend')),
    descSecao: texto(document.getElementById('section-desc')),
    descGraficos: texto(document.getElementById('charts-sub')),
    descTabela: texto(document.getElementById('table-sub')),
    descConsol: texto(document.getElementById('consol-sub')),
  };
}`;

test.describe('L0 — matriz dos 10 estados', () => {
  test('extrator percorre anos × bases, salva JSON e screenshots', async ({ page }) => {
    fs.mkdirSync(EVID, { recursive: true });
    await page.goto(PAGINA, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(600);

    const dataStore = await page.locator('#data-store').textContent();
    fs.writeFileSync(path.join(EVID, 'data-store.json'), (dataStore ?? '').trim());

    const matriz: Record<string, unknown> = {};
    for (const base of BASES) {
      await page.locator(`#mode-toggle button[data-mode="${base.modo}"]`).click();
      for (const ano of ANOS) {
        await page.locator('#year-select').selectOption(ano.valor);
        await page.waitForTimeout(150);
        const estado = await page.evaluate(`(${EXTRAIR_ESTADO})()`);
        const chave = `ano-${ano.rotulo}_base-${base.rotulo}`;
        matriz[chave] = estado;
        fs.writeFileSync(path.join(EVID, `estado-${chave}.json`), JSON.stringify(estado, null, 2));
        await page.screenshot({ path: path.join(EVID, `estado-${chave}.png`), fullPage: true });
      }
    }
    fs.writeFileSync(path.join(EVID, 'matriz-estados.json'), JSON.stringify(matriz, null, 2));
    expect(Object.keys(matriz)).toHaveLength(10);
  });
});

test.describe('L0 — comportamentos', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(PAGINA, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(500);
  });

  test('header sticky sob scroll + offset da sidebar', async ({ page }) => {
    await page.evaluate(() => window.scrollTo(0, 900));
    await page.waitForTimeout(200);
    const topbar = await page.locator('#topbar').boundingBox();
    const topVar = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--topbar-h'));
    await page.screenshot({ path: path.join(EVID, 'comportamento-sticky.png') });
    expect(topbar).not.toBeNull();
    expect(Math.round(topbar!.y)).toBe(0);
    expect(topVar.trim().length).toBeGreaterThan(0);
  });

  test('colapsáveis da sidebar alternam grupo e aria-expanded', async ({ page }) => {
    const grupo = page.locator('.nav-group[data-target="grp-pilares"]');
    const sub = page.locator('#grp-pilares');
    await expect(sub).not.toHaveClass(/open/);
    await grupo.click();
    await expect(sub).toHaveClass(/open/);
    await expect(grupo).toHaveAttribute('aria-expanded', 'true');
    await page.screenshot({ path: path.join(EVID, 'comportamento-sidebar.png') });
    await grupo.click();
    await expect(sub).not.toHaveClass(/open/);
    await expect(grupo).toHaveAttribute('aria-expanded', 'false');
    const contas = page.locator('.nav-group[data-target="grp-contas"]');
    await contas.click();
    await expect(page.locator('#grp-contas')).toHaveClass(/open/);
  });

  test('modal abre, fecha por X, por backdrop e por ESC', async ({ page }) => {
    const modal = page.locator('#info-modal');
    await expect(modal).not.toHaveClass(/open/);
    await page.locator('#btn-info').click();
    await expect(modal).toHaveClass(/open/);
    await page.screenshot({ path: path.join(EVID, 'comportamento-modal.png') });
    const titulo = (await page.locator('#info-modal .modal h3').textContent())?.trim();
    expect(titulo).toBe('Farol de execução: metodologia e leitura');
    await page.locator('#info-modal [data-close]').click();
    await expect(modal).not.toHaveClass(/open/);
    await page.locator('#btn-info').click();
    await expect(modal).toHaveClass(/open/);
    await page.mouse.click(30, 300);
    await expect(modal).not.toHaveClass(/open/);
    await page.locator('#btn-info').click();
    await page.keyboard.press('Escape');
    await expect(modal).not.toHaveClass(/open/);
  });

  test('edição abre grade, salva altera e restaura padrão', async ({ page }) => {
    const subAntes = (await page.locator('#kpi-grid .kpi .sub').first().textContent())?.trim();
    const badgeAntes = (await page.locator('#kpi-grid .kpi .badge').first().textContent())?.trim();
    await page.locator('#btn-edit').click();
    await expect(page.locator('#editor')).toHaveClass(/open/);
    await expect(page.locator('#btn-edit')).toHaveText(/Fechar edição/);
    const cabecalhos = await page.locator('#editor-body .edit-caption').allTextContents();
    expect(cabecalhos.length).toBeGreaterThanOrEqual(4);
    const totalInputs = await page.locator('#editor-body input[type="number"]').count();
    expect(totalInputs).toBeGreaterThan(0);
    await page.screenshot({ path: path.join(EVID, 'comportamento-editor.png') });
    const primeiro = page.locator('#editor-body input[type="number"]').first();
    await primeiro.fill('99');
    await page.locator('#btn-save').click();
    await page.waitForTimeout(200);
    const subDepois = (await page.locator('#kpi-grid .kpi .sub').first().textContent())?.trim();
    expect(subDepois).not.toBe(subAntes);
    await page.locator('#btn-reset').click();
    await page.waitForTimeout(200);
    const subReset = (await page.locator('#kpi-grid .kpi .sub').first().textContent())?.trim();
    const badgeReset = (await page.locator('#kpi-grid .kpi .badge').first().textContent())?.trim();
    expect(subReset).toBe(subAntes);
    expect(badgeReset).toBe(badgeAntes);
  });

  test('tooltip aparece no hover da barra', async ({ page }) => {
    const barra = page.locator('#chart-ppi svg rect[data-tip]').first();
    await barra.hover();
    const tip = page.locator('#tip');
    await expect(tip).toBeVisible();
    const texto = await tip.textContent();
    expect((texto ?? '').length).toBeGreaterThan(0);
  });
});
