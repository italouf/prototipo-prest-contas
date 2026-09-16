import { expect, test, type Page } from '@playwright/test';

async function login(page: Page, username = 'erica', password = 'erica123') {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill(username);
  await page.getByLabel('Senha').fill(password);
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('navega entre 3 paginas pela navbar com boost', async ({ page }) => {
  await login(page);
  const navbar = page.getByTestId('navbar');
  await expect(navbar).toBeVisible();
  // 1. Geral (link direto)
  await navbar.getByRole('link', { name: /^Geral/ }).click();
  await expect(page.getByRole('heading', { name: /dashboard executivo/i })).toBeVisible();
  // 2. Pilares (dropdown) — primeiro pilar, sem fixar PK
  await navbar.getByRole('button', { name: /pilares/i }).click();
  await navbar.getByRole('menuitem').first().click();
  await expect(page).toHaveURL(/\/pilar\/\d+\//);
  await expect(page.getByTestId('breadcrumbs')).toBeVisible();
  // 3. Sistema -> Auditoria (dropdown)
  await navbar.getByRole('button', { name: /^sistema/i }).click();
  await navbar.getByRole('menuitem', { name: /auditoria/i }).click();
  await expect(page.getByRole('heading', { name: /auditoria/i })).toBeVisible();
});

test('navega 5 abas principais com boost', async ({ page }) => {
  await login(page);
  const navbar = page.getByTestId('navbar');
  await expect(navbar).toBeVisible();
  // 1. Geral (link direto)
  await navbar.getByRole('link', { name: /^Geral/ }).click();
  await expect(page).toHaveURL(/\/?(\?.*)?$/);
  await expect(page.getByTestId('page-dashboard').getByRole('heading', { name: /dashboard executivo/i })).toBeVisible();
  // 2. Pilares (dropdown) — primeiro pilar, sem PK hardcoded
  await navbar.getByRole('button', { name: /pilares/i }).click();
  await navbar.getByRole('menuitem').first().click();
  await expect(page).toHaveURL(/\/pilar\/\d+\//);
  await expect(page.getByTestId('page-pilar')).toBeVisible();
  await expect(page.getByTestId('page-pilar').getByRole('heading').first()).toBeVisible();
  await expect(page.getByTestId('breadcrumbs')).toBeVisible();
  // 3. Talentos (link direto)
  await navbar.getByRole('link', { name: /talentos/i }).click();
  await expect(page).toHaveURL(/\/talentos\/organograma\//);
  await expect(page.getByTestId('page-talentos').getByRole('heading', { name: /organograma/i })).toBeVisible();
  // 4. Gestão de Associados (link direto)
  await navbar.getByRole('link', { name: /gestão de associados/i }).click();
  await expect(page).toHaveURL(/\/crm-at\/funil\//);
  await expect(page.getByTestId('page-funil').getByRole('heading', { name: /funil at/i })).toBeVisible();
  // 5. Sistema -> Auditoria (dropdown)
  await navbar.getByRole('button', { name: /^sistema/i }).click();
  await navbar.getByRole('menuitem', { name: /auditoria/i }).click();
  await expect(page).toHaveURL(/\/auditoria\//);
  await expect(page.getByTestId('page-auditoria').getByRole('heading', { name: /auditoria/i })).toBeVisible();
});

test('navbar mobile abre, navega e fecha', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  await page.getByTestId('navbar-toggle').click();
  await page.getByTestId('navbar').getByRole('link', { name: /Auditoria/ }).click();
  await expect(page.getByRole('heading', { name: /auditoria/i })).toBeVisible();
});

test('breadcrumbs refletem a hierarquia', async ({ page }) => {
  await login(page);
  await page.goto('/pilar/1/');
  const breadcrumbs = page.getByTestId('breadcrumbs');
  await expect(breadcrumbs).toBeVisible();
  await expect(breadcrumbs).toContainText('Início');
  await expect(breadcrumbs.locator('[aria-current="page"]')).toHaveText('PDI / FCCT');
});

test('busca global encontra indicador visivel', async ({ page }) => {
  await login(page);
  await Promise.all([
    page.waitForResponse((r) => r.url().includes('/busca/') && r.url().includes('q=artigos')),
    page.getByTestId('busca-global').fill('artigos'),
  ]);
  await expect(page.getByTestId('busca-lista')).toBeVisible();
  await expect(page.getByTestId('busca-lista')).toContainText('Artigos publicados');
});

test('seletor de periodo muda o dashboard', async ({ page }) => {
  await login(page);
  await page.getByTestId('period-selector').selectOption({ label: '2026-05 — Fechado' });
  await expect(page).toHaveURL(/periodo=2026-05-01/);
  await expect(page.getByText(/Lançamentos — 2026-05/)).toBeVisible();
});

test('papel ativo aparece na navbar', async ({ page }) => {
  await login(page);
  await expect(page.getByTestId('papel-badge')).toHaveText('Master');
});

test('toggle operacional|financeiro troca secoes sem reload', async ({ page }) => {
  await login(page);
  await page.goto('/?escopo=operacional');
  await expect(page.getByTestId('escopo-operacional')).toBeVisible();
  await page.getByTestId('scope-financeiro').click();
  await expect(page).toHaveURL(/escopo=financeiro/);
  await expect(page.getByTestId('escopo-financeiro')).toBeVisible();
  await expect(page.getByTestId('escopo-operacional')).toBeHidden();
  await expect(page.getByTestId('scope-financeiro')).toHaveAttribute('aria-current', 'page');
  await page.getByTestId('scope-operacional').click();
  await expect(page.getByTestId('escopo-operacional')).toBeVisible();
  await expect(page.getByTestId('scope-operacional')).toHaveAttribute('aria-current', 'page');
});

test('toggle fora do dashboard navega para dashboard com escopo', async ({ page }) => {
  await login(page);
  await page.goto('/auditoria/');
  await expect(page.getByRole('heading', { name: /auditoria/i })).toBeVisible();
  await page.getByTestId('scope-financeiro').click();
  await expect(page).toHaveURL(/escopo=financeiro/);
  await expect(page.getByTestId('page-dashboard')).toBeVisible();
});
