import { expect, test, type Page } from '@playwright/test';

async function login(page: Page, username = 'erica', password = 'erica123') {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário', { exact: true }).fill(username);
  await page.getByLabel('Senha', { exact: true }).fill(password);
  await page.getByRole('button', { name: /entrar/i }).click();
  await expect(page.getByTestId('dashboard-panel')).toBeVisible();
}

async function openActions(page: Page) {
  await page.getByLabel('Mais ações', { exact: true }).click();
  return page.locator('.overview-more-actions');
}

test('topbar organiza ações à esquerda e usuário abaixo dos logos', async ({ page }) => {
  await login(page);
  const header = page.getByTestId('app-header');
  await expect(header.locator('[data-testid="papel-badge"], input[type="search"], a[title="Buscar"]')).toHaveCount(0);
  await expect(header.locator('select[name="acompanhamento"]')).toHaveCount(0);
  await expect(header.locator('.overview-user-name')).toBeVisible();
  await expect(header.locator('.overview-user-name')).not.toContainText(/master|coordenação|admin/i);
  await expect(header.getByRole('button', { name: 'Sair', exact: true })).toBeVisible();
  const logos = await header.locator('.brand-logos').boundingBox();
  const user = await header.locator('.overview-header-actions').boundingBox();
  expect(user!.y).toBeGreaterThanOrEqual(logos!.y + logos!.height);
  const actions = await openActions(page);
  await expect(actions.getByRole('link', { name: 'Importar dados' })).toBeVisible();
  await expect(actions.getByRole('button', { name: 'Editar dados' })).toBeVisible();
  await expect(actions.getByRole('link', { name: 'Baixar dados (CSV)' })).toBeVisible();
  await expect(actions.getByText('Restaurar padrão')).toHaveCount(0);
  await expect(page.locator('.overview-page-actions')).toHaveCount(0);
});

test('MM/AAAA atualiza filtros via HTMX e preserva a versão dos dados', async ({ page }) => {
  await login(page);
  const acompanhamento = await page.locator('.overview-filters input[name="acompanhamento"]').inputValue();
  await page.getByLabel('Mês/ano inicial', { exact: true }).fill('02/2025');
  await page.getByLabel('Mês/ano inicial', { exact: true }).press('Tab');
  await expect(page).toHaveURL(/mes_inicial=02%2F2025/);
  await expect(page.getByLabel('Mês/ano inicial', { exact: true })).toHaveValue('02/2025');
  await expect(page.getByTestId('context-chips')).toContainText('fev/2025');
  await expect(page.getByTestId('print-cabecalho')).toContainText('fev/2025');
  const actions = await openActions(page);
  const download = actions.getByRole('link', { name: 'Baixar dados (CSV)' });
  await expect(download).toHaveAttribute('href', new RegExp(`acompanhamento=${acompanhamento}`));
  await expect(download).toHaveAttribute('href', /mes_inicial=2025-02/);
  await page.getByLabel('Mais ações', { exact: true }).click();
  await page.getByTestId('remover-filtros').click();
  await expect(page.locator('.overview-filters input[name="acompanhamento"]')).toHaveValue(acompanhamento);
  await expect(page.getByLabel('Mês/ano inicial', { exact: true })).toHaveValue('');
});

test('edição só envia dados depois de confirmar, permitindo voltar e usar Escape', async ({ page }) => {
  await login(page);
  await openActions(page);
  await page.getByTestId('btn-editar-dados').click();
  const editor = page.getByTestId('editor-dados');
  const firstValue = editor.locator('input[type="number"]').first();
  await firstValue.fill('123');
  const submitted: string[] = [];
  await page.route('**/plano-anual/aplicar/', async route => {
    submitted.push(route.request().postData() || '');
    await route.fulfill({ status: 200, contentType: 'text/html', body: '<p>Envio confirmado</p>' });
  });
  await editor.getByRole('button', { name: 'Salvar alterações' }).click();
  const dialog = page.getByRole('dialog', { name: 'Confirmar alterações' });
  await expect(dialog).toBeVisible();
  expect(submitted).toHaveLength(0);
  await dialog.getByRole('button', { name: 'Continuar editando' }).click();
  await expect(dialog).toBeHidden();
  await expect(firstValue).toHaveValue('123');
  await editor.getByRole('button', { name: 'Salvar alterações' }).click();
  await dialog.press('Escape');
  await expect(dialog).toBeHidden();
  expect(submitted).toHaveLength(0);
  await editor.getByRole('button', { name: 'Salvar alterações' }).click();
  await dialog.getByRole('button', { name: 'Confirmar e salvar' }).click();
  await expect(page.getByText('Envio confirmado')).toBeVisible();
  expect(submitted).toHaveLength(1);
  expect(submitted[0]).toContain('123');
});

test('aviso aparece no conteúdo sem sobrepor a topbar', async ({ page }) => {
  await login(page);
  await page.evaluate(() => (window as any).quiinToast('Dados atualizados.', 'success'));
  const message = page.getByText('Dados atualizados.', { exact: true });
  await expect(message).toBeVisible();
  const header = await page.getByTestId('app-header').boundingBox();
  const box = await message.boundingBox();
  expect(box!.y).toBeGreaterThanOrEqual(header!.y + header!.height);
  await expect(message).toHaveCSS('position', 'static');
});

test('impressão inclui tabelas recolhidas e restaura seu estado depois', async ({ page }, testInfo) => {
  await login(page);
  for (const base of ['fin', 'fis']) {
    await page.goto(`/?base=${base}`);
    const panels = page.locator('.overview-accordion');
    await expect(panels.first()).not.toHaveAttribute('open', '');
    await page.emulateMedia({ media: 'print' });
    await page.evaluate(() => window.dispatchEvent(new Event('beforeprint')));
    await expect(page.getByTestId('app-header')).toBeHidden();
    await expect(page.getByTestId('print-cabecalho')).toBeVisible();
    await expect(page.getByTestId('editor-dados')).toBeHidden();
    for (const panel of await panels.all()) {
      await expect(panel.locator('.overview-accordion-body')).toBeVisible();
    }
    const overflow = await page.locator('.overview-dashboard table').evaluateAll(tables => tables.filter(table => {
      const box = table.getBoundingClientRect();
      return box.right > document.documentElement.clientWidth + 1;
    }).length);
    expect(overflow).toBe(0);
    await page.screenshot({ path: testInfo.outputPath(`impressao-${base}.png`), fullPage: true });
    await page.pdf({ path: testInfo.outputPath(`dashboard-${base}.pdf`), preferCSSPageSize: true, printBackground: true });
    await page.emulateMedia({ media: 'screen' });
    await page.evaluate(() => window.dispatchEvent(new Event('afterprint')));
    await expect(panels.first()).not.toHaveAttribute('open', '');
  }
});

test('topbar mantém nome, menu e campos disponíveis em telas menores', async ({ page }, testInfo) => {
  await login(page);
  for (const width of [1440, 1100, 768, 375, 320]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.locator('.overview-user-name')).toBeVisible();
    await expect(page.getByLabel('Mês/ano inicial', { exact: true })).toBeVisible();
    const actions = await openActions(page);
    await expect(actions.getByRole('link', { name: 'Baixar dados (CSV)' })).toBeVisible();
    const box = await actions.locator('div').boundingBox();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(width);
    await page.getByTestId('app-header').screenshot({ path: testInfo.outputPath(`topbar-${width}.png`) });
    await page.getByLabel('Mais ações', { exact: true }).click();
  }
});

test('pilar preserva datas compactas, baixa seu escopo e imprime tabelas completas', async ({ page }, testInfo) => {
  await login(page);
  const pdi = page.locator('.sidebar a[data-nav-link][href^="/pilar/"]').filter({ hasText: /PDI|PD&I/ }).first();
  const href = await pdi.getAttribute('href');
  expect(href).toBeTruthy();
  await page.goto(`${href}?base=fis&mes_inicial=2025-01&mes_final=2025-12`);
  await expect(page.getByLabel('Mês/ano inicial', { exact: true })).toHaveValue('01/2025');
  await expect(page.getByLabel('Mês/ano final', { exact: true })).toHaveValue('12/2025');
  const actions = await openActions(page);
  await expect(actions.getByRole('link', { name: 'Baixar dados (CSV)' })).toHaveAttribute('href', /pilar=\d+/);
  await actions.getByRole('button', { name: 'Editar dados' }).click();
  await expect(page.getByTestId('editor-dados')).toBeVisible();
  for (const base of ['fin', 'fis']) {
    await page.goto(`${href}?base=${base}`);
    await page.emulateMedia({ media: 'print' });
    await page.evaluate(() => window.dispatchEvent(new Event('beforeprint')));
    await expect(page.getByTestId('print-cabecalho')).toBeVisible();
    const overflow = await page.locator('.overview-dashboard table').evaluateAll(tables => tables.filter(table => {
      return table.getBoundingClientRect().right > document.documentElement.clientWidth + 1;
    }).length);
    expect(overflow).toBe(0);
    await page.pdf({ path: testInfo.outputPath(`pilar-${base}.pdf`), preferCSSPageSize: true, printBackground: true });
    await page.emulateMedia({ media: 'screen' });
  }
});
