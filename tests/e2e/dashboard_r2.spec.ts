import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import * as path from 'node:path';

/** Fixtures importados próprios, removidos ao final. Prefira executar em cópia do banco. */
const python = path.resolve('.venv/Scripts/python.exe');
const cleanup = `
from apps.reports.models import ApresentacaoMensal
from apps.accountability.models import CentroCompetencia
from apps.accounts.models import User
ApresentacaoMensal.objects.filter(acompanhamento__centro__codigo='mensal-e2e').delete()
CentroCompetencia.objects.filter(codigo='mensal-e2e').delete()
User.objects.filter(username='mensal_e2e').delete()
`;
const setup = `
from datetime import date
from apps.accountability.models import CentroCompetencia,Acompanhamento,ResumoFinanceiro,KpiAcompanhamento
from apps.reports.models import ApresentacaoMensal
from apps.accounts.models import User
from apps.core.permissions import adicionar_grupo
from apps.pillars.models import Pilar
u=adicionar_grupo(User.objects.create_user(username='mensal_e2e',password='mensal-e2e-123'),'Master')
c=CentroCompetencia.objects.create(codigo='mensal-e2e',nome='Centro de Competência QuIIN em Tecnologias Quânticas')
a=Acompanhamento.objects.create(centro=c,periodo_referencia='3T/2026')
for codigo in ['PDI','FORMACAO','STARTUPS','INFRA','AT','OUTRASFONTES']:
 p,_=Pilar.objects.get_or_create(codigo=codigo,defaults={'nome':codigo})
 ResumoFinanceiro.objects.create(acompanhamento=a,origem='TAB. 9' if codigo in ['AT','OUTRASFONTES'] else 'TAB. 1',pilar=p,recurso_ou_meta=1000000,captado=600000 if codigo in ['AT','OUTRASFONTES'] else None,realizado=250000)
for n,(codigo,nome,meta,executado) in enumerate([
 ('PDI','Projetos de pesquisa e desenvolvimento',18,15),('PDI','Pedidos de propriedade intelectual',9,4),('PDI','Publicações em periódicos',21,9),
 ('FORMACAO','Profissionais formados e capacitados',800,2107),('STARTUPS','Empresas de base tecnológica participantes',50,70),('STARTUPS','Projetos em inovação aberta',26,2),
 ('AT','Empresas participantes como associadas',129,14),('AT','Participação de recursos das empresas associadas',1,0.4),('OUTRASFONTES','Recursos de outras fontes',1,0.6),('INFRA','Implantação da infraestrutura',1,0.56)],1):
 KpiAcompanhamento.objects.create(acompanhamento=a,codigo=f'E2E-{n:02}',sequencia=n,nome=nome,pilar=Pilar.objects.get(codigo=codigo),meta_total=meta,acumulado=executado,unidade='Número absoluto')
for mes in [11,12]:
 ApresentacaoMensal.objects.create(competencia=date(2098,mes,1),acompanhamento=a,titulo='Reunião de acompanhamento mensal',criado_por=u)
`;

async function login(page: Page) {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill('mensal_e2e');
  await page.getByLabel('Senha', { exact: true }).fill('mensal-e2e-123');
  await page.getByRole('button', { name: /entrar/i }).click();
  await expect(page).not.toHaveURL(/accounts\/login/);
}

test.describe('Apresentação mensal importada', () => {
  test.skip(!process.env.QUIIN_PRESENTATION_E2E, 'Use --config=playwright.presentation.config.ts para executar em banco isolado.');
  test.describe.configure({ mode: 'serial' });
  test.beforeAll(() => {
    execFileSync(python, ['manage.py', 'shell', '-c', cleanup + setup], { timeout: 60_000 });
  });
  test.afterAll(() => {
    execFileSync(python, ['manage.py', 'shell', '-c', cleanup], { timeout: 30_000 });
  });
  test.beforeEach(async ({ page }) => login(page));

  test('M01 nove slides, controles e navegação pelo teclado', async ({ page }, testInfo) => {
    await page.goto('/prestacao/mensal/?periodo=2098-11-01');
    const deck = page.getByTestId('presentation-deck');
    await expect(deck).toHaveAttribute('data-ready', 'true');
    await expect(deck.locator('.slides > section')).toHaveCount(9);
    await expect(page.locator('[data-presentation-counter]')).toHaveText('1 / 9');
    await page.screenshot({ path: testInfo.outputPath('mensal-capa.png'), fullPage: true });
    await deck.focus();
    await page.keyboard.press('ArrowRight');
    await expect(page.locator('[data-presentation-counter]')).toHaveText('2 / 9');
    await page.getByRole('button', { name: 'Próximo slide', exact: true }).click();
    await expect(page.locator('[data-presentation-counter]')).toHaveText('3 / 9');
    await expect(deck.locator('section.present')).toContainText('Projetos de pesquisa');
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: testInfo.outputPath('mensal-pdi.png'), fullPage: true });
  });

  test('M02 navegação HTMX, troca de mês e retorno não duplicam eventos', async ({ page }) => {
    await page.locator('[data-testid="sidebar"]').getByRole('link', { name: 'Mensal', exact: true }).click();
    await expect(page.getByTestId('presentation-deck')).toHaveAttribute('data-ready', 'true');
    await page.evaluate(() => { (window as any).__mensalMarker = 42; });
    await page.getByTestId('presentation-month').selectOption('2098-11-01');
    await page.getByRole('button', { name: 'Exibir', exact: true }).click();
    await expect(page).toHaveURL(/periodo=2098-11-01/);
    await expect(page.getByTestId('presentation-deck')).toHaveAttribute('data-ready', 'true');
    expect(await page.evaluate(() => (window as any).__mensalMarker)).toBe(42);
    await page.locator('[data-testid="sidebar"]').getByRole('link', { name: 'Visão geral', exact: true }).click();
    await expect(page.getByTestId('presentation-deck')).toHaveCount(0);
    await page.locator('[data-testid="sidebar"]').getByRole('link', { name: 'Mensal', exact: true }).click();
    await expect(page.getByTestId('presentation-deck')).toHaveAttribute('data-ready', 'true');
    await page.getByRole('button', { name: 'Próximo slide', exact: true }).click();
    await expect(page.locator('[data-presentation-counter]')).toHaveText('2 / 9');
  });

  test('M03 editor salva destaque com imagem no banco e gera continuação', async ({ page }) => {
    await page.goto('/prestacao/mensal/editar/?periodo=2098-12-01');
    await page.getByRole('link', { name: 'Adicionar conteúdo', exact: true }).click();
    await page.getByLabel(/^Título/).fill('Marco de pesquisa do mês');
    await page.getByLabel(/^Texto/).fill('Integração das tecnologias quânticas e clássicas. '.repeat(25));
    await page.getByLabel(/^Imagem opcional/).setInputFiles({
      name: 'marco.png', mimeType: 'image/png',
      buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64'),
    });
    await page.getByLabel(/^Descrição da imagem/).fill('Ilustração do marco de pesquisa');
    await page.getByRole('button', { name: 'Salvar conteúdo', exact: true }).click();
    await expect(page.getByText('Marco de pesquisa do mês', { exact: true })).toBeVisible();
    await page.getByRole('link', { name: 'Ver apresentação', exact: true }).click();
    const deck = page.getByTestId('presentation-deck');
    await expect(deck).toHaveAttribute('data-ready', 'true');
    expect(await deck.locator('[data-slide-kind="editorial"]').count()).toBeGreaterThan(1);
    const image = deck.locator('.deck-editorial img').first();
    await expect(image).toHaveAttribute('src', /prestacao\/mensal\/imagens\/\d+\//);
    expect(await image.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0)).toBe(true);
  });

  test('M04 PDF contém uma página por slide, sem shell e sem cortes', async ({ page }, testInfo) => {
    await page.goto('/prestacao/mensal/?periodo=2098-12-01&print-pdf=1');
    const deck = page.getByTestId('presentation-deck');
    await expect(deck).toHaveAttribute('data-ready', 'true');
    await expect(page.getByTestId('sidebar')).toHaveCount(0);
    const total = await deck.locator('section.quiin-slide').count();
    const pdf = await page.pdf({ path: testInfo.outputPath('mensal.pdf'), printBackground: true, preferCSSPageSize: true });
    expect(pdf.subarray(0, 4).toString()).toBe('%PDF');
    expect((pdf.toString('latin1').match(/\/Type\s*\/Page\b/g) || []).length).toBe(total);
    const overflow = await deck.locator('.deck-body').evaluateAll(elements => elements.filter(el => el.scrollHeight > el.clientHeight + 4).length);
    expect(overflow).toBe(0);
  });

  test('M05 tela cheia, responsividade e ausência de erros JS', async ({ page }, testInfo) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('/prestacao/mensal/?periodo=2098-11-01');
    await expect(page.getByTestId('presentation-deck')).toHaveAttribute('data-ready', 'true');
    await page.getByRole('button', { name: /Tela cheia/ }).click();
    await expect.poll(() => page.evaluate(() => !!document.fullscreenElement)).toBe(true);
    await page.getByRole('button', { name: /Sair da tela cheia/ }).click();
    await expect.poll(() => page.evaluate(() => !!document.fullscreenElement)).toBe(false);
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath('mensal-mobile.png'), fullPage: true });
    expect(errors).toEqual([]);
  });

  test('M06 axe sem violações graves na apresentação', async ({ page }) => {
    await page.goto('/prestacao/mensal/?periodo=2098-11-01');
    await expect(page.getByTestId('presentation-deck')).toHaveAttribute('data-ready', 'true');
    const resultado = await new AxeBuilder({ page }).include('.presentation-page').withTags(['wcag2a', 'wcag2aa']).analyze();
    expect(resultado.violations.filter(v => ['critical', 'serious'].includes(v.impact || ''))).toEqual([]);
  });

  test('M07 hierarquia e estado do grupo Gestao da AT', async ({ page }, testInfo) => {
    await page.goto('/prestacao/mensal/?periodo=2098-11-01');
    const sidebar = page.getByTestId('sidebar');
    const button = sidebar.locator('[data-nav-grupo="grp-gestao"]');
    const group = sidebar.locator('#grp-gestao');
    const associados = group.getByRole('link', { name: 'Associados', exact: true });
    const solicitacoes = group.getByRole('link', { name: 'Solicitações', exact: true });
    const acompanhamento = group.getByRole('link', { name: 'Acompanhamento', exact: true });
    const talentos = group.getByRole('link', { name: 'Talentos', exact: true });
    await expect(group).toBeVisible();
    await expect(associados).toBeVisible();
    await expect(solicitacoes).toBeVisible();
    await expect(acompanhamento).toBeVisible();
    await expect(group.getByRole('link', { name: 'Funil de prospecção', exact: true })).toBeVisible();
    const talentosHref = await talentos.getAttribute('href');
    const firstX = await associados.locator('.nav-rotulo').evaluate(el => el.getBoundingClientRect().x);
    const childX = await solicitacoes.locator('.nav-rotulo').evaluate(el => el.getBoundingClientRect().x);
    const talentosX = await talentos.locator('.nav-rotulo').evaluate(el => el.getBoundingClientRect().x);
    expect(childX).toBeGreaterThan(firstX);
    expect(talentosX).toBeCloseTo(firstX, 0);
    await talentos.scrollIntoViewIfNeeded();
    await sidebar.screenshot({ path: testInfo.outputPath('sidebar-hierarchy.png') });
    await button.click();
    await expect(group).toBeHidden();
    await expect(button).toHaveAttribute('aria-expanded', 'false');
    await page.reload();
    await expect(page.locator('#grp-gestao')).toBeHidden();
    await page.goto(talentosHref!);
    await expect(page.locator('#grp-gestao')).toBeVisible();
    await expect(sidebar.getByRole('link', { name: 'Talentos', exact: true })).toHaveAttribute('aria-current', 'page');
  });

});
