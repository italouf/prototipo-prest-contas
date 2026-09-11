import { expect, test, type Page } from '@playwright/test';

async function login(page: Page, username = 'erica', password = 'erica123') {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill(username);
  await page.getByLabel('Senha').fill(password);
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('funil mostra pipeline, meta de CNPJs e renovacoes separadas', async ({ page }) => {
  await login(page);
  await page.goto('/crm-at/funil/');
  await expect(page.getByTestId('funil-kpis')).toContainText('Pipeline em aberto');
  await expect(page.getByTestId('funil-kpis')).toContainText('Meta CNPJs novos');
  const colunas = ['PROSPECCAO', 'QUALIFICACAO', 'REUNIAO_TECNICA', 'NEGOCIACAO', 'FECHAMENTO'];
  for (const fase of colunas) {
    await expect(page.getByTestId(`funil-coluna-${fase}`)).toBeVisible();
  }
  await expect(page.locator('[data-testid^="oportunidade-"]').first()).toBeVisible();
  await expect(page.getByTestId('kanban-renovacoes')).toBeVisible();
  await expect(page.getByTestId('page-funil')).toContainText('RN-007');
});

test('organograma filtra por pilar via HTMX sem reload', async ({ page }) => {
  await login(page);
  await page.goto('/talentos/organograma/');
  await page.evaluate(() => {
    (window as unknown as { __marcador: number }).__marcador = 7;
  });
  await Promise.all([
    page.waitForResponse((r) => r.url().includes('/talentos/organograma/') && r.url().includes('pilar=AT')),
    page.locator('#filtro-pilar').selectOption('AT'),
  ]);
  await expect(page.getByTestId('talentos-lista')).toContainText('Ana Demonstração');
  await expect(page.getByTestId('talentos-lista')).not.toContainText('Bruno Exemplo');
  const marcador = await page.evaluate(
    () => (window as unknown as { __marcador: number }).__marcador,
  );
  expect(marcador).toBe(7);
});

test('busca por skill esconde cards sem correspondencia', async ({ page }) => {
  await login(page);
  await page.goto('/talentos/organograma/');
  await expect(page.getByTestId('talento-card')).toHaveCount(3);
  const ana = page.getByTestId('talento-card').first();
  await expect(ana).toContainText('h livres');

  await page.getByTestId('busca-talento').fill('óptica quântica');
  await expect(ana).not.toBeVisible();
  await expect(page.locator('[data-testid="talento-card"]:visible')).toHaveCount(1);

  await page.getByTestId('busca-talento').fill('python');
  await expect(page.locator('[data-testid="talento-card"]:visible')).toHaveCount(1);
  await expect(page.locator('[data-testid="talento-card"]:visible')).toContainText('Ana Demonstração');
});
