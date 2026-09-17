import { expect, test, type Page } from '@playwright/test';

const EVID = 'docs/retrofit/evidencias/dashboard-anual/loop-9';

async function login(page: Page) {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill('erica');
  await page.getByLabel('Senha').fill('erica123');
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('evidência L9: gráficos pintados, tabela e sidebar Gestão', async ({ page }) => {
  await login(page);
  await page.goto('/?ano=todos&base=fin');
  await expect(page.getByTestId('chart-fonte-ppi').locator('rect').first()).toBeVisible();
  await page.screenshot({ path: `${EVID}/graficos-corrigidos.png`, fullPage: true });
  await page.goto('/?ano=2026&base=fis');
  await expect(page.getByTestId('chart-consolidado')).toBeVisible();
  await page.getByTestId('pilares-table').scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${EVID}/tabela-2026-fis.png` });
  await page.getByTestId('sidebar').screenshot({ path: `${EVID}/sidebar-gestao.png` });
});
