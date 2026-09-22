import { expect, test, type Page } from '@playwright/test';

async function login(page: Page, username = 'erica', password = 'erica123') {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill(username);
  await page.getByLabel('Senha').fill(password);
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('navega entre 5 paginas pela sidebar com boost', async ({ page }) => {
  await login(page);
  await expect(page.getByTestId('sidebar')).toBeVisible();

  const rotas: Array<[RegExp, string, RegExp]> = [
    [/^Lançamentos/, '/lancamentos/2/1/', /lançamentos mensais/i],
    [/^Aprovação/, '/aprovacao/2/', /painel de aprovação/i],
    [/^Financeiro$/, '/financeiro/', /financeiro consolidado/i],
    [/^Relatórios$/, '/relatorio/mensal/3/', /relatório mensal/i],
    [/^Auditoria$/, '/auditoria/', /auditoria/i],
  ];

  for (const [nome, caminho, titulo] of rotas) {
    await page.getByTestId('sidebar').getByRole('link', { name: nome }).click();
    await expect(page).toHaveURL(new RegExp(caminho.replace(/\//g, '\\/')));
    await expect(page.getByRole('heading', { name: titulo }).first()).toBeVisible();
    await expect(page).toHaveTitle(/Portal QuIIN/);
  }

  await page.getByTestId('sidebar').getByRole('link', { name: /^Geral/ }).click();
  await expect(page.getByRole('heading', { name: /gestão do quiin/i })).toBeVisible();
});

test('grupos da sidebar colapsam com aria-expanded e persistem', async ({ page }) => {
  await login(page);
  const grupo = page.getByRole('button', { name: /pilares/i });
  await expect(grupo).toHaveAttribute('aria-expanded', 'true');
  await grupo.click();
  await expect(grupo).toHaveAttribute('aria-expanded', 'false');
  await expect(page.locator('#grp-pilares')).toBeHidden();
  await page.reload();
  await expect(page.getByRole('button', { name: /pilares/i })).toHaveAttribute('aria-expanded', 'false');
  await page.getByRole('button', { name: /pilares/i }).click();
  await expect(page.locator('#grp-pilares')).toBeVisible();
});

test('prestação de contas leva a mensal e semestral', async ({ page }) => {
  await login(page);
  await page.getByTestId('sidebar').getByRole('link', { name: /^Mensal/ }).click();
  await expect(page).toHaveURL(/prestacao\/mensal/);
  await expect(page.getByRole('heading', { name: /dashboard executivo/i })).toBeVisible();
  await page.getByTestId('sidebar').getByRole('link', { name: /^Semestral/ }).click();
  await expect(page).toHaveURL(/prestacao\/semestral/);
  await expect(page.getByRole('heading', { name: /semestral/i })).toBeVisible();
});

test('pilar com filtro anual exibe painel e mantém seção mensal', async ({ page }) => {
  await login(page);
  await page.goto('/pilar/1/?ano=2026&base=fis');
  await expect(page.getByTestId('context-chips')).toContainText('Ano 3: 2026');
  await expect(page.getByTestId('painel-pilar')).toBeVisible();
  await expect(page.getByRole('heading', { name: /prestação mensal do pilar/i })).toBeVisible();
});

test('sidebar mobile abre, navega e fecha', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  const sidebar = page.getByTestId('sidebar');
  await expect(sidebar).not.toBeInViewport();
  await page.getByTestId('sidebar-toggle').click();
  await expect(sidebar).toBeInViewport();
  await sidebar.getByRole('link', { name: /Auditoria/ }).click();
  await expect(page.getByRole('heading', { name: /auditoria/i })).toBeVisible();
  await expect(sidebar).not.toBeInViewport();
});

test('breadcrumbs refletem a hierarquia', async ({ page }) => {
  await login(page);
  await page.goto('/pilar/1/');
  const breadcrumbs = page.getByTestId('breadcrumbs');
  await expect(breadcrumbs).toBeVisible();
  await expect(breadcrumbs).toContainText('Início');
  await expect(breadcrumbs.locator('[aria-current="page"]')).toHaveText('PDI / FCCT');
});

test('busca global encontra indicador visivel', async ({ page }) => {
  await login(page);
  await Promise.all([
    page.waitForResponse((r) => r.url().includes('/busca/') && r.url().includes('q=artigos')),
    page.getByTestId('busca-global').fill('artigos'),
  ]);
  await expect(page.getByTestId('busca-lista')).toBeVisible();
  await expect(page.getByTestId('busca-lista')).toContainText('Artigos publicados');
});

test('seletor de periodo muda o dashboard mensal', async ({ page }) => {
  await login(page);
  await page.goto('/prestacao/mensal/');
  await page.getByTestId('period-selector-dashboard').selectOption({ label: '2026-05 — Fechado' });
  await expect(page).toHaveURL(/periodo=2026-05-01/);
  await expect(page.getByText(/Lançamentos — 2026-05/)).toBeVisible();
});

test('papel ativo aparece no topbar', async ({ page }) => {
  await login(page);
  await expect(page.getByTestId('papel-badge')).toHaveText('Master');
});

test('L10 topbar full-width com sidebar abaixo e scroll único', async ({ page }) => {
  await login(page);
  await page.goto('/?ano=todos&base=fin');
  const geo = await page.evaluate(() => {
    const header = document.querySelector('[data-testid="app-header"]') as HTMLElement;
    const sidebar = document.querySelector('[data-testid="sidebar"]') as HTMLElement;
    const hc = header.getBoundingClientRect();
    const sc = sidebar.getBoundingClientRect();
    return {
      larguraViewport: window.innerWidth,
      headerX: Math.round(hc.x),
      headerLargura: Math.round(hc.width),
      sidebarTopo: Math.round(sc.y),
      headerBase: Math.round(hc.bottom),
      overflowSidebar: getComputedStyle(sidebar).overflowY,
    };
  });
  expect(geo.headerX).toBe(0);
  expect(Math.abs(geo.headerLargura - geo.larguraViewport)).toBeLessThanOrEqual(1);
  expect(geo.sidebarTopo).toBeGreaterThanOrEqual(geo.headerBase - 1);
  expect(geo.overflowSidebar).toBe('visible');
});

test('L10 botões em linha própria alinhados à direita', async ({ page }) => {
  await login(page);
  await page.goto('/?ano=todos&base=fin');
  const geo = await page.evaluate(() => {
    const header = document.querySelector('[data-testid="app-header"]') as HTMLElement;
    const chips = document.querySelector('[data-testid="context-chips"]') as HTMLElement;
    const toolbar = document.querySelector('[role="toolbar"]') as HTMLElement;
    const hc = header.getBoundingClientRect();
    const cc = chips.getBoundingClientRect();
    const tc = toolbar.getBoundingClientRect();
    return {
      bordaDireita: Math.round(hc.right),
      chipsDireita: Math.round(cc.right),
      toolbarDireita: Math.round(tc.right),
      chipsBase: Math.round(cc.bottom),
      toolbarTopo: Math.round(tc.top),
    };
  });
  expect(geo.toolbarTopo).toBeGreaterThanOrEqual(geo.chipsBase - 1);
  expect(geo.bordaDireita - geo.toolbarDireita).toBeLessThanOrEqual(48);
  expect(geo.bordaDireita - geo.chipsDireita).toBeLessThanOrEqual(48);
});

test('L11 botoes da toolbar na escala do mockup (12px, raio 8px, mesma linha)', async ({ page }) => {
  await login(page);
  await page.goto('/?ano=todos&base=fin');
  const botoes = page.locator('[role="toolbar"] a, [role="toolbar"] button');
  await expect(botoes).toHaveCount(5);
  const metricas = await botoes.evaluateAll((els) =>
    els.map((el) => {
      const cs = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      return {
        fonte: cs.fontSize,
        padTopo: cs.paddingTop,
        padEsq: cs.paddingLeft,
        raio: cs.borderRadius,
        topo: Math.round(r.top),
        direita: Math.round(r.right),
        altura: Math.round(r.height),
      };
    }),
  );
  for (const m of metricas) {
    expect(m.fonte).toBe('12px');
    expect(m.padTopo).toBe('8px');
    expect(m.padEsq).toBe('16px');
    expect(m.raio).toBe('8px');
  }
  const topos = new Set(metricas.map((m) => m.topo));
  expect(topos.size).toBe(1);
  const alturas = new Set(metricas.map((m) => m.altura));
  expect(alturas.size).toBe(1);
  const bordaHeader = await page.getByTestId('app-header').evaluate((el) => el.getBoundingClientRect().right);
  expect(bordaHeader - Math.max(...metricas.map((m) => m.direita))).toBeLessThanOrEqual(48);
});

test('L11 botoes-icone do header em 32px com icones 16px', async ({ page }) => {
  await login(page);
  await page.goto('/?ano=todos&base=fin');
  for (const seletor of ['[data-testid="dark-toggle"]', 'button[aria-label="Sair"]']) {
    const botao = page.locator(seletor);
    const caixa = await botao.boundingBox();
    expect(Math.round(caixa?.width ?? 0)).toBe(32);
    expect(Math.round(caixa?.height ?? 0)).toBe(32);
    const svg = await botao.locator('svg').nth(0).evaluate((el) => ({
      w: Math.round(el.getBoundingClientRect().width),
      h: Math.round(el.getBoundingClientRect().height),
    }));
    expect(svg.w).toBe(16);
    expect(svg.h).toBe(16);
  }
});

test('L17 navegacao com boost mantem o header coerente com a pagina', async ({ page }) => {
  await login(page);
  await page.goto('/pilar/1/?ano=2026&base=fin');

  // Pilar 1 -> Pilar 4 (AT) pela sidebar: o toggle de base deve mirar o pilar 4.
  await page.locator('#grp-pilares').getByRole('link', { name: /Associação Tecnológica/ }).click();
  await expect(page).toHaveURL(/pilar\/4\/$/);
  const fisicoAT = page.getByTestId('base-toggle').getByRole('link', { name: 'Físico' });
  await expect(fisicoAT).toHaveAttribute('href', /pilar\/4\/.*base=fis/);
  await fisicoAT.click();
  await expect(page).toHaveURL(/pilar\/4\/\?.*ano=todos.*base=fis/);
  await expect(page.getByTestId('context-chips')).toContainText('Unidade: quantidade de metas');
  await expect(page.getByTestId('painel-pilar')).toContainText('Captado');

  // Pilar 4 -> Geral: o toggle de base deve voltar ao escopo do dashboard.
  await page.getByTestId('sidebar').getByRole('link', { name: /^Geral/ }).click();
  await expect(page).toHaveURL(/127\.0\.0\.1:8000\/$/);
  const fisicoGeral = page.getByTestId('base-toggle').getByRole('link', { name: 'Físico' });
  await expect(fisicoGeral).toHaveAttribute('href', /^\/?\?ano=todos&base=fis$/);
  await fisicoGeral.click();
  await expect(page).toHaveURL(/\/\?ano=todos&base=fis/);
  await expect(page.getByTestId('dashboard-panel')).toBeVisible();
  await expect(page.getByTestId('context-chips')).toContainText('Base: Físico');

  // Geral -> Mensal: pagina sem controles nao pode herdar o toggle antigo.
  await page.getByTestId('sidebar').getByRole('link', { name: /^Mensal/ }).click();
  await expect(page).toHaveURL(/prestacao\/mensal/);
  await expect(page.getByTestId('base-toggle')).toHaveCount(0);
});

test('L11 sidebar acompanha a rolagem principal (sem scroll exclusivo)', async ({ page }) => {
  await login(page);
  await page.goto('/?ano=todos&base=fin');
  const sidebar = page.getByTestId('sidebar');
  const topoAntes = Math.round((await sidebar.boundingBox())?.y ?? 0);
  expect(topoAntes).toBeGreaterThan(0);
  await page.evaluate(() => window.scrollTo(0, 600));
  await page.waitForTimeout(250);
  const topoDepois = Math.round((await sidebar.boundingBox())?.y ?? 0);
  expect(topoDepois).toBeLessThan(topoAntes);
  const overflow = await sidebar.evaluate((el) => getComputedStyle(el).overflowY);
  expect(overflow).toBe('visible');
});

test('L18 header anual: filtros acima dos chips; só Editar dados primário', async ({ page }) => {
  await login(page);
  for (const url of ['/?ano=todos&base=fin', '/pilar/1/']) {
    await page.goto(url);
    const geometria = await page.evaluate(() => {
      const caixa = (sel: string) => (document.querySelector(sel) as HTMLElement).getBoundingClientRect();
      return {
        filtrosBase: Math.round(Math.max(caixa('#year-select').bottom, caixa('[data-testid="base-toggle"]').bottom)),
        chipsTopo: Math.round(caixa('[data-testid="context-chips"]').top),
      };
    });
    expect(geometria.chipsTopo).toBeGreaterThanOrEqual(geometria.filtrosBase - 1);
    const botoes = page.locator('[role="toolbar"] a, [role="toolbar"] button');
    await expect(botoes).toHaveCount(5);
    const fundos = await botoes.evaluateAll((els) => els.map((el) => getComputedStyle(el).backgroundColor));
    expect(fundos.filter((fundo) => fundo === 'rgb(4, 4, 126)')).toHaveLength(1);
    await expect(page.locator('[role="toolbar"] [data-testid="btn-editar-dados"]'))
      .toHaveCSS('background-color', 'rgb(4, 4, 126)');
  }
});

test('L19 barra do painel pode ser ocultada e o estado persiste', async ({ page }) => {
  await login(page);
  await page.goto('/?ano=todos&base=fin');
  const alternador = page.getByTestId('barra-toggle');
  const controles = page.getByTestId('dashboard-controls');
  await expect(controles).toBeVisible();
  await expect(alternador).toHaveAttribute('aria-expanded', 'true');

  await alternador.click();
  await expect(controles).toBeHidden();
  await expect(alternador).toHaveAttribute('aria-expanded', 'false');
  await expect(alternador).toHaveAttribute('aria-label', 'Mostrar filtros e ações');
  expect(await page.evaluate(() => localStorage.getItem('quiin-barra'))).toBe('oculta');

  await page.reload();
  await expect(controles).toBeHidden();

  // Oculto sobrevive à navegação com boost (header trocado via OOB).
  await page.locator('#grp-pilares').getByRole('link', { name: /^PDI/ }).click();
  await expect(page).toHaveURL(/pilar\/1\/$/);
  await expect(controles).toBeHidden();
  await expect(alternador).toHaveAttribute('aria-expanded', 'false');

  await alternador.click();
  await expect(controles).toBeVisible();
  await expect(alternador).toHaveAttribute('aria-expanded', 'true');
  await page.getByTestId('base-toggle').getByRole('link', { name: 'Físico' }).click();
  await expect(page.getByTestId('context-chips')).toContainText('Unidade: quantidade de metas');
  await expect(controles).toBeVisible();

  // Página sem painel não tem o botão.
  await page.getByTestId('sidebar').getByRole('link', { name: /^Mensal/ }).click();
  await expect(page).toHaveURL(/prestacao\/mensal/);
  await expect(alternador).toHaveCount(0);
});
