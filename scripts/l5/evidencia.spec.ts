import { expect, test, type Page } from '@playwright/test';

const EVID = 'docs/retrofit/evidencias/dashboard-anual/loop-5';

async function login(page: Page) {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill('erica');
  await page.getByLabel('Senha').fill('erica123');
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('evidência: cards e gráficos no padrão e em 2026/físico', async ({ page }) => {
  await login(page);
  await expect(page.getByTestId('kpi-ppi')).toBeVisible();
  await page.screenshot({ path: `${EVID}/cards-graficos-padrao.png`, fullPage: true });
  await page.goto('/?ano=2026&base=fis');
  await expect(page.getByTestId('chart-consolidado')).toBeVisible();
  await page.screenshot({ path: `${EVID}/cards-graficos-2026-fis.png`, fullPage: true });
});
