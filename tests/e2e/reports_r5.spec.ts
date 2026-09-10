import { expect, test, type Page } from '@playwright/test';

async function login(page: Page, username = 'erica', password = 'erica123') {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill(username);
  await page.getByLabel('Senha').fill(password);
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('relatorio A4 com capa, secoes, assinatura e graficos', async ({ page }) => {
  await login(page);
  await page.goto('/relatorio/mensal/2/');
  await expect(page.getByTestId('report-capa')).toBeVisible();
  await expect(page.getByTestId('report-assinatura')).toHaveText(/^[0-9a-f]{16}$/);
  await expect(page.getByTestId('report-secao-PDI')).toBeVisible();
  await expect(page.getByTestId('report-financeiro')).toBeVisible();
  await expect(page.getByTestId('report-grafico-captacao')).toBeVisible();

  await page.emulateMedia({ media: 'print' });
  await expect(page.getByTestId('topbar')).toBeHidden();
  await expect(page.getByTestId('sidebar')).toBeHidden();
  await expect(page.getByTestId('report-capa')).toBeVisible();
  await expect(page.getByRole('button', { name: /imprimir/i })).toBeHidden();
});

test('auditoria filtra, mostra timeline e paginacao', async ({ page }) => {
  await login(page, 'auditor', 'auditor123');
  await page.goto('/auditoria/');
  await expect(page.getByTestId('timeline-auditoria')).toBeVisible();
  await expect(page.getByTestId('evento-auditoria').first()).toBeVisible();

  await page.locator('select[name="acao"]').selectOption('LOGIN');
  await page.getByRole('button', { name: /filtrar/i }).click();
  await expect(page.locator('table tbody [data-testid="badge-acao"]').filter({ hasText: /login realizado/i }).first()).toBeVisible();
  const total = await page.locator('[data-testid="auditoria-total"] strong').first().textContent();
  expect(Number(total)).toBeGreaterThan(0);

  await page.getByRole('link', { name: /próxima/i }).click();
  await expect(page.getByTestId('paginacao-auditoria')).toContainText('Página 2');
});
