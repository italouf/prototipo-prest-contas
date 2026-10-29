import { expect, test, type Page } from '@playwright/test';

test.skip(!process.env.QUIIN_OPERATION_E2E, 'Use playwright.operation.config.ts (banco temporário).');

async function login(page: Page, focal = false) {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill(focal ? 'operation-focal' : 'overview-e2e');
  await page.getByLabel('Senha', { exact: true }).fill(focal ? 'operation-test-123' : 'overview-test-123');
  await page.getByRole('button', { name: /entrar/i }).click();
  await expect(page.getByTestId('dashboard-panel')).toBeVisible();
}

test('menu mantém logo e fonte; aprovados são carregados em páginas de dez', async ({ page }, info) => {
  await login(page);
  const sidebar = page.getByTestId('sidebar');
  const style = () => sidebar.evaluate(el => {
    const logo = el.querySelector('.sidebar-sig-logo')!.getBoundingClientRect();
    const link = el.querySelector('[data-nav-link]')!;
    return { width: logo.width, height: logo.height, font: getComputedStyle(link).font, sidebar: el.getBoundingClientRect().width };
  });
  const before = await style();
  await sidebar.getByRole('link', { name: /^Aprovação/ }).click();
  await expect(page.getByTestId('operation-board')).toBeVisible();
  expect(await style()).toEqual(before);
  await expect(page.getByTestId('operational-card')).toHaveCount(0);
  await page.getByRole('button', { name: 'Expandir', exact: true }).click();
  const approved = page.locator('.op-column[data-status="APROVADO"]');
  await expect(approved.getByTestId('operational-card')).toHaveCount(10);
  await expect(approved).toContainText('1–10 / 50');
  await approved.getByRole('link', { name: 'Próxima', exact: true }).click();
  await expect(approved).toContainText('11–20 / 50');
  await expect(approved.getByTestId('operational-card')).toHaveCount(10);
  expect(await approved.locator('.op-column-body').evaluate(el => getComputedStyle(el).overflowY)).toBe('auto');
  await approved.getByRole('link', { name: 'Ver detalhes' }).first().click();
  await expect(page.locator('#operation-dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('#operation-dialog')).not.toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: 'Aprovados (50)' }).click();
  await expect(approved).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath('operation-mobile.png'), fullPage: true });
});

test('ponto focal envia; gestor revisa e publica; dashboards e CSV exibem o resultado aprovado', async ({ page, browser }) => {
  await login(page, true);
  await page.getByTestId('sidebar').getByRole('link', { name: /^Lançamentos/ }).click();
  await expect(page.getByTestId('catalogo-operacional')).toBeVisible();
  await page.getByLabel('Base de análise', { exact: true }).selectOption('fisico');
  await page.getByRole('button', { name: 'Filtrar', exact: true }).click();
  const row = page.getByTestId('catalogo-operacional').locator('tbody tr').filter({ hasText: 'Pedidos de propriedade intelectual' });
  await row.getByRole('link', { name: 'Lançar / corrigir' }).click();
  await expect(page.getByRole('button', { name: 'Publicar ajuste direto' })).toHaveCount(0);
  await page.getByLabel(/Novo acumulado/).fill('6');
  await page.getByLabel(/Comentário/).fill('Evidências verificadas no mês');
  await page.getByRole('button', { name: 'Salvar rascunho' }).click();
  await expect(row).toContainText('Rascunho');
  await row.getByRole('link', { name: 'Lançar / corrigir' }).click();
  await page.getByRole('button', { name: 'Enviar para análise' }).click();
  await expect(row).toContainText('Enviado');

  const manager = await browser.newPage();
  await login(manager);
  await manager.getByTestId('sidebar').getByRole('link', { name: /^Aprovação/ }).click();
  const proposal = manager.getByTestId('operational-card').filter({ hasText: 'Pedidos de propriedade intelectual' });
  await proposal.getByRole('link', { name: 'Revisar proposta' }).click();
  await expect(manager.locator('#operation-dialog')).toContainText('Variação no resultado');
  await manager.getByRole('button', { name: 'Aprovar e publicar' }).click();
  await expect(manager.getByText('Resultado aprovado e publicado nos dashboards.', { exact: true })).toBeVisible();
  await page.reload();
  await expect(row).toContainText('Aprovado');
  await expect(row.locator('td').nth(2)).toHaveText('6');
  await manager.goto('/?base=fis');
  await expect(manager.getByTestId('dashboard-panel')).toContainText('Resultados homologados');
  await manager.close();
});
