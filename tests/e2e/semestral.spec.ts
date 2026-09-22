import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import * as fs from 'node:fs';

/**
 * E2E da visão geral semestral no padrão Geral/Pilares (L21).
 * Pré-requisito: `seed_demo` (S1/2026 com dados; S2/2026 quase vazio).
 * Casos: specs/prestacao-semestral.md (S01–S10).
 */

async function login(page: Page, username = 'erica', password = 'erica123') {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill(username);
  await page.getByLabel('Senha').fill(password);
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('S01 padrão resolve um semestre com visão geral', async ({ page }) => {
  await login(page);
  await page.goto('/prestacao/semestral/');
  await expect(page.getByRole('heading', { name: /prestação de contas — semestral/i })).toBeVisible();
  await expect(page.getByTestId('context-chips')).toContainText(/[12]º semestre de 20\d\d/);
  await expect(page.getByTestId('kpi-sem-pdi')).toBeVisible();
  await expect(page.getByTestId('chart-fonte-meses')).toBeVisible();
  await expect(page.getByTestId('tabela-semestre')).toContainText('PDI');
  await expect(page.getByTestId('status-semestre')).toBeVisible();
  await page.goto('/prestacao/semestral/?ano=2026&semestre=1');
  await expect(page.getByTestId('context-chips')).toContainText('1º semestre de 2026');
  await expect(page.getByTestId('chart-fonte-pilares')).toBeVisible();
  await expect(page.getByTestId('meses-semestre').getByRole('link', { name: '2026-06' }))
    .toHaveAttribute('href', '/prestacao/mensal/?periodo=2026-06-01');
});

test('S02 troca de semestre reage sem reload', async ({ page }) => {
  await login(page);
  await page.goto('/prestacao/semestral/?ano=2026&semestre=1');
  await page.getByTestId('semestre-toggle').getByRole('link', { name: '2º semestre' }).click();
  await expect(page).toHaveURL(/semestre=2/);
  await expect(page.getByTestId('context-chips')).toContainText('2º semestre de 2026');
  await expect(page.getByTestId('feed-semestre')).toContainText('Nenhum destaque neste semestre');
});

test('S03 KPIs e tabela com farol', async ({ page }) => {
  await login(page);
  await page.goto('/prestacao/semestral/?ano=2026&semestre=1');
  await expect(page.getByTestId('kpi-sem-pdi')).toBeVisible();
  const tabela = page.getByTestId('tabela-semestre');
  await expect(tabela.getByRole('row', { name: /PDI-PROJ-INI/ })).toBeVisible();
});

test('S04 SVG por mês e por pilar', async ({ page }) => {
  await login(page);
  await page.goto('/prestacao/semestral/?ano=2026&semestre=1');
  const meses = page.getByTestId('chart-fonte-meses');
  await expect(meses.locator('g[data-categoria="Mai 2026"]')).toHaveCount(1);
  await expect(page.getByTestId('chart-fonte-pilares')).toBeVisible();
});

test('S05 drill-down mês ↔ semestre', async ({ page }) => {
  await login(page);
  await page.goto('/prestacao/semestral/?ano=2026&semestre=1');
  await page.getByTestId('meses-semestre').getByRole('link', { name: '2026-06' }).click();
  await expect(page).toHaveURL(/prestacao\/mensal\/\?periodo=2026-06-01/);
  await page.getByRole('toolbar', { name: /ações do mês/i })
    .getByRole('link', { name: /ver semestre/i }).click();
  await expect(page).toHaveURL(/prestacao\/semestral\/\?ano=2026&semestre=1/);
});

test('S06 CSV do semestre reflete ano e escopo', async ({ page }) => {
  await login(page);
  await page.goto('/prestacao/semestral/?ano=2026&semestre=1');
  const download = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('link', { name: /baixar dados/i }).click(),
  ]);
  const caminho = await download[0].path();
  const texto = fs.readFileSync(caminho as string, 'utf8').replace(/^﻿/, '');
  const linhas = texto.split('\n');
  expect(linhas[0]).toBe('Mês;Pilar;Indicador;Meta;Realizado;% Executado');
  expect(texto).toContain(';PDI;');
  expect(texto).toContain('2026-05');
});

test('S07 impressão mostra cabeçalho do semestre e esconde controles', async ({ page }) => {
  await login(page);
  await page.goto('/prestacao/semestral/?ano=2026&semestre=1');
  await page.emulateMedia({ media: 'print' });
  await expect(page.getByTestId('print-cabecalho')).toBeVisible();
  await expect(page.getByTestId('print-cabecalho')).toContainText('1º semestre de 2026');
  await expect(page.getByTestId('dashboard-controls')).toBeHidden();
});

test('S08 axe-core limpo no semestral', async ({ page }) => {
  await login(page);
  await page.goto('/prestacao/semestral/?ano=2026&semestre=1');
  await page.addStyleTag({ content: '*,*::before,*::after{animation:none!important;transition:none!important}' });
  const resultado = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
  const graves = resultado.violations.filter((v) => ['critical', 'serious'].includes(v.impact ?? ''));
  expect(graves, graves.map((v) => `${v.id}: ${v.help}`).join('\n')).toEqual([]);
});

test('S09 header tem ano, semestre e toggle da barra', async ({ page }) => {
  await login(page);
  await page.goto('/prestacao/semestral/?ano=2026&semestre=1');
  const controles = page.getByTestId('dashboard-controls');
  await expect(controles).toBeVisible();
  await expect(controles.getByTestId('semestre-ano')).toBeVisible();
  await expect(page.getByTestId('semestre-toggle').getByRole('link', { name: '1º semestre' }))
    .toHaveAttribute('aria-current', 'true');
  const alternador = page.getByTestId('barra-toggle');
  await alternador.click();
  await expect(controles).toBeHidden();
  await alternador.click();
  await expect(controles).toBeVisible();
});

test('S10 ponto focal vê só o próprio pilar', async ({ page }) => {
  await login(page, 'focal_pdi', 'focal123');
  await page.goto('/prestacao/semestral/?ano=2026&semestre=1');
  await expect(page.getByTestId('kpi-sem-pdi')).toBeVisible();
  await expect(page.getByTestId('kpi-sem-at')).toHaveCount(0);
});
