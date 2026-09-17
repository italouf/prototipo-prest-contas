import { expect, test, type Page } from '@playwright/test';

const EVID = 'docs/retrofit/evidencias/dashboard-anual/loop-8';

async function login(page: Page) {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill('erica');
  await page.getByLabel('Senha').fill('erica123');
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('evidência final: folha de impressão A4 e viewport móvel', async ({ page }) => {
  await login(page);
  await page.goto('/?ano=2026&base=fis');
  await page.emulateMedia({ media: 'print' });
  await expect(page.getByTestId('print-cabecalho')).toBeVisible();
  await page.screenshot({ path: `${EVID}/impressao-a4.png`, fullPage: true });
  await page.emulateMedia({ media: 'screen' });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/?ano=todos&base=fin');
  await expect(page.getByTestId('kpi-ppi')).toBeVisible();
  await page.screenshot({ path: `${EVID}/mobile-390.png`, fullPage: true });
});
