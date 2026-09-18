import { expect, test, type Page } from '@playwright/test';

const EVID = 'docs/retrofit/evidencias/dashboard-anual/loop-15';

async function login(page: Page) {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill('erica');
  await page.getByLabel('Senha').fill('erica123');
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('evidência L15: toolbar e editor escopados do PDI', async ({ page }) => {
  await login(page);
  await page.goto('/pilar/1/?ano=todos&base=fin');
  await expect(page.getByRole('toolbar')).toBeVisible();
  await page.getByRole('button', { name: /editar dados/i }).click();
  await expect(page.getByTestId('editor-dados')).toBeVisible();
  await page.getByTestId('editor-dados').scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${EVID}/editor-pdi.png` });
});
