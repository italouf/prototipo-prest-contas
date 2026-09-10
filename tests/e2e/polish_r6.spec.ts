import { expect, test, type Page } from '@playwright/test';

async function login(page: Page, username = 'erica', password = 'erica123') {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill(username);
  await page.getByLabel('Senha').fill(password);
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('skeleton aparece durante swap HTMX do dashboard', async ({ page }) => {
  await login(page);
  await page.route('**/?periodo=2026-05-01', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 800));
    await route.continue();
  });
  const seletores = page.getByTestId('period-selector-dashboard');
  await seletores.selectOption({ label: '2026-05 — Fechado' });
  await expect(page.locator('#skeleton-global')).toHaveClass(/htmx-request/);
  await expect(page.getByText(/Lançamentos — 2026-05/)).toBeVisible();
  await expect(page.locator('#skeleton-global')).not.toHaveClass(/htmx-request/);
});

test('cards usam animacao de entrada e respeitam reduced motion', async ({ page }) => {
  await login(page);
  const animacao = await page
    .getByTestId('kpi-pdi')
    .evaluate((el) => getComputedStyle(el).animationName);
  expect(animacao).toBe('quiin-entrada');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.reload();
  const semAnimacao = await page
    .getByTestId('kpi-pdi')
    .evaluate((el) => getComputedStyle(el).animationName);
  expect(semAnimacao).toBe('none');
});

test('view transitions habilitadas e foco visivel por teclado', async ({ page }) => {
  await login(page);
  const globalViewTransitions = await page.evaluate(
    () => (window as unknown as { htmx: { config: { globalViewTransitions: boolean } } }).htmx.config.globalViewTransitions,
  );
  expect(globalViewTransitions).toBe(true);

  await page.keyboard.press('Tab');
  const primeiroFoco = await page.evaluate(() => document.activeElement?.textContent?.trim());
  expect(primeiroFoco).toContain('Pular para o conteúdo');

  await page.keyboard.press('Tab');
  const segundoFoco = await page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null;
    return el?.getAttribute('aria-label') || el?.textContent?.trim() || '';
  });
  expect(segundoFoco.length).toBeGreaterThan(0);
});
