import { expect, test, type Page } from '@playwright/test';

const EVID = 'docs/retrofit/evidencias/dashboard-anual/loop-13';

async function login(page: Page) {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill('erica');
  await page.getByLabel('Senha').fill('erica123');
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('evidência L13: painel do PDI e da AT', async ({ page }) => {
  await login(page);
  await page.goto('/pilar/1/');
  await expect(page.getByTestId('painel-pilar')).toBeVisible();
  await page.screenshot({ path: `${EVID}/pilar-pdi.png`, fullPage: true });
  await page.goto('/pilar/4/?ano=2026&base=fis');
  await expect(page.getByTestId('painel-pilar')).toContainText('Captado');
  await page.screenshot({ path: `${EVID}/pilar-at-2026-fis.png`, fullPage: true });
});
