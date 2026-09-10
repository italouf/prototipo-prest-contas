import { expect, test, type Page } from '@playwright/test';

async function login(page: Page, username = 'erica', password = 'erica123') {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill(username);
  await page.getByLabel('Senha').fill(password);
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('navega entre 5 paginas pela sidebar com boost', async ({ page }) => {
  await login(page);
  await expect(page.getByTestId('sidebar')).toBeVisible();

  const rotas: Array<[RegExp, string, RegExp]> = [
    [/^Lançamentos/, '/lancamentos/2/1/', /lançamentos mensais/i],
    [/^Aprovação/, '/aprovacao/2/', /painel de aprovação/i],
    [/^Financeiro$/, '/financeiro/', /financeiro consolidado/i],
    [/^Relatório Mensal$/, '/relatorio/mensal/3/', /relatório mensal/i],
    [/^Auditoria$/, '/auditoria/', /auditoria/i],
  ];

  for (const [nome, caminho, titulo] of rotas) {
    await page.getByTestId('sidebar').getByRole('link', { name: nome }).click();
    await expect(page).toHaveURL(new RegExp(caminho.replace(/\//g, '\\/')));
    await expect(page.getByRole('heading', { name: titulo }).first()).toBeVisible();
    await expect(page).toHaveTitle(/Portal QuIIN/);
  }

  await page.getByTestId('sidebar').getByRole('link', { name: /^Dashboard/ }).click();
  await expect(page.getByRole('heading', { name: /dashboard executivo/i })).toBeVisible();
});

test('sidebar mobile abre, navega e fecha', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  const sidebar = page.getByTestId('sidebar');
  await expect(sidebar).not.toBeInViewport();
  await page.getByTestId('sidebar-toggle').click();
  await expect(sidebar).toBeInViewport();
  await sidebar.getByRole('link', { name: /Auditoria/ }).click();
  await expect(page.getByRole('heading', { name: /auditoria/i })).toBeVisible();
  await expect(sidebar).not.toBeInViewport();
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

test('papel ativo aparece no topbar', async ({ page }) => {
  await login(page);
  await expect(page.getByTestId('papel-badge')).toHaveText('Master');
});
