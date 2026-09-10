import { test, type Page } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const dir = process.env.EVIDENCIA_DIR ?? 'docs/retrofit/evidencias/atuais';

async function login(page: Page) {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill('erica');
  await page.getByLabel('Senha').fill('erica123');
  await page.getByRole('button', { name: /entrar/i }).click();
  await page.waitForURL('**/');
}

test('captura evidencias visuais das paginas principais', async ({ page }) => {
  fs.mkdirSync(dir, { recursive: true });
  await page.setViewportSize({ width: 1440, height: 900 });

  await page.goto('/accounts/login/');
  await page.screenshot({ path: path.join(dir, 'login.png'), fullPage: true });

  await login(page);
  const paginas: Array<[string, string]> = [
    ['dashboard', '/'],
    ['pilar-pdi', '/pilar/1/'],
    ['lancamento', '/lancamentos/2/1/'],
    ['aprovacao', '/aprovacao/2/'],
    ['financeiro-importar', '/financeiro/importar/'],
    ['crm-at-funil', '/crm-at/funil/'],
    ['talentos-organograma', '/talentos/organograma/'],
    ['auditoria', '/auditoria/'],
    ['relatorio-mensal', '/relatorio/mensal/2/'],
  ];
  for (const [nome, url] of paginas) {
    await page.goto(url);
    await page.screenshot({ path: path.join(dir, `${nome}.png`), fullPage: true });
  }
});
