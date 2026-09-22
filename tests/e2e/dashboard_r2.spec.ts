import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

/**
 * E2E da prestação mensal no padrão Geral/Pilares (L20).
 * Pré-requisito: `seed_demo` (períodos 2026-05 fechado, 2026-06 aberto).
 * Casos: specs/prestacao-mensal.md (M01–M09).
 */

async function login(page: Page, username = 'erica', password = 'erica123') {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill(username);
  await page.getByLabel('Senha').fill(password);
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('M01 mensal exibe KPIs, financeiro, SVG, heatmap, avisos e farol', async ({ page }) => {
  await login(page);
  await page.goto('/prestacao/mensal/');
  await expect(page.getByRole('heading', { name: /dashboard executivo/i })).toBeVisible();
  await expect(page.locator('[data-kpi-card]')).toHaveCount(6);
  await expect(page.getByTestId('kpi-pdi')).toBeVisible();
  await expect(page.getByTestId('kpi-at')).toBeVisible();
  await expect(page.getByTestId('heatmap')).toBeVisible();
  await expect(page.getByTestId('avisos')).toBeVisible();
  await expect(page.getByText('Evolução financeira mensal')).toBeVisible();
  await expect(page.getByText('Captação × execução por pilar')).toBeVisible();
  await expect(page.getByTestId('chart-fonte-mensal')).toBeVisible();
  await expect(page.getByTestId('chart-fonte-pilares')).toBeVisible();
  await expect(page.getByTestId('chart-fonte-mensal').locator('g[data-categoria="Jun 2026"]')).toHaveCount(1);
  await expect(page.getByTestId('status-distribuicao')).toBeVisible();
  await expect(page.getByText(/R\$ .* mi|R\$ \d+ mil/).first()).toBeVisible();
});

test('M02 filtro de periodo atualiza widgets via HTMX sem reload', async ({ page }) => {
  await login(page);
  await page.goto('/prestacao/mensal/');
  await page.evaluate(() => {
    (window as unknown as { __marcador: number }).__marcador = 42;
  });
  await page.getByTestId('period-selector-dashboard').selectOption({ label: '2026-05 — Fechado' });
  await expect(page.getByText(/Lançamentos — 2026-05/)).toBeVisible();
  await expect(page).toHaveURL(/periodo=2026-05-01/);
  const marcador = await page.evaluate(
    () => (window as unknown as { __marcador: number }).__marcador,
  );
  expect(marcador).toBe(42);
});

test('M03 KPI card abre drawer com detalhe do pilar', async ({ page }) => {
  await login(page);
  await page.goto('/prestacao/mensal/');
  await page.getByTestId('kpi-pdi').click();
  const drawer = page.getByTestId('drawer');
  await expect(drawer).toBeVisible();
  await expect(page.getByTestId('drawer-pilar')).toBeVisible();
  await expect(page.getByTestId('drawer-pilar')).toContainText('PDI-PROJ-INI');
  await page.getByTestId('drawer-fechar').click();
  await expect(drawer).not.toBeVisible();
});

test('M04 destaques filtram por pilar', async ({ page }) => {
  await login(page);
  await page.goto('/prestacao/mensal/');
  const filtros = page.getByTestId('destaques-filtros');
  await Promise.all([
    page.waitForResponse((r) => r.url().includes('destaque_pilar=4')),
    filtros.getByRole('button', { name: 'AT', exact: true }).click(),
  ]);
  await expect(page.getByTestId('feed-destaques')).toContainText('renovações');
  await expect(page.getByTestId('feed-destaques')).toContainText('Arena QuIIN');
  await Promise.all([
    page.waitForResponse((r) => r.url().includes('destaque_pilar=1')),
    filtros.getByRole('button', { name: 'PDI', exact: true }).click(),
  ]);
  await expect(page.getByTestId('feed-destaques')).toContainText('Arena QuIIN');
  await expect(page.getByTestId('feed-destaques')).not.toContainText('renovações');
});

test('M05 dashboard responde em menos de 1000ms no servidor', async ({ page }) => {
  await login(page);
  await page.goto('/prestacao/mensal/');
  const tempos = await page.evaluate(() => {
    const nav = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
    return { servidor: nav.responseEnd - nav.requestStart };
  });
  expect(tempos.servidor).toBeLessThan(1000);
});

test('M06 header tem periodo, chips e toggle da barra', async ({ page }) => {
  await login(page);
  await page.goto('/prestacao/mensal/');
  const controles = page.getByTestId('dashboard-controls');
  await expect(controles).toBeVisible();
  await expect(controles.getByTestId('period-selector-dashboard')).toBeVisible();
  await expect(page.getByTestId('context-chips')).toContainText('Período:');
  const alternador = page.getByTestId('barra-toggle');
  await alternador.click();
  await expect(controles).toBeHidden();
  await alternador.click();
  await expect(controles).toBeVisible();
  await page.getByTestId('period-selector-dashboard').selectOption({ label: '2026-05 — Fechado' });
  await expect(page).toHaveURL(/periodo=2026-05-01/);
  await expect(page.getByTestId('context-chips')).toContainText('2026-05');
});

test('M07 toolbar: aprovar pendentes, relatório e imprimir', async ({ page }) => {
  await login(page);
  await page.goto('/prestacao/mensal/');
  const toolbar = page.getByRole('toolbar', { name: /ações do mês/i });
  await expect(toolbar.getByRole('link', { name: /aprovar \d+ pendente/i }))
    .toHaveAttribute('href', /\/aprovacao\/\d+\//);
  await expect(toolbar.getByRole('link', { name: /relatório mensal/i }))
    .toHaveAttribute('href', /\/relatorio\/mensal\/\d+\//);
  await expect(toolbar.getByRole('button', { name: /imprimir/i })).toBeVisible();
});

test('M08 impressão mostra cabeçalho do mês e esconde controles', async ({ page }) => {
  await login(page);
  await page.goto('/prestacao/mensal/');
  await page.emulateMedia({ media: 'print' });
  await expect(page.getByTestId('print-cabecalho')).toBeVisible();
  await expect(page.getByTestId('print-cabecalho')).toContainText('Dashboard Executivo');
  await expect(page.getByTestId('dashboard-controls')).toBeHidden();
});

test('M09 axe-core limpo no mensal', async ({ page }) => {
  await login(page);
  await page.goto('/prestacao/mensal/');
  await page.addStyleTag({ content: '*,*::before,*::after{animation:none!important;transition:none!important}' });
  const resultado = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
  const graves = resultado.violations.filter((v) => ['critical', 'serious'].includes(v.impact ?? ''));
  expect(graves, graves.map((v) => `${v.id}: ${v.help}`).join('\n')).toEqual([]);
});
