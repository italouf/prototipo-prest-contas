import { expect, test, type Page } from '@playwright/test';

const EVID = 'docs/retrofit/evidencias/dashboard-anual/loop-3';

async function login(page: Page) {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill('erica');
  await page.getByLabel('Senha').fill('erica123');
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('evidência: header global + painel padrão + estado 2026/físico', async ({ page }) => {
  await login(page);
  await expect(page.getByTestId('app-header')).toBeVisible();
  await page.screenshot({ path: `${EVID}/header-painel-padrao.png`, fullPage: true });
  await page.getByTestId('year-select').selectOption('2026');
  await page.getByTestId('base-toggle').getByRole('link', { name: 'Físico' }).click();
  await expect(page.getByTestId('context-chips')).toContainText('Ano 3: 2026');
  await page.screenshot({ path: `${EVID}/header-painel-2026-fis.png`, fullPage: true });
});
