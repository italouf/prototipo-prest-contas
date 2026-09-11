import { expect, test, type Locator, type Page } from '@playwright/test';
import * as fs from 'fs';

async function login(page: Page, username = 'erica', password = 'erica123') {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill(username);
  await page.getByLabel('Senha').fill(password);
  await page.getByRole('button', { name: /entrar/i }).click();
}

async function logout(page: Page) {
  await page.getByRole('button', { name: /sair/i }).click();
  await expect(page.getByRole('heading', { name: /entrar no portal quiin/i })).toBeVisible();
}

/** Simula o drag-and-drop HTML5 de forma determinística (dragstart/dragover/drop). */
async function arrastar(page: Page, card: Locator, destino: string) {
  const aguardar =
    destino === 'DEVOLVIDO'
      ? null
      : page.waitForResponse(
          (r) => r.request().method() === 'POST' && r.url().includes('/mover/'),
        );
  await card.evaluate((el, alvo) => {
    const coluna = document.querySelector(`[data-testid="kanban-coluna-${alvo}"]`);
    const dt = new DataTransfer();
    el.dispatchEvent(new DragEvent('dragstart', { bubbles: true, dataTransfer: dt }));
    coluna?.dispatchEvent(new DragEvent('dragover', { bubbles: true, cancelable: true, dataTransfer: dt }));
    coluna?.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt }));
  }, destino);
  if (aguardar) {
    await aguardar;
  }
}

test('timeline abre apos navegacao por boost e mostra eventos', async ({ page }) => {
  await login(page);
  await page.getByTestId('sidebar').getByRole('link', { name: /^Aprovação/ }).click();
  await expect(page.getByRole('heading', { name: /painel de aprovação/i })).toBeVisible();

  const cartao = page.locator('[data-testid^="kanban-card-"]').first();
  await cartao.getByRole('button', { name: /ver timeline/i }).click();
  const drawer = page.getByTestId('drawer-timeline');
  await expect(drawer).toBeVisible();
  await expect(page.getByTestId('drawer-lancamento')).toBeVisible();
  await expect(page.getByTestId('drawer-lancamento')).toContainText('Timeline de aprovação');
  await expect(page.getByTestId('timeline-lancamento')).toContainText(/Lançamento/);
  await page.getByTestId('drawer-timeline-fechar').click();
  await expect(drawer).not.toBeVisible();
});

test('modal de devolucao abre apos navegacao por boost', async ({ page }) => {
  await login(page, 'focal_pdi', 'focal123');
  await page.goto('/lancamentos/2/1/');
  await page.locator('input[name="valor_3"]').fill('2');
  await page.getByRole('button', { name: /enviar para validação/i }).click();
  await expect(page.locator('.messages .alert')).toContainText(/enviados para validação/i);
  await logout(page);

  await login(page);
  await page.getByTestId('sidebar').getByRole('link', { name: /^Aprovação/ }).click();
  const cartao = page
    .getByTestId('kanban-coluna-ENVIADO')
    .locator('article', { hasText: 'Projetos iniciados' })
    .first();
  await cartao.getByRole('button', { name: /devolver/i }).click();
  await expect(page.getByTestId('modal-devolucao')).toBeVisible();
  await expect(page.getByTestId('motivo-devolucao')).toBeVisible();
  await page.getByRole('button', { name: /cancelar/i }).click();
  await expect(page.getByTestId('modal-devolucao')).not.toBeVisible();
});

test('talentos renderiza no primeiro clique pela sidebar', async ({ page }) => {
  await login(page);
  await page.getByTestId('sidebar').getByRole('link', { name: /^Talentos/ }).click();
  await expect(page.getByRole('heading', { name: /organograma/i })).toBeVisible();
  await expect(page.getByTestId('talento-card').first()).toBeVisible();
  await expect(page.getByTestId('busca-talento')).toBeVisible();
});

test('drag move card no kanban e toast confirma', async ({ page }) => {
  await login(page, 'focal_pdi', 'focal123');
  await page.goto('/lancamentos/2/1/');
  await page.locator('input[name="valor_3"]').fill('2');
  await page.getByRole('button', { name: /salvar rascunho/i }).click();
  await expect(page.locator('.messages .alert')).toContainText(/rascunho salvo/i);
  await logout(page);

  await login(page);
  await page.goto('/aprovacao/2/');
  const rascunho = page
    .getByTestId('kanban-coluna-RASCUNHO')
    .locator('article', { hasText: 'Projetos iniciados' })
    .first();
  await expect(rascunho).toBeVisible();
  await arrastar(page, rascunho, 'ENVIADO');
  await expect(
    page.locator('.messages .alert').filter({ hasText: /movido para Enviado/i }),
  ).toBeVisible();
  await expect(page.getByTestId('kanban-coluna-ENVIADO')).toContainText('Projetos iniciados');

  const enviado = page
    .getByTestId('kanban-coluna-ENVIADO')
    .locator('article', { hasText: 'Projetos iniciados' })
    .first();
  await arrastar(page, enviado, 'APROVADO');
  await expect(
    page.locator('.messages .alert').filter({ hasText: /movido para Aprovado/i }),
  ).toBeVisible();
  await expect(page.getByTestId('kanban-coluna-APROVADO')).toContainText('Projetos iniciados');
});

test('drag para devolvido abre o modal de justificativa', async ({ page }) => {
  await login(page, 'focal_pdi', 'focal123');
  await page.goto('/lancamentos/2/1/');
  await page.locator('input[name="valor_4"]').fill('9');
  await page.getByRole('button', { name: /enviar para validação/i }).click();
  await expect(page.locator('.messages .alert')).toContainText(/enviados para validação/i);
  await logout(page);

  await login(page);
  await page.goto('/aprovacao/2/');
  const card = page
    .getByTestId('kanban-coluna-ENVIADO')
    .locator('article', { hasText: 'Projetos em andamento' })
    .first();
  await arrastar(page, card, 'DEVOLVIDO');
  await expect(page.getByTestId('modal-devolucao')).toBeVisible();
  await page.getByTestId('motivo-devolucao').fill('Ajustar meta de demonstração.');
  await page.getByRole('button', { name: /confirmar devolução/i }).click();
  await expect(page.locator('.messages .alert')).toContainText(/devolvido/i);
  await expect(page.getByTestId('kanban-coluna-DEVOLVIDO')).toContainText('Projetos em andamento');
});

test('financeiro oferece download do modelo CSV importavel', async ({ page }) => {
  await login(page);
  await page.goto('/financeiro/importar/');
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByTestId('baixar-modelo-csv').click(),
  ]);
  expect(download.suggestedFilename()).toBe('modelo_financeiro.csv');
  const caminho = await download.path();
  const conteudo = fs.readFileSync(caminho, 'utf-8');
  expect(conteudo.split('\n')[0].replace(/^\ufeff/, '')).toBe(
    'competencia,pilar,tipo_recurso,valor_captado,valor_executado,observacao',
  );
  expect(conteudo).toContain(',EMBRAPII,');
});

test('nova oportunidade usa empresa como texto com sugestoes', async ({ page }) => {
  await login(page, 'focal_at', 'focal123');
  await page.goto('/crm-at/oportunidades/nova/');
  const campo = page.locator('input[name="empresa_nome"]');
  await expect(campo).toBeVisible();
  await expect(page.locator('datalist#empresas-lista')).toHaveCount(1);

  await campo.fill('Empresa Que Não Existe Ltda');
  await page.locator('input[name="valor_previsto"]').fill('100');
  await page.getByRole('button', { name: /salvar/i }).click();
  await expect(page.getByText(/empresa não encontrada/i)).toBeVisible();

  await campo.fill('Metalúrgica Exemplo S.A.');
  await page.getByRole('button', { name: /salvar/i }).click();
  await expect(page.getByRole('heading', { name: /funil at/i })).toBeVisible();
});

test('oportunidade perdida pode ser reaberta pela edicao', async ({ page }) => {
  await login(page, 'erica', 'erica123');
  await page.goto('/crm-at/funil/');
  const perdidas = page.locator('details', { hasText: /oportunidades perdidas/i });
  if ((await perdidas.count()) === 0) {
    test.skip(true, 'sem oportunidades perdidas no estado atual');
    return;
  }
  await perdidas.locator('summary').click();
  const link = perdidas.getByRole('link', { name: /editar \/ reabrir/i }).first();
  await link.click();
  await expect(page.getByRole('heading', { name: /editar oportunidade/i })).toBeVisible();
  await expect(page.locator('input[name="empresa_nome"]')).not.toHaveValue('');
});
