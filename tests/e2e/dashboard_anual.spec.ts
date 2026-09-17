import { expect, test, type Page } from '@playwright/test';
import * as fs from 'node:fs';
import * as path from 'node:path';

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

const MATRIZ_L0 = JSON.parse(
  fs.readFileSync(
    path.join(process.cwd(), 'docs/retrofit/evidencias/dashboard-anual/loop-0/matriz-estados.json'),
    'utf8',
  ),
) as Record<string, {
  chips: string[];
  cards: Array<{ val: string; sub: string; badge: string }>;
  rodapePpi: { badge: string }; rodapeAt: { badge: string }; rodapeOutras: { badge: string };
}>;

const ESTADOS_L5 = [
  { chave: 'ano-todos_base-fin', ano: 'todos', base: 'fin', destaque: null as string | null },
  { chave: 'ano-2024_base-fin', ano: '2024', base: 'fin', destaque: 'Ano 1 2024' },
  { chave: 'ano-2025_base-fin', ano: '2025', base: 'fin', destaque: 'Ano 2 2025' },
  { chave: 'ano-2026_base-fin', ano: '2026', base: 'fin', destaque: 'Ano 3 2026' },
  { chave: 'ano-2027_base-fin', ano: '2027', base: 'fin', destaque: 'Ano 4 2027' },
  { chave: 'ano-todos_base-fis', ano: 'todos', base: 'fis', destaque: null as string | null },
  { chave: 'ano-2024_base-fis', ano: '2024', base: 'fis', destaque: 'Ano 1 2024' },
  { chave: 'ano-2025_base-fis', ano: '2025', base: 'fis', destaque: 'Ano 2 2025' },
  { chave: 'ano-2026_base-fis', ano: '2026', base: 'fis', destaque: 'Ano 3 2026' },
  { chave: 'ano-2027_base-fis', ano: '2027', base: 'fis', destaque: 'Ano 4 2027' },
];

const IDS_CARDS = ['kpi-ppi', 'kpi-at', 'kpi-outras', 'kpi-total'] as const;

test('T09 farol por faixa no acumulado financeiro', async ({ page }) => {
  await login(page);
  const tabela = page.getByTestId('pilares-table');
  await expect(tabela.getByRole('row', { name: /Infraestrutura/ })).toContainText('Meta atingida');
  await expect(tabela.getByRole('row', { name: /PDI/ }).first()).toContainText('Execução parcial');
  await expect(tabela.getByRole('row', { name: /ACS/ })).toContainText('Execução crítica');
});

test('T09 farol reage ao estado (acumulado físico, FCRH 47%)', async ({ page }) => {
  await login(page);
  await page.goto('/?ano=todos&base=fis');
  const tabela = page.getByTestId('pilares-table');
  await expect(tabela.getByRole('row', { name: /Formação FCRH/ })).toContainText('Execução crítica');
  await expect(page.getByTestId('farol-legenda')).toContainText('Meta atingida:');
});

test('T11 modal abre com foco, fecha por ESC devolvendo o foco', async ({ page }) => {
  await login(page);
  const gatilho = page.getByTestId('farol-abrir');
  await gatilho.click();
  const modal = page.getByTestId('farol-modal');
  await expect(modal).toBeVisible();
  await expect(modal.getByRole('dialog')).toBeVisible();
  await expect(modal).toContainText('Farol de execução: metodologia e leitura');
  const focado = await page.evaluate(() => document.activeElement?.getAttribute('data-fechar'));
  expect(focado).not.toBeNull();
  await page.keyboard.press('Escape');
  await expect(modal).toBeHidden();
  await expect(gatilho).toBeFocused();
});

test('T11 modal fecha pelo X e pelo backdrop', async ({ page }) => {
  await login(page);
  await page.getByTestId('farol-abrir').click();
  const modal = page.getByTestId('farol-modal');
  await expect(modal).toBeVisible();
  await modal.getByRole('button', { name: /fechar/i }).click();
  await expect(modal).toBeHidden();
  await page.getByTestId('farol-abrir').click();
  await expect(modal).toBeVisible();
  await page.mouse.click(30, 300);
  await expect(modal).toBeHidden();
});

for (const estado of ESTADOS_L5) {
  test(`L5 paridade ${estado.chave} com o Anexo A`, async ({ page }) => {
    await login(page);
    await page.goto(`/?ano=${estado.ano}&base=${estado.base}`);
    const esperado = MATRIZ_L0[estado.chave];
    const chips = page.getByTestId('context-chips');
    for (const chip of esperado.chips) {
      await expect(chips).toContainText(chip);
    }
    for (let i = 0; i < 4; i++) {
      const card = page.getByTestId(IDS_CARDS[i]);
      await expect(card).toContainText(esperado.cards[i].val);
      await expect(card).toContainText(esperado.cards[i].sub);
      await expect(card).toContainText(esperado.cards[i].badge);
    }
    await expect(page.getByTestId('chart-rodape-ppi')).toContainText(esperado.rodapePpi.badge);
    await expect(page.getByTestId('chart-rodape-at')).toContainText(esperado.rodapeAt.badge);
    await expect(page.getByTestId('chart-rodape-outras')).toContainText(esperado.rodapeOutras.badge);
    for (const grafico of ['chart-fonte-ppi', 'chart-fonte-at', 'chart-fonte-outras']) {
      const bloco = page.getByTestId(grafico);
      if (estado.destaque === null) {
        await expect(bloco.locator('g[data-destaque="true"]')).toHaveCount(0);
      } else {
        await expect(bloco.locator(`g[data-categoria="${estado.destaque}"]`)).toHaveAttribute('data-destaque', 'true');
      }
    }
    const consol = page.getByTestId('chart-consolidado');
    if (estado.destaque === null) {
      await expect(consol.locator('g[data-destaque="true"]')).toHaveCount(0);
    } else {
      await expect(consol.locator(`g[data-categoria="${estado.destaque}"]`)).toHaveAttribute('data-destaque', 'true');
    }
  });
}
