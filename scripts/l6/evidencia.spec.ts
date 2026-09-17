import { expect, test, type Page } from '@playwright/test';

const EVID = 'docs/retrofit/evidencias/dashboard-anual/loop-6';

async function login(page: Page) {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill('erica');
  await page.getByLabel('Senha').fill('erica123');
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('evidência: tabela gerencial e modal do farol', async ({ page }) => {
  await login(page);
  await expect(page.getByTestId('pilares-table')).toBeVisible();
  await page.getByTestId('pilares-table').scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${EVID}/tabela-gerencial.png` });
  await page.getByTestId('farol-abrir').click();
  await expect(page.getByTestId('farol-modal')).toBeVisible();
  await page.screenshot({ path: `${EVID}/modal-farol.png` });
});
