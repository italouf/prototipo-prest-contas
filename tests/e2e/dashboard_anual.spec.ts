import { expect, test, type Page } from '@playwright/test';

/**
 * E2E do Painel Anual QuIIN (L3+; estendida nos loops L5–L7).
 * Pré-requisito: banco criado com `python manage.py seed_demo` (48 linhas do plano anual).
 * Casos: specs/dashboard-anual.md (T01–T08 neste loop).
 */

async function login(page: Page, username = 'erica', password = 'erica123') {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill(username);
  await page.getByLabel('Senha').fill(password);
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('T01 estado padrão: chips e card PPI', async ({ page }) => {
  await login(page);
  const chips = page.getByTestId('context-chips');
  await expect(chips).toContainText('Período: Acumulado 2024 a 2027');
  await expect(chips).toContainText('Base: Financeiro');
  await expect(chips).toContainText('Unidade: R$ milhões');
  const ppi = page.getByTestId('kpi-ppi');
  await expect(ppi).toContainText('R$ 40 mi');
  await expect(ppi).toContainText('de R$ 60 mi projetados');
  await expect(ppi).toContainText('67%');
});

test('T02 filtro por ano reage em todo o painel', async ({ page }) => {
  await login(page);
  await page.getByTestId('year-select').selectOption('2026');
  await expect(page.getByTestId('context-chips')).toContainText('Período: Ano 3: 2026');
  await expect(page.getByTestId('kpi-ppi')).toContainText('R$ 15 mi');
  await expect(page.getByTestId('chart-rodape-ppi')).toContainText('75%');
  await expect(page).toHaveURL(/ano=2026/);
});

test('T03 troca de base para Físico', async ({ page }) => {
  await login(page);
  await page.getByTestId('base-toggle').getByRole('link', { name: 'Físico' }).click();
  await expect(page.getByTestId('context-chips')).toContainText('Base: Físico');
  await expect(page.getByTestId('context-chips')).toContainText('Unidade: quantidade de metas');
  await expect(page.getByTestId('kpi-total')).toContainText('34 metas');
  await expect(page.getByTestId('kpi-total')).toContainText('50%');
  await expect(page).toHaveURL(/base=fis/);
});

test('T06 deep-link renderiza o estado e sobrevive ao reload', async ({ page }) => {
  await login(page);
  await page.goto('/?ano=2025&base=fis');
  await expect(page.getByTestId('context-chips')).toContainText('Período: Ano 2: 2025');
  await expect(page.getByTestId('context-chips')).toContainText('Base: Físico');
  await expect(page.getByTestId('kpi-ppi')).toContainText('12 metas');
  await page.reload();
  await expect(page.getByTestId('context-chips')).toContainText('Período: Ano 2: 2025');
  await expect(page.getByTestId('kpi-ppi')).toContainText('12 metas');
});

test('T07 parâmetro inválido redireciona para o padrão', async ({ page }) => {
  await login(page);
  await page.goto('/?ano=2030&base=x');
  await expect(page).toHaveURL('/?ano=todos&base=fin');
  await expect(page.getByTestId('context-chips')).toContainText('Período: Acumulado 2024 a 2027');
});

test('T08 URL mensal antiga redireciona 301 para o ano equivalente', async ({ page }) => {
  await login(page);
  const resposta = await page.goto('/?periodo=2026-06-01');
  expect(resposta?.status()).toBe(200);
  await expect(page).toHaveURL('/?ano=2026&base=fin');
  await expect(page.getByTestId('context-chips')).toContainText('Período: Ano 3: 2026');
});
