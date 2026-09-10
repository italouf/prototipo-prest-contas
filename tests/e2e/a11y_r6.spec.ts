import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

async function login(page: Page, username = 'erica', password = 'erica123') {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill(username);
  await page.getByLabel('Senha').fill(password);
  await page.getByRole('button', { name: /entrar/i }).click();
}

const ROTAS = [
  '/',
  '/pilar/1/',
  '/lancamentos/2/1/',
  '/aprovacao/2/',
  '/financeiro/',
  '/financeiro/importar/',
  '/crm-at/funil/',
  '/talentos/organograma/',
  '/relatorio/mensal/2/',
  '/auditoria/',
  '/busca/?q=artigos',
  '/dev/design-system/',
];

for (const rota of ROTAS) {
  test(`a11y: ${rota}`, async ({ page }) => {
    await login(page);
    await page.goto(rota);
    const resultado = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
    const graves = resultado.violations.filter((v) => ['critical', 'serious'].includes(v.impact ?? ''));
    const resumo = graves.map((v) => `${v.id}: ${v.help}`).join('\n');
    expect(graves, resumo).toEqual([]);
  });
}
