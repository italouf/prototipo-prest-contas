import { test, expect, type Page } from '@playwright/test';

/**
 * E2E do Dashboard Executivo, Admin e Auditoria (Portal QuIIN).
 * Pré-requisito: banco criado com `python manage.py seed_demo`.
 */

async function login(page: Page, username: string, password: string) {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill(username);
  await page.getByLabel('Senha').fill(password);
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('erica acessa o admin do Django', async ({ page }) => {
  await login(page, 'erica', 'erica123');
  const resposta = await page.goto('/admin/');
  expect(resposta?.status()).toBe(200);
  await expect(page.getByRole('heading', { name: /site administration/i })).toBeVisible();
});

test('logout via botão encerra a sessão', async ({ page }) => {
  await login(page, 'erica', 'erica123');
  await page.getByRole('button', { name: /sair/i }).click();
  await expect(page.getByRole('heading', { name: /entrar no portal quiin/i })).toBeVisible();
  await page.goto('/');
  await expect(page).toHaveURL(/\/accounts\/login\//);
});

test('dashboard executivo exibe gráficos e escala de valores', async ({ page }) => {
  await login(page, 'erica', 'erica123');
  await expect(page.getByRole('heading', { name: /dashboard executivo/i })).toBeVisible();
  await expect(page.getByText('Evolução financeira mensal')).toBeVisible();
  await expect(page.getByText('Captação × execução por pilar')).toBeVisible();
  await expect(page.locator('.kpi-strip .kpi')).toHaveCount(8);
  await expect(page.getByText(/R\$ .* mi|R\$ \d+ mil/).first()).toBeVisible();
  await expect(page.locator('.segbar')).toBeVisible();
});

test('dashboard executivo é responsivo no viewport móvel', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page, 'erica', 'erica123');
  const scroll = await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);
  expect(scroll).toBeTruthy();
});

test('auditoria filtra por ação e pagina resultados', async ({ page }) => {
  await login(page, 'auditor', 'auditor123');
  await page.goto('/auditoria/');
  await expect(page.getByRole('heading', { name: /auditoria/i })).toBeVisible();
  await page.locator('select[name="acao"]').selectOption('LOGIN');
  await page.getByRole('button', { name: /filtrar/i }).click();
  await expect(page.locator('table tbody .badge-action').filter({ hasText: /login realizado/i }).first()).toBeVisible();
  const total = await page.locator('.panel p.muted.small strong').first().textContent();
  expect(Number(total)).toBeGreaterThan(0);
});

test('detalhes expansíveis aparecem na auditoria', async ({ page }) => {
  await login(page, 'erica', 'erica123');
  await page.goto('/auditoria/');
  const details = page.locator('details.audit-detail').first();
  if ((await details.count()) === 0) {
    test.skip(true, 'sem detalhes expansíveis no seed');
    return;
  }
  await expect(details).not.toHaveAttribute('open', '');
  await details.locator('summary').click();
  await expect(details).toHaveAttribute('open', '');
});
