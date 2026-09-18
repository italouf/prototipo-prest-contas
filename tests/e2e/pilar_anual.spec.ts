import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import * as fs from 'node:fs';

/**
 * E2E do painel anual por pilar (L13; estendido em L14–L15).
 * Pré-requisito: `seed_demo` (pilares 1=PDI, 4=AT; 48 linhas do plano anual).
 * Casos: specs/painel-pilar.md (P01–P06, P11 neste loop).
 */

async function login(page: Page, username = 'erica', password = 'erica123') {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill(username);
  await page.getByLabel('Senha').fill(password);
  await page.getByRole('button', { name: /entrar/i }).click();
}

test('P01 PDI padrão: chips, cards e tabela por ano', async ({ page }) => {
  await login(page);
  await page.goto('/pilar/1/');
  const chips = page.getByTestId('context-chips');
  await expect(chips).toContainText('Período: Acumulado 2024 a 2027');
  await expect(chips).toContainText('Base: Financeiro');
  await expect(page.getByTestId('painel-pilar')).toBeVisible();
  await expect(page.getByTestId('kpi-previsto')).toContainText('29');
  await expect(page.getByTestId('kpi-executado')).toContainText('21');
  await expect(page.getByTestId('kpi-percentual')).toContainText('72%');
  const tabela = page.getByTestId('pilar-tabela');
  await expect(tabela.getByRole('row', { name: /Ano 3: 2026/ })).toContainText('80%');
  await expect(tabela.getByRole('row', { name: /^Total/ })).toContainText('72%');
});

test('P02 filtro por ano reage sem reload', async ({ page }) => {
  await login(page);
  await page.goto('/pilar/1/');
  await page.getByTestId('year-select').selectOption('2026');
  await expect(page.getByTestId('context-chips')).toContainText('Período: Ano 3: 2026');
  await expect(page.getByTestId('kpi-executado')).toContainText('8');
  await expect(page).toHaveURL(/pilar\/1\/\?.*ano=2026/);
});

test('P03 base Físico troca unidade e valores', async ({ page }) => {
  await login(page);
  await page.goto('/pilar/1/');
  await page.getByTestId('base-toggle').getByRole('link', { name: 'Físico' }).click();
  await expect(page.getByTestId('context-chips')).toContainText('Unidade: quantidade de metas');
  await expect(page.getByTestId('kpi-previsto')).toContainText('18');
  await expect(page.getByTestId('kpi-executado')).toContainText('13');
});

test('P04 deep-link renderiza o estado e sobrevive ao reload', async ({ page }) => {
  await login(page);
  await page.goto('/pilar/1/?ano=2025&base=fis');
  await expect(page.getByTestId('context-chips')).toContainText('Período: Ano 2: 2025');
  await expect(page.getByTestId('kpi-executado')).toContainText('5');
  await page.reload();
  await expect(page.getByTestId('context-chips')).toContainText('Período: Ano 2: 2025');
});

test('P05 AT usa Captado e seção mensal continua', async ({ page }) => {
  await login(page);
  await page.goto('/pilar/4/');
  await expect(page.getByTestId('painel-pilar')).toContainText('Captado');
  await expect(page.getByTestId('kpi-executado')).toContainText('2');
  await expect(page.getByRole('heading', { name: /prestação mensal do pilar/i })).toBeVisible();
  await expect(page.locator('#th-1')).toContainText('Captado (R$ mi)');
});

test('P07 sidebar: 5 pilares clicáveis; AT abre o painel; Funil AT em Gestão', async ({ page }) => {
  await login(page);
  await page.goto('/?ano=todos&base=fin');
  const pilares = page.locator('#grp-pilares');
  for (const rotulo of ['PDI', 'Formação FCRH', 'ACS', 'Infraestrutura']) {
    await expect(pilares.getByRole('link', { name: rotulo })).toBeVisible();
  }
  await pilares.getByRole('link', { name: /Associação Tecnológica/ }).click();
  await expect(page).toHaveURL(/pilar\/4\/$/);
  await expect(page.getByTestId('painel-pilar')).toContainText('Captado');
  const gestao = page.locator('#grp-gestao');
  await expect(gestao.getByRole('link', { name: /^Funil AT/ })).toBeVisible();
  await expect(gestao.getByRole('link', { name: /Associação Tecnológica \(AT\)/ })).toHaveCount(0);
});

test('P06 tabela por ano com farol e gráfico com destaque', async ({ page }) => {
  await login(page);
  await page.goto('/pilar/5/?ano=2026&base=fin');
  const tabela = page.getByTestId('pilar-tabela');
  await expect(tabela.getByRole('row', { name: /Ano 3: 2026/ })).toContainText('Meta atingida');
  await expect(tabela.getByRole('row', { name: /Ano 3: 2026/ })).toHaveAttribute('data-destaque', 'true');
  await expect(tabela.getByRole('row', { name: /^Total/ })).toContainText('90%');
  const grafico = page.getByTestId('chart-fonte-pilar');
  await expect(grafico.locator('g[data-categoria="Ano 3 2026"]')).toHaveAttribute('data-destaque', 'true');
});

test('P08 CSV do pilar reflete ano e base', async ({ page }) => {
  await login(page);
  await page.goto('/pilar/1/?ano=2026&base=fis');
  const download = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('link', { name: /baixar dados/i }).click(),
  ]);
  const caminho = await download[0].path();
  const texto = fs.readFileSync(caminho as string, 'utf8').replace(/^﻿/, '');
  const linhas = texto.split('\n');
  expect(linhas[0]).toBe('Pilar;Ano;Previsto;Executado;Saldo;% Executado');
  expect(texto).toContain('PDI;Ano 3: 2026;6;5;1;83%');
  expect(texto).toContain('PDI;Total;18;13;5;72%');
  expect(texto).not.toContain('INFRA');
});

test('P09 impressão do pilar mostra cabeçalho com pilar e filtros', async ({ page }) => {
  await login(page);
  await page.goto('/pilar/4/?ano=2026&base=fin');
  await page.emulateMedia({ media: 'print' });
  await expect(page.getByTestId('print-cabecalho')).toBeVisible();
  await expect(page.getByTestId('print-cabecalho')).toContainText('Associação Tecnológica');
  await expect(page.getByTestId('print-cabecalho')).toContainText('Ano 3: 2026');
  await expect(page.getByTestId('dashboard-controls')).toBeHidden();
});

test('P10 editor do pilar é escopado por papel', async ({ page }) => {
  await login(page, 'focal_pdi', 'focal123');
  await page.goto('/pilar/1/');
  await page.getByRole('button', { name: /editar dados/i }).click();
  await expect(page.getByTestId('editor-dados')).toBeVisible();
  await expect(page.locator('#editor-dados input[name*="__PDI__"]')).not.toHaveCount(0);
  await expect(page.locator('#editor-dados input[name*="__INFRA__"]')).toHaveCount(0);
  await page.goto('/pilar/5/');
  await expect(page.getByRole('button', { name: /editar dados/i })).toHaveCount(0);
  await expect(page.getByTestId('editor-dados')).toHaveCount(0);
});

test('P10b master edita o pilar e restaura', async ({ page }) => {
  await login(page);
  await page.goto('/pilar/1/?ano=todos&base=fin');
  await page.getByRole('button', { name: /editar dados/i }).click();
  await page.locator('input[name="v__2026__financeiro__PDI__executado"]').fill('9');
  await page.getByRole('button', { name: /^aplicar alterações$/i }).first().click();
  await expect(page.getByTestId('kpi-executado')).toContainText('R$ 22 mi');
  await page.goto('/auditoria/');
  await expect(page.getByTestId('timeline-auditoria')).toContainText(/plano anual editado/i);
  await page.goto('/pilar/1/?ano=todos&base=fin');
  await page.getByRole('button', { name: /editar dados/i }).click();
  await page.locator('input[name="v__2026__financeiro__PDI__executado"]').fill('8');
  await page.getByRole('button', { name: /^aplicar alterações$/i }).first().click();
  await expect(page.getByTestId('kpi-executado')).toContainText('R$ 21 mi');
});

test('P11 axe-core limpo no pilar padrão e em AT 2026/Físico', async ({ page }) => {
  await login(page);
  for (const url of ['/pilar/1/', '/pilar/4/?ano=2026&base=fis']) {
    await page.goto(url);
    // Congela animações (anim-entrada): o axe não deve analisar no meio do fade.
    await page.addStyleTag({ content: '*,*::before,*::after{animation:none!important;transition:none!important}' });
    const resultado = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
    const graves = resultado.violations.filter((v) => ['critical', 'serious'].includes(v.impact ?? ''));
    expect(graves, graves.map((v) => `${v.id}: ${v.help}`).join('\n')).toEqual([]);
  }
});
