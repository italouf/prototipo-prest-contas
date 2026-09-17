import { expect, test, type Page } from '@playwright/test';

const EVID = 'docs/retrofit/evidencias/dashboard-anual/loop-7';

async function login(page: Page) {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill('erica');
  await page.getByLabel('Senha').fill('erica123');
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('evidência: footer institucional e modo de edição', async ({ page }) => {
  await login(page);
  await expect(page.getByTestId('app-footer')).toBeVisible();
  await page.getByTestId('app-footer').scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${EVID}/footer.png` });
  await page.goto('/?ano=todos&base=fin');
  await page.getByRole('button', { name: /editar dados/i }).click();
  await expect(page.getByTestId('editor-dados')).toBeVisible();
  await page.getByTestId('editor-dados').scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${EVID}/editor.png` });
});
