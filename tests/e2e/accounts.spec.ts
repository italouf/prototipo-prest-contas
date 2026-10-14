import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

test.use({ locale: 'pt-BR' });

test('login segue a composição da referência e carrega o novo logo', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/accounts/login/');
  await expect(page.getByRole('img', { name: 'SIG QuIIN — Sistema de Informações Gerenciais', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Entrar no SIG QuIIN' })).toHaveCount(1);
  const painel = await page.locator('.login-panel').boundingBox();
  expect(painel!.width).toBe(486);
  expect(Math.abs(painel!.x + painel!.width / 2 - 640)).toBeLessThan(1);
  const logo = page.getByRole('img', { name: 'SENAI CIMATEC', exact: true });
  await expect(logo).toHaveAttribute('src', /senai-cimatec-correto/);
  expect(await logo.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth === 1920)).toBe(true);
  await expect(page.getByTestId('sidebar')).toHaveCount(0);
});

test('controle de senha alterna a visibilidade sem enviar o formulário', async ({ page }) => {
  await page.goto('/accounts/login/');
  const senha = page.getByLabel('Senha', { exact: true });
  await senha.fill('SenhaDeTeste123!');
  await page.getByRole('button', { name: 'Mostrar senha' }).click();
  await expect(senha).toHaveAttribute('type', 'text');
  await expect(page.getByRole('button', { name: 'Ocultar senha' })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: 'Ocultar senha' }).click();
  await expect(senha).toHaveAttribute('type', 'password');
  await expect(senha).toHaveValue('SenhaDeTeste123!');
  await expect(page).toHaveURL(/accounts\/login\/$/);
});

test('login inválido informa o erro e preserva o usuário', async ({ page }) => {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário', { exact: true }).fill('usuario.inexistente.e2e');
  await page.getByLabel('Senha', { exact: true }).fill('SenhaInvalida123!');
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('não conferem');
  await expect(page.getByLabel('Usuário', { exact: true })).toHaveValue('usuario.inexistente.e2e');
});

test('links do login abrem cadastro e recuperação e permitem voltar', async ({ page }) => {
  await page.goto('/accounts/login/');
  await page.getByRole('link', { name: 'Cadastre-se' }).click();
  await expect(page.getByRole('heading', { name: 'Cadastro', exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Entrar', exact: true }).click();
  await page.getByRole('link', { name: 'Esqueci minha senha' }).click();
  await expect(page.getByRole('heading', { name: 'Esqueceu a senha?' })).toBeVisible();
  await page.getByRole('link', { name: 'Voltar para o login' }).click();
  await expect(page).toHaveURL(/accounts\/login\/$/);
});

test('cadastro valida confirmação de senha no servidor', async ({ page }) => {
  await page.goto('/accounts/cadastro/');
  await page.getByLabel('Nome completo').fill('Pessoa de Teste');
  await page.getByLabel('Usuário', { exact: true }).fill('teste.e2e.' + Date.now());
  await page.getByLabel('E-mail', { exact: true }).fill('teste.e2e@example.com');
  await page.getByLabel('Senha', { exact: true }).fill('SenhaDeTeste123!');
  await page.getByLabel('Confirmar senha', { exact: true }).fill('OutraSenha123!');
  await page.getByRole('button', { name: 'Cadastrar', exact: true }).click();
  await expect(page.getByLabel('Confirmar senha', { exact: true })).toHaveAttribute('aria-invalid', 'true');
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page.getByLabel('Nome completo')).toHaveValue('Pessoa de Teste');
  await expect(page).toHaveURL(/accounts\/cadastro\/$/);
});

test('recuperação confirma a solicitação sem revelar contas', async ({ page }) => {
  await page.goto('/accounts/esqueceu-senha/');
  await page.locator('input[name="email"]').fill('inexistente.e2e@example.com');
  await page.getByRole('button', { name: 'Enviar instruções' }).click();
  await expect(page).toHaveURL(/esqueceu-senha\/enviado\/$/);
  await expect(page.getByRole('status')).toContainText('Se houver uma conta ativa');
  await page.getByRole('link', { name: 'Solicitar novamente' }).click();
  await expect(page.getByRole('button', { name: 'Enviar instruções' })).toBeVisible();
});

test('link inválido de recuperação oferece nova solicitação', async ({ page }) => {
  await page.goto('/accounts/redefinir-senha/invalido/token-invalido/');
  await expect(page.getByRole('alert')).toContainText('inválido ou expirou');
  await expect(page.getByRole('button', { name: 'Salvar nova senha' })).toHaveCount(0);
  await page.getByRole('link', { name: 'Solicitar novo link' }).click();
  await expect(page).toHaveURL(/accounts\/esqueceu-senha\/$/);
});

const rotas = ['/accounts/login/', '/accounts/cadastro/', '/accounts/esqueceu-senha/'];
for (const width of [320, 390, 1280]) {
  for (const rota of rotas) {
    test(`layout público sem corte horizontal: ${rota} em ${width}px`, async ({ page }, testInfo) => {
      await page.setViewportSize({ width, height: width === 1280 ? 800 : 844 });
      await page.goto(rota);
      await page.evaluate(() => document.fonts.ready);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
      const painel = await page.locator('.login-panel').boundingBox();
      expect(painel!.x).toBeGreaterThanOrEqual(0);
      expect(painel!.x + painel!.width).toBeLessThanOrEqual(width);
      await expect(page.locator('.login-footer')).toBeVisible();
      await page.screenshot({ path: testInfo.outputPath('tela.png'), fullPage: true });
    });
  }
}

for (const rota of rotas) {
  test(`acessibilidade do formulário público: ${rota}`, async ({ page }) => {
    await page.goto(rota);
    const resultado = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
    expect(resultado.violations, resultado.violations.map(v => `${v.id}: ${v.help}`).join('\n')).toEqual([]);
  });
}
