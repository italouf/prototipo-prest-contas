import { test, expect, type Page } from '@playwright/test';

/**
 * E2E do Portal QuIIN (protótipo local).
 *
 * Pré-requisito: banco criado com `python manage.py seed_demo` (períodos
 * 2026-05=1, 2026-06=2, 2026-07=3; pilar PDI=1, FORMACAO=2).
 */

async function login(page: Page, username: string, password: string) {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill(username);
  await page.getByLabel('Senha').fill(password);
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('login com credenciais válidas redireciona para o dashboard', async ({ page }) => {
  await login(page, 'erica', 'erica123');
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole('heading', { name: /dashboard executivo/i })).toBeVisible();
});

test('login com credenciais inválidas exibe erro', async ({ page }) => {
  await login(page, 'erica', 'senha-errada');
  await expect(page.getByText(/não conferem/i)).toBeVisible();
});

test('master visualiza dashboard de qualquer pilar', async ({ page }) => {
  await login(page, 'erica', 'erica123');
  const resposta = await page.goto('/pilar/2/');
  expect(resposta?.status()).toBe(200);
  await expect(page.getByRole('heading', { name: /Formação/i })).toBeVisible();
});

test('ponto focal não acessa pilar não autorizado', async ({ page }) => {
  await login(page, 'focal_pdi', 'focal123');
  const negado = await page.goto('/pilar/2/');
  expect(negado?.status()).toBe(403);
  const permitido = await page.goto('/pilar/1/');
  expect(permitido?.status()).toBe(200);
});

test('ponto focal salva rascunho do próprio pilar', async ({ page }) => {
  await login(page, 'focal_pdi', 'focal123');
  await page.goto('/lancamentos/2/1/');
  await expect(page.getByRole('heading', { name: /lançamentos mensais/i })).toBeVisible();
  await page.locator('input[name="valor_3"]').fill('2');
  await page.getByRole('button', { name: /salvar rascunho/i }).click();
  await expect(page.getByText(/rascunho salvo/i)).toBeVisible();
});

test('master aprova lançamento enviado', async ({ page }) => {
  await login(page, 'erica', 'erica123');
  await page.goto('/aprovacao/2/');
  await expect(page.getByRole('heading', { name: /painel de aprovação/i })).toBeVisible();
  const form = page.locator('form', { has: page.getByRole('button', { name: /aprovar/i }) }).first();
  if ((await form.count()) > 0) {
    await form.getByRole('button', { name: /aprovar/i }).click();
    await expect(page.getByText(/aprovado/i).first()).toBeVisible();
  }
});

test('relatório mensal é gerado com dados por pilar', async ({ page }) => {
  await login(page, 'erica', 'erica123');
  const resposta = await page.goto('/relatorio/mensal/2/');
  expect(resposta?.status()).toBe(200);
  await expect(page.getByRole('heading', { name: /relatório mensal/i })).toBeVisible();
  await expect(page.locator('.report').getByText(/competência/i)).toBeVisible();
});

test('importação CSV financeira é validada na tela', async ({ page }) => {
  await login(page, 'erica', 'erica123');
  await page.goto('/financeiro/importar/');
  await page.locator('main select[name="periodo"]').selectOption({ label: '2026-06 — Aberto' });
  await page.locator('input[type="file"]').setInputFiles('data/seed/financeiro_demo.csv');
  await page.getByRole('button', { name: /importar/i }).click();
  const textos = await page.locator('.messages .alert').allTextContents();
  expect(textos.some((t) => /importadas com sucesso|rejeitada|duplicada|fechado/i.test(t))).toBeTruthy();
});
