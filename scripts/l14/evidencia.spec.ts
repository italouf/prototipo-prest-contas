import { expect, test, type Page } from '@playwright/test';

const EVID = 'docs/retrofit/evidencias/dashboard-anual/loop-14';

async function login(page: Page) {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill('erica');
  await page.getByLabel('Senha').fill('erica123');
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('evidência L14: AT em Pilares, Funil AT em Gestão', async ({ page }) => {
  await login(page);
  await page.goto('/?ano=todos&base=fin');
  await expect(page.locator('#grp-pilares').getByRole('link', { name: /Associação Tecnológica/ })).toBeVisible();
  await page.getByTestId('sidebar').screenshot({ path: `${EVID}/sidebar-at-pilares.png` });
});
