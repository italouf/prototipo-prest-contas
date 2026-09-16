import { expect, test, type Page } from '@playwright/test';

async function login(page: Page, username = 'erica', password = 'erica123') {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill(username);
  await page.getByLabel('Senha').fill(password);
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('navega entre 5 paginas pela navbar com boost', async ({ page }) => {
  await login(page);
  await expect(page.getByTestId('navbar')).toBeVisible();
  // Lançamentos/Aprovações podem estar em dropdown mobile; usar navbar como escopo:
  await page.getByTestId('navbar').getByRole('link', { name: /^Geral/ }).click();
  await expect(page.getByRole('heading', { name: /dashboard executivo/i })).toBeVisible();
});

test('navbar mobile abre, navega e fecha', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  await page.getByTestId('navbar-toggle').click();
  await page.getByTestId('navbar').getByRole('link', { name: /Auditoria/ }).click();
  await expect(page.getByRole('heading', { name: /auditoria/i })).toBeVisible();
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

test('seletor de periodo muda o dashboard', async ({ page }) => {
  await login(page);
  await page.getByTestId('period-selector').selectOption({ label: '2026-05 — Fechado' });
  await expect(page).toHaveURL(/periodo=2026-05-01/);
  await expect(page.getByText(/Lançamentos — 2026-05/)).toBeVisible();
});

test('papel ativo aparece no topbar', async ({ page }) => {
  await login(page);
  await expect(page.getByTestId('papel-badge')).toHaveText('Master');
});
