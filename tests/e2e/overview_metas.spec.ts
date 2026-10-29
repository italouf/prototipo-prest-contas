import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

test('AT e Outras Fontes: captação e execução em blocos separados', async ({ page }, info) => {
  await page.locator('#grp-pilares').getByRole('link', { name: 'AT e Outras Fontes', exact: true }).click();
  const at = page.getByTestId('resumo-financeiro-AT');
  const outras = page.getByTestId('resumo-financeiro-OUTRASFONTES');
  await expect(at.locator('.overview-card-title h3')).toHaveText(['Meta de captação do recurso', 'Recurso captado total', 'Diferença captação']);
  await expect(outras.locator('.overview-card-title h3')).toHaveText(['Meta de execução dos recursos', 'Recurso executado total', 'Diferença execução']);
  await expect(at.locator('.overview-card-value')).toHaveText(['R$ 7,75 milhões', 'R$ 5,62 milhões', 'R$ 2,13 milhões']);
  await expect(outras.locator('.overview-card-value')).toHaveText(['R$ 6,30 milhões', 'R$ 242,11 mil', 'R$ 6,06 milhões']);
  await expect(outras).toContainText('3,84% da meta');
  const atBox = await at.boundingBox();
  const outrasBox = await outras.boundingBox();
  expect(outrasBox!.y).toBeGreaterThanOrEqual(atBox!.y + atBox!.height);
  const cardBoxes = await at.locator('.overview-card').evaluateAll(els => els.map(el => el.getBoundingClientRect().y));
  expect(new Set(cardBoxes).size).toBe(1);
  await page.getByTestId('financeiro-accordion').locator('summary').first().click();
  const tabela = page.locator('.pillar-capture-table');
  await expect(tabela.locator('thead th')).toHaveCount(8);
  await expect(tabela.locator('tbody tr')).toHaveCount(3);
  await expect(tabela.locator('tbody tr').last().locator('td').nth(3)).toHaveText('15.843.468,00');
  await page.screenshot({ path: info.outputPath('fontes-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await expect(at.locator('.overview-card')).toHaveCount(3);
  await expect(outras.locator('.overview-card')).toHaveCount(3);
  await page.screenshot({ path: info.outputPath('fontes-mobile.png'), fullPage: true });
});

test.skip(!process.env.QUIIN_OVERVIEW_E2E, 'Use --config=playwright.overview.config.ts para executar em banco isolado.');

async function login(page: Page) {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill('overview-e2e');
  await page.getByLabel('Senha', { exact: true }).fill('overview-test-123');
  await page.getByRole('button', { name: /entrar/i }).click();
  await expect(page.getByTestId('dashboard-panel')).toBeVisible();
}
async function expand(page: Page) {
  await page.getByTestId('programa-accordion').locator('summary').first().click();
  await page.getByTestId('anual-accordion').locator('summary').first().click();
}

test.beforeEach(async ({ page }) => login(page));

test('produtos da AT: catálogo, materiais, filtros e exportação', async ({ page }, info) => {
  test.setTimeout(120_000);
  const link = page.locator('#grp-pilares').getByRole('link', { name: 'AT e Outras Fontes', exact: true });
  const destino = new URL((await link.getAttribute('href'))!, page.url());
  await link.click();
  await expect(page).toHaveURL(destino.href);
  await expect(page.getByTestId('painel-pilar')).toHaveAttribute('data-base', 'fin');
  const fisico = page.getByTestId('base-toggle').getByRole('link', { name: 'Físico', exact: true });
  await expect.poll(async () => new URL((await fisico.getAttribute('href'))!, page.url()).pathname).toBe(destino.pathname);
  await fisico.click();
  const quadro = page.getByTestId('entregaveis-at-accordion');
  await quadro.locator('summary').first().click();
  await expect(quadro.locator('thead th')).toHaveText(['Produto', 'Materiais do produto', 'Ações']);
  await expect(quadro.locator('tbody tr')).toHaveCount(9);
  await expect(quadro.locator('tbody tr').last()).toContainText('Propriedade Intelectual (PI)');
  await expect(quadro).not.toContainText('Book geral');
  await quadro.getByRole('link', { name: 'Adicionar material', exact: true }).first().click();
  await expect(page.getByLabel(/^Tipo/).locator('option')).toHaveText(['---------', 'Apresentação', 'Relatório', 'Boletim', 'Documento', 'Certificado', 'Artigo', 'Outros']);
  await page.getByLabel(/^Título/).fill('Apresentação do grupo de trabalho');
  await page.getByLabel(/^Tipo/).selectOption('APRESENTACAO');
  await page.getByLabel('Link do material').fill('https://example.org/grupo-at');
  await page.getByRole('button', { name: 'Salvar', exact: true }).click();
  await expect(quadro).toContainText('1 material');
  await quadro.getByRole('link', { name: 'Ver materiais', exact: true }).first().click();
  await expect(page.getByRole('link', { name: 'Apresentação do grupo de trabalho', exact: true })).toHaveAttribute('href', 'https://example.org/grupo-at');
  await page.getByRole('link', { name: 'Editar', exact: true }).click();
  await page.getByLabel(/^Título/).fill('Relatório do grupo de trabalho');
  await page.getByLabel(/^Tipo/).selectOption('RELATORIO');
  await page.getByRole('button', { name: 'Salvar', exact: true }).click();
  await expect(page.getByTestId('lista-materiais')).toContainText('Relatório do grupo de trabalho');
  await page.getByRole('link', { name: 'Voltar à consulta anterior' }).click();
  await quadro.getByRole('link', { name: 'Novo produto', exact: true }).click();
  await page.getByLabel('Nome do produto').fill('Produto AT de validação');
  await expect(page.getByLabel('Ordem de exibição')).toHaveValue('9');
  await page.getByRole('button', { name: 'Salvar', exact: true }).click();
  await expect(quadro.locator('tbody tr')).toHaveCount(10);
  await quadro.getByRole('link', { name: 'Gerenciar produtos e materiais' }).click();
  let produto = page.locator('.project-management-card').filter({ has: page.getByRole('heading', { name: 'Produto AT de validação', exact: true }) });
  await produto.getByRole('link', { name: 'Editar produto e ordem' }).click();
  await page.getByLabel('Nome do produto').fill('Produto AT revisado');
  await page.getByLabel('Ordem de exibição').fill('0');
  await page.getByRole('button', { name: 'Salvar', exact: true }).click();
  await expect(quadro).toContainText('Produto AT revisado');
  await quadro.getByRole('link', { name: 'Gerenciar produtos e materiais' }).click();
  produto = page.locator('.project-management-card').filter({ has: page.getByRole('heading', { name: 'Produto AT revisado' }) });
  await produto.getByRole('button', { name: 'Arquivar produto', exact: true }).click();
  await produto.getByRole('button', { name: 'Reativar produto', exact: true }).click();
  await page.getByRole('link', { name: 'Voltar aos entregáveis da AT' }).click();
  await expect(quadro.locator('tbody tr')).toHaveCount(10);
  await page.locator('#overview-start').fill('01/2025');
  await page.locator('#overview-start').press('Tab');
  await expect.poll(() => new URL(page.url()).searchParams.get('mes_inicial')).toBe('01/2025');
  if (await quadro.getAttribute('open') === null) await quadro.locator('summary').first().click();
  await expect(quadro).toContainText('1 material');
  await expect(quadro).not.toContainText('Relatório do grupo de trabalho');
  const csv = await page.request.get((await quadro.getByRole('link', { name: 'Baixar entregáveis da AT (CSV)' }).getAttribute('href'))!);
  expect(await csv.text()).toContain('https://example.org/grupo-at');
  await page.screenshot({ path: info.outputPath('produtos-at-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath('produtos-at-mobile.png'), fullPage: true });
  await page.setViewportSize({ width: 1123, height: 794 });
  await page.emulateMedia({ media: 'print' });
  const pdf = await page.pdf({ path: info.outputPath('produtos-at.pdf'), landscape: true, printBackground: true });
  expect(pdf.subarray(0, 4).toString()).toBe('%PDF');
});

test('entregáveis físicos: materiais próprios e Book geral nos três pilares', async ({ page }, info) => {
  test.setTimeout(120_000);
  async function abrirFisico(nome: string) {
    const link = page.locator('#grp-pilares').getByRole('link', { name: nome, exact: true });
    const destino = new URL((await link.getAttribute('href'))!, page.url());
    const caminho = destino.pathname;
    await link.click();
    await expect(page).toHaveURL(destino.href);
    await expect(page.getByTestId('painel-pilar')).toBeVisible();
    await expect(page.getByTestId('painel-pilar')).toHaveAttribute('data-base', destino.searchParams.get('base') || 'fin');
    const fisico = page.getByTestId('base-toggle').getByRole('link', { name: 'Físico', exact: true });
    await expect.poll(async () => new URL((await fisico.getAttribute('href'))!, page.url()).pathname).toBe(caminho);
    if (await page.getByTestId('painel-pilar').getAttribute('data-base') !== 'fis') await fisico.click();
    await expect(page.getByTestId('painel-pilar')).toHaveAttribute('data-base', 'fis');
  }
  await abrirFisico('PDI');
  let quadro = page.getByTestId('entregaveis-accordion');
  await quadro.locator('summary').first().click();
  await expect(quadro).toContainText('Carteira completa');
  await expect(quadro.locator('tbody tr')).toHaveCount(18);
  await quadro.getByRole('link', { name: 'Adicionar material', exact: true }).first().click();
  await page.getByLabel(/^Título/).fill('Artigo de validação PDI');
  await page.getByLabel(/^Tipo/).selectOption('ARTIGO');
  await page.getByLabel('Link do material').fill('https://example.org/artigo-pdi');
  await page.getByRole('button', { name: 'Salvar', exact: true }).click();
  await expect(quadro).toContainText('1 material');
  await quadro.getByRole('link', { name: 'Ver materiais', exact: true }).first().click();
  await expect(page.getByRole('link', { name: 'Artigo de validação PDI', exact: true })).toHaveAttribute('href', 'https://example.org/artigo-pdi');
  await page.getByRole('link', { name: 'Editar', exact: true }).click();
  await page.getByLabel(/^Título/).fill('Artigo PDI revisado');
  await page.getByRole('button', { name: 'Salvar', exact: true }).click();
  await expect(page.getByTestId('lista-materiais')).toContainText('Artigo PDI revisado');
  await page.getByRole('link', { name: 'Voltar à consulta anterior' }).click();
  await quadro.getByRole('link', { name: 'Novo projeto', exact: true }).click();
  await page.getByLabel('Nome do projeto').fill('Projeto físico de validação');
  await page.getByRole('button', { name: 'Salvar', exact: true }).click();
  await expect(quadro.locator('tbody tr')).toHaveCount(19);
  await quadro.getByRole('link', { name: 'Cadastrar Book geral', exact: true }).click();
  await page.getByLabel('Título do Book').fill('Book geral de validação');
  await page.getByLabel('Link do Book').fill('https://example.org/book-geral');
  await page.getByRole('button', { name: 'Salvar', exact: true }).click();
  for (const [nome, quantidade] of [['PDI', 19], ['FCRH', 8], ['ACS', 7]] as const) {
    await abrirFisico(nome);
    quadro = page.getByTestId('entregaveis-accordion');
    if (!(await quadro.getAttribute('open') !== null)) await quadro.locator('summary').first().click();
    await expect(quadro.getByRole('link', { name: /^Abrir Book geral para/ })).toHaveCount(quantidade);
    if (nome !== 'PDI') await expect(quadro).not.toContainText('Artigo PDI revisado');
  }
  await page.locator('#overview-start').fill('01/2025');
  await page.locator('#overview-start').press('Tab');
  await expect.poll(() => new URL(page.url()).searchParams.get('mes_inicial')).toBe('01/2025');
  if (await quadro.getAttribute('open') === null) await quadro.locator('summary').first().click();
  await expect(quadro.locator('tbody tr')).toHaveCount(7);
  await expect(quadro).toContainText('Book geral de validação');
  await page.screenshot({ path: info.outputPath('entregaveis-desktop.png'), fullPage: true });
  const csv = await page.request.get((await quadro.getByRole('link', { name: 'Baixar entregáveis (CSV)' }).getAttribute('href'))!);
  expect(await csv.text()).toContain('https://example.org/book-geral');
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath('entregaveis-mobile.png'), fullPage: true });
  await page.setViewportSize({ width: 1123, height: 794 });
  await page.emulateMedia({ media: 'print' });
  const pdf = await page.pdf({ path: info.outputPath('entregaveis.pdf'), landscape: true, printBackground: true });
  expect(pdf.subarray(0, 4).toString()).toBe('%PDF');
});

test('filtros no conteúdo, seis cards e quadros financeiros independentes', async ({ page }, info) => {
  const header = page.getByTestId('app-header');
  const controls = page.getByTestId('dashboard-controls');
  await expect(header.getByTestId('base-toggle')).toBeVisible();
  await expect(header.locator('#dashboard-controls')).toHaveCount(0);
  await expect(controls).toBeVisible();
  const heading = await page.getByRole('heading', { name: 'Visão geral', exact: true }).boundingBox();
  const filters = await controls.boundingBox();
  expect(filters!.y).toBeGreaterThan(heading!.y);
  await expect(page.locator('.overview-financial-cards .overview-card-title > h3')).toHaveText([
    'Recurso PPI realizado', 'Realizado AT', 'Recurso captado AT',
    'Outras fontes realizado', 'Outras fontes captado', 'Realizado consolidado',
  ]);
  await expect(page.getByTestId('kpi-total')).toContainText('R$ 74,05 milhões');
  await expand(page);
  const captacao = page.getByTestId('fontes-captado');
  const execucao = page.getByTestId('fontes-realizado');
  await expect(captacao.locator('tbody tr')).toHaveCount(2);
  await expect(captacao.locator('tfoot')).toContainText('-1,79');
  await expect(execucao.locator('tfoot')).toContainText('0,46');
  await expect(captacao.locator('tbody tr').nth(1)).toContainText('162,32%');
  await expect(execucao.locator('tbody tr').first()).toContainText('2,84%');
  await expect(captacao.locator('tfoot')).not.toContainText('PPI');
  await expect(page.getByTestId('tabela-anual-ppi').locator('thead tr').last().locator('th')).toHaveText([
    'Ação', 'Recurso PPI total', 'Meta ano 1 - 2024', 'Realizado ano 1 - 2024',
    'Meta ano 2 - 2025', 'Realizado ano 2 - 2025', 'Meta ano 3 - 2026',
    'Realizado ano 3 (YTD) - 2026', 'Projetado 2026', 'Projetado 2027',
    'Total projetado', 'Realizado + projetado', 'Diferença ($)', '% executado', 'Farol',
  ]);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: info.outputPath('overview-desktop.png'), fullPage: true });
});

test('HTMX preserva estado e evita duplicação ao trocar base e pilares', async ({ page }) => {
  await page.evaluate(() => { (window as any).__overviewMarker = 42; });
  await page.getByTestId('base-toggle').getByRole('link', { name: 'Físico' }).click();
  await expect(page.getByTestId('dashboard-panel')).toHaveAttribute('data-base', 'fis');
  await expect(page.getByTestId('dashboard-controls')).toHaveCount(1);
  await page.getByTestId('base-toggle').getByRole('link', { name: 'Financeiro' }).click();
  await expect(page.getByTestId('dashboard-panel')).toHaveAttribute('data-base', 'fin');
  expect(await page.evaluate(() => (window as any).__overviewMarker)).toBe(42);
  await page.getByTestId('pilares-filter').locator('summary').click();
  await page.locator('[data-pilares-todos]').uncheck();
  await page.getByTestId('pilares-filter').locator('input[name="pilares"][value="AT"]').check();
  await page.getByTestId('pilares-filter').getByRole('button', { name: 'Aplicar', exact: true }).click();
  await expect(page).toHaveURL(/pilares=AT/);
  await expect(page.getByTestId('dashboard-controls')).toHaveCount(1);
  await expect(page.getByTestId('base-toggle')).toHaveCount(1);
  await page.getByTestId('programa-accordion').locator('summary').first().click();
  await expect(page.getByTestId('fontes-captado').locator('tbody tr')).toHaveCount(1);
  await expect(page.getByTestId('fontes-captado').locator('tfoot')).toContainText('7,75');
  await page.reload();
  await expect(page.getByTestId('pilares-filter').locator('summary')).toContainText('1 pilares selecionados');
  await page.getByTestId('pilares-filter').locator('summary').click();
  await page.getByTestId('pilares-filter').getByRole('button', { name: 'Limpar', exact: true }).click();
  await page.getByTestId('pilares-filter').getByRole('button', { name: 'Aplicar', exact: true }).click();
  await expect(page.getByTestId('dashboard-panel').getByRole('status')).toContainText('Selecione ao menos um pilar');
  await expect(page.locator('.overview-financial-cards')).toHaveCount(0);
  await page.getByTestId('remover-filtros').click();
  await expect(page.getByTestId('kpi-total')).toBeVisible();
});

test('editor salva meta anual e campo vazio restaura o importado', async ({ page }) => {
  await page.locator('.overview-more-actions > summary').click();
  await page.getByTestId('btn-editar-dados').click();
  const field = page.locator('input[name="v__2024__financeiro__PDI__meta_anual"]');
  await expect(field).toHaveValue(/^1000000(?:\.0+)?$/);
  await field.fill('1250000');
  await page.getByRole('button', { name: 'Salvar alterações', exact: true }).click();
  await page.getByRole('button', { name: 'Confirmar e salvar', exact: true }).click();
  await expect(page.getByTestId('dashboard-panel')).toBeVisible();
  await page.getByTestId('anual-accordion').locator('summary').first().click();
  await expect(page.getByTestId('tabela-anual-ppi').locator('tbody tr').first().locator('td').nth(1)).toHaveText('1,25');
  await page.locator('.overview-more-actions > summary').click();
  await page.getByTestId('btn-editar-dados').click();
  await field.fill('');
  await page.getByRole('button', { name: 'Salvar alterações', exact: true }).click();
  await page.getByRole('button', { name: 'Confirmar e salvar', exact: true }).click();
  await page.getByTestId('anual-accordion').locator('summary').first().click();
  await expect(page.getByTestId('tabela-anual-ppi').locator('tbody tr').first().locator('td').nth(1)).toHaveText('1,00');
});

test('mobile, tema escuro e impressão preservam tabelas sem cortes', async ({ page }, info) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await expand(page);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const annual = page.getByTestId('tabela-anual-ppi');
  await annual.focus();
  await page.keyboard.press('ArrowRight');
  await expect.poll(() => annual.evaluate(el => el.scrollLeft)).toBeGreaterThan(0);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: info.outputPath('overview-mobile.png'), fullPage: true });
  await page.evaluate(() => document.documentElement.classList.add('dark'));
  await page.screenshot({ path: info.outputPath('overview-dark.png'), fullPage: true });
  await page.setViewportSize({ width: 1123, height: 794 });
  await annual.evaluate(el => { el.scrollLeft = 0; });
  await page.emulateMedia({ media: 'print' });
  await expect(page.getByTestId('dashboard-controls')).toBeHidden();
  await expect(page.getByTestId('app-header')).toBeHidden();
  expect(await annual.evaluate(el => el.scrollWidth <= el.clientWidth + 2)).toBe(true);
  await page.screenshot({ path: info.outputPath('overview-print.png'), fullPage: true });
  const pdf = await page.pdf({ path: info.outputPath('overview.pdf'), format: 'A4', landscape: true, printBackground: true, preferCSSPageSize: true });
  expect(pdf.subarray(0, 4).toString()).toBe('%PDF');
  expect(errors).toEqual([]);
});

test('acessibilidade sem violações graves nos controles e tabelas', async ({ page }) => {
  await expand(page);
  const result = await new AxeBuilder({ page }).include('#dashboard-panel').include('#app-header')
    .withTags(['wcag2a', 'wcag2aa']).analyze();
  expect(result.violations.filter(v => ['critical', 'serious'].includes(v.impact || ''))).toEqual([]);
});

for (const nome of ['PDI', 'FCRH', 'ACS', 'AT e Outras Fontes']) {
  test('pilares: navbar e filtros preservam contexto de ' + nome, async ({ page }, info) => {
    await page.locator('#grp-pilares').getByRole('link', { name: nome, exact: true }).click();
    const panel = page.getByTestId('painel-pilar');
    await expect(panel).toBeVisible();
    const caminho = new URL(page.url()).pathname;
    const pilar = caminho.split('/')[2];
    const header = page.getByTestId('app-header');
    const controls = page.getByTestId('dashboard-controls');
    await expect(header.locator('#dashboard-controls')).toHaveCount(0);
    await expect(panel.getByTestId('dashboard-controls')).toHaveCount(1);
    await expect(header.getByTestId('base-toggle')).toBeVisible();
    await expect(header.locator('.brand-logos')).toBeVisible();
    const titulo = await page.locator('.overview-page-title').boundingBox();
    const filtros = await controls.boundingBox();
    expect(filtros!.y).toBeGreaterThanOrEqual(titulo!.y + titulo!.height);
    await page.evaluate(() => { (window as any).__pillarMarker = 73; });

    await header.getByTestId('base-toggle').getByRole('link', { name: 'Físico', exact: true }).click();
    await expect(panel).toHaveAttribute('data-base', 'fis');
    expect(new URL(page.url()).pathname).toBe(caminho);
    await page.locator('#overview-start').fill('01/2025');
    await page.locator('#overview-start').press('Tab');
    await expect.poll(() => new URL(page.url()).searchParams.get('mes_inicial')).toBe('01/2025');
    await page.locator('#overview-end').fill('12/2025');
    await page.locator('#overview-end').press('Tab');
    await expect.poll(() => new URL(page.url()).searchParams.get('mes_final')).toBe('12/2025');
    await header.getByTestId('base-toggle').getByRole('link', { name: 'Financeiro', exact: true }).click();
    await expect(panel).toHaveAttribute('data-base', 'fin');
    expect(new URL(page.url()).pathname).toBe(caminho);
    expect(new URL(page.url()).searchParams.get('mes_inicial')).toBe('2025-01');
    expect(new URL(page.url()).searchParams.get('mes_final')).toBe('2025-12');
    expect(new URL(page.url()).searchParams.get('acompanhamento')).toBeTruthy();
    expect(await page.evaluate(() => (window as any).__pillarMarker)).toBe(73);
    await expect(page.getByTestId('dashboard-controls')).toHaveCount(1);
    await expect(page.getByTestId('base-toggle')).toHaveCount(1);

    await controls.locator('.overview-more-actions > summary').click();
    const csv = await controls.getByRole('link', { name: 'Baixar dados (CSV)' }).getAttribute('href');
    expect(new URL(csv!, page.url()).searchParams.get('pilar')).toBe(pilar);
    await controls.locator('.overview-more-actions > summary').click();
    await page.getByTestId('remover-filtros').click();
    await expect(panel).toHaveAttribute('data-base', 'fin');
    expect(new URL(page.url()).pathname).toBe(caminho);
    await expect(page.locator('#overview-start')).toHaveValue('');
    await expect(page.locator('#overview-end')).toHaveValue('');
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: info.outputPath('pilar-desktop.png'), fullPage: true });

    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    const logos = await header.locator('.brand-logos').boundingBox();
    const usuario = await header.locator('.overview-header-actions').boundingBox();
    expect(logos!.x + logos!.width).toBeLessThanOrEqual(usuario!.x + 1);
    expect(Math.abs(logos!.y + logos!.height / 2 - usuario!.y - usuario!.height / 2)).toBeLessThan(2);
    await page.screenshot({ path: info.outputPath('pilar-mobile.png'), fullPage: true });
  });
}

for (const [nome, tabela, titulo, grupos, quantidade] of [
  ['PDI', 'PDI', 'Recurso PPI AFCCT total', 3, 18],
  ['FCRH', 'FCRH', 'Recurso PPI FCRH total', 2, 8],
  ['ACS', 'ACS', 'Recurso PPI ACS total', 3, 7],
] as const) {
  test('financeiro revisado: cards, datas, etapas e gráfico de ' + nome, async ({ page }, info) => {
    await page.locator('#grp-pilares').getByRole('link', { name: nome, exact: true }).click();
    await expect(page.locator('.pillar-financial-summary .overview-card-title > h3')).toHaveText([
      titulo, 'Recurso PPI realizado', 'Diferença rel. PPI',
    ]);
    await page.getByTestId('projetos-accordion').locator('summary').first().click();
    const projetos = page.getByTestId('tbl_Projetos' + tabela);
    await expect(projetos.locator('thead th')).toHaveCount(15);
    await expect(projetos.locator('thead')).toContainText('Assinatura da síntese');
    await expect(projetos.locator('thead')).toContainText('Final previsto na síntese');
    await expect(projetos.locator('thead')).toContainText('Data do kick-off');
    await expect(projetos.locator('thead')).toContainText('Final previsto real');
    await expect(projetos.locator('thead')).toContainText('Farol');
    await expect(projetos.locator('tbody[data-project-rows] tr')).toHaveCount(quantidade);
    await expect(projetos.locator('tbody[data-project-rows] tr > :nth-child(11) .overview-status')).toHaveCount(quantidade);
    if (nome !== 'FCRH') await expect(projetos).toContainText('Futuros projetos');
    await expect(projetos).not.toContainText('Em preparação');
    const ocultar = projetos.locator('[data-project-group-toggle]').first();
    const grupoId = await ocultar.getAttribute('aria-controls');
    await ocultar.click();
    await expect(page.locator('#' + grupoId)).toBeHidden();
    await ocultar.click();
    await expect(page.locator('#' + grupoId)).toBeVisible();

    await page.getByTestId('financeiro-accordion').locator('summary').first().click();
    const grafico = page.getByTestId('grafico-financeiro-pilar');
    await expect(grafico).toBeVisible();
    await expect(grafico.locator('.pillar-chart-stage')).toHaveCount(grupos);
    await expect(grafico).toContainText('Orçado dos projetos');
    await expect(grafico).toContainText('Projetado 2027');
    await expect(page.locator('.pillar-financial-table')).toHaveCount(0);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: info.outputPath('financeiro-desktop.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath('financeiro-mobile.png'), fullPage: true });
    if (nome === 'PDI') {
      await page.setViewportSize({ width: 1123, height: 794 });
      await page.emulateMedia({ media: 'print' });
      expect(await projetos.evaluate(el => el.scrollWidth <= el.clientWidth + 2)).toBe(true);
      const pdf = await page.pdf({ path: info.outputPath('financeiro.pdf'), landscape: true, preferCSSPageSize: true, printBackground: true });
      expect(pdf.subarray(0, 4).toString()).toBe('%PDF');
    }
  });
}
