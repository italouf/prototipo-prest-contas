import { expect, test, type Page } from '@playwright/test';

async function login(page: Page, username: string, password: string) {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill(username);
  await page.getByLabel('Senha').fill(password);
  await page.getByRole('button', { name: /entrar/i }).click();
}

async function logout(page: Page) {
  await page.getByRole('button', { name: /sair/i }).click();
  await expect(page.getByRole('heading', { name: /entrar no portal quiin/i })).toBeVisible();
}

test('fluxo completo rascunho -> enviado -> aprovado no kanban', async ({ page }) => {
  await login(page, 'focal_pdi', 'focal123');
  await page.goto('/lancamentos/2/1/');
  await page.locator('input[name="valor_3"]').fill('2');
  await page.getByRole('button', { name: /salvar rascunho/i }).click();
  await expect(page.locator('.messages .alert')).toContainText(/rascunho salvo/i);

  await page.getByRole('button', { name: /enviar para validação/i }).click();
  await expect(page.locator('.messages .alert')).toContainText(/enviados para validação/i);

  await logout(page);
  await login(page, 'erica', 'erica123');
  await page.goto('/aprovacao/2/');

  const colunaEnviado = page.getByTestId('kanban-coluna-ENVIADO');
  const cartao = colunaEnviado.locator('article', { hasText: 'Projetos iniciados' }).first();
  await expect(cartao).toBeVisible();
  await cartao.getByRole('button', { name: /^Aprovar$/ }).click();
  await expect(page.locator('.messages .alert')).toContainText(/aprovado/i);
  await expect(page.getByTestId('kanban-coluna-APROVADO')).toContainText('Projetos iniciados');
});

test('devolucao exige justificativa via modal', async ({ page }) => {
  await login(page, 'focal_pdi', 'focal123');
  await page.goto('/lancamentos/2/1/');
  await page.locator('input[name="valor_4"]').fill('9');
  await page.getByRole('button', { name: /enviar para validação/i }).click();
  await expect(page.locator('.messages .alert')).toContainText(/enviados para validação/i);

  await logout(page);
  await login(page, 'erica', 'erica123');
  await page.goto('/aprovacao/2/');
  const cartao = page.getByTestId('kanban-coluna-ENVIADO').locator('article', { hasText: 'Projetos em andamento' }).first();
  await cartao.getByRole('button', { name: /devolver/i }).click();
  await expect(page.getByTestId('modal-devolucao')).toBeVisible();
  await page.getByTestId('motivo-devolucao').fill('Ajustar a meta do mês.');
  await page.getByRole('button', { name: /confirmar devolução/i }).click();
  await expect(page.locator('.messages .alert')).toContainText(/devolvido/i);
  await expect(page.getByTestId('kanban-coluna-DEVOLVIDO')).toContainText('Ajustar a meta do mês.');
});

test('periodo fechado fica somente leitura', async ({ page }) => {
  await login(page, 'erica', 'erica123');
  await page.goto('/lancamentos/1/1/');
  await expect(page.getByTestId('periodo-bloqueado')).toBeVisible();
  await expect(page.getByRole('button', { name: /salvar rascunho/i })).toHaveCount(0);
  await expect(page.locator('input[name="valor_3"]')).toBeDisabled();
});

test('filtro por tipo de indicador esconde linhas', async ({ page }) => {
  await login(page, 'erica', 'erica123');
  await page.goto('/lancamentos/2/4/');
  await page.getByTestId('filtro-tipo-QTD').click();
  await expect(page.locator('[data-tipo="QTD"]').first()).toBeVisible();
  await expect(page.locator('[data-tipo="MON"]').first()).not.toBeVisible();
  await page.getByTestId('filtro-tipo-TODOS').click();
  await expect(page.locator('[data-tipo="MON"]').first()).toBeVisible();
});

test('preview do CSV valida arquivo bom e ruim', async ({ page }) => {
  await login(page, 'erica', 'erica123');
  await page.goto('/financeiro/importar/');
  await page.locator('input[type="file"]').setInputFiles('data/seed/financeiro_demo.csv');
  await expect(page.getByTestId('preview-valido')).toBeVisible();
  await expect(page.getByTestId('preview-valido')).toContainText('6 linha');

  await page.locator('input[type="file"]').setInputFiles('tests/e2e/fixtures/csv_invalido.csv');
  await expect(page.getByTestId('preview-invalido')).toBeVisible();
  await expect(page.getByTestId('preview-csv')).toContainText('Colunas: esperado 6');
  await expect(page.getByRole('button', { name: /importar/i })).toBeDisabled();
});
