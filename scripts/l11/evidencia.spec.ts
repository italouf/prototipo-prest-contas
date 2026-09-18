import { expect, test, type Page } from '@playwright/test';

const EVID = 'docs/retrofit/evidencias/dashboard-anual/loop-11';

async function login(page: Page) {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill('erica');
  await page.getByLabel('Senha').fill('erica123');
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('evidência L11: header com botões e ícones na escala do mockup', async ({ page }) => {
  await login(page);
  await page.goto('/?ano=todos&base=fin');
  await expect(page.getByRole('toolbar')).toBeVisible();
  await page.getByTestId('app-header').screenshot({ path: `${EVID}/header-escala.png` });
});
