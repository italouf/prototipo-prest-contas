import { expect, test, type Page } from '@playwright/test';

async function login(page: Page, username = 'erica', password = 'erica123') {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill(username);
  await page.getByLabel('Senha').fill(password);
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('exibe 6 KPIs dos pilares e cards financeiros', async ({ page }) => {
  await login(page);
  await expect(page.locator('[data-kpi-card]')).toHaveCount(6);
  await expect(page.getByTestId('kpi-pdi')).toBeVisible();
  await expect(page.getByTestId('kpi-at')).toBeVisible();
  await expect(page.getByTestId('heatmap')).toBeVisible();
  await expect(page.getByTestId('avisos')).toBeVisible();
});

test('filtro de periodo atualiza widgets via HTMX sem reload', async ({ page }) => {
  await login(page);
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

test('KPI card abre drawer com detalhe do pilar', async ({ page }) => {
  await login(page);
  await page.getByTestId('kpi-pdi').click();
  const drawer = page.getByTestId('drawer');
  await expect(drawer).toBeVisible();
  await expect(page.getByTestId('drawer-pilar')).toBeVisible();
  await expect(page.getByTestId('drawer-pilar')).toContainText('PDI-PROJ-INI');
  await page.getByTestId('drawer-fechar').click();
  await expect(drawer).not.toBeVisible();
});

test('destaques filtram por pilar', async ({ page }) => {
  await login(page);
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

test('dashboard responde em menos de 1000ms no servidor', async ({ page }) => {
  await login(page);
  const tempos = await page.evaluate(() => {
    const nav = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
    return { servidor: nav.responseEnd - nav.requestStart };
  });
  expect(tempos.servidor).toBeLessThan(1000);
});
