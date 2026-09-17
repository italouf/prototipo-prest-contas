import { expect, test, type Page } from '@playwright/test';

const EVID = 'docs/retrofit/evidencias/dashboard-anual/loop-4';

async function login(page: Page) {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill('erica');
  await page.getByLabel('Senha').fill('erica123');
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('evidência: sidebar reagrupada + semestral + pilar com contexto', async ({ page }) => {
  await login(page);
  await expect(page.getByTestId('sidebar')).toBeVisible();
  await page.screenshot({ path: `${EVID}/sidebar-painel.png` });
  await page.goto('/prestacao/semestral/');
  await expect(page.getByTestId('page-semestral')).toBeVisible();
  await page.screenshot({ path: `${EVID}/semestral.png`, fullPage: true });
  await page.goto('/pilar/1/?ano=2026&base=fis');
  await expect(page.getByTestId('contexto-anual')).toBeVisible();
  await page.screenshot({ path: `${EVID}/pilar-contexto-anual.png`, fullPage: true });
});
