import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

async function login(page: Page) {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill('erica');
  await page.getByLabel('Senha').fill('erica123');
  await page.getByRole('button', { name: /entrar/i }).click();
}

test.describe('design system (R0)', () => {
  test('pagina dev renderiza primitivos', async ({ page }) => {
    await login(page);
    await page.goto('/dev/design-system/');
    await expect(page.getByTestId('page-design-system')).toBeVisible();
    await expect(page.getByTestId('btn-primary')).toBeVisible();
    await expect(page.getByTestId('btn-ghost')).toBeVisible();
    await expect(page.getByTestId('badge-aprovado')).toBeVisible();
  });

  test('dark mode alterna e persiste', async ({ page }) => {
    await login(page);
    await page.goto('/dev/design-system/');
    const html = page.locator('html');
    await expect(html).not.toHaveClass(/dark/);
    await page.getByTestId('dark-toggle').click();
    await expect(html).toHaveClass(/dark/);
    await page.reload();
    await expect(html).toHaveClass(/dark/);
    await page.getByTestId('dark-toggle').click();
    await expect(html).not.toHaveClass(/dark/);
  });

  test('sem violacoes serias de acessibilidade', async ({ page }) => {
    await login(page);
    await page.goto('/dev/design-system/');
    const resultado = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
    const graves = resultado.violations.filter((v) => ['critical', 'serious'].includes(v.impact ?? ''));
    expect(graves, JSON.stringify(graves, null, 2)).toEqual([]);
  });
});
