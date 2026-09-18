import { expect, test, type Page } from '@playwright/test';

const EVID = 'docs/retrofit/evidencias/dashboard-anual/loop-10';

async function login(page: Page) {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill('erica');
  await page.getByLabel('Senha').fill('erica123');
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('evidência L10: shell full-width, scroll e sidebar recolhida', async ({ page }) => {
  await login(page);
  await page.goto('/?ano=todos&base=fin');
  await expect(page.getByTestId('app-header')).toBeVisible();
  await page.screenshot({ path: `${EVID}/shell-topo.png` });
  await page.evaluate(() => window.scrollTo(0, 1200));
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${EVID}/shell-rolado.png` });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.getByTestId('sidebar-collapse').click();
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${EVID}/shell-recolhida.png` });
});
