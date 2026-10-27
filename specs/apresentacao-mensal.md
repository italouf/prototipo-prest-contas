# Apresentação executiva mensal

Substitui o dashboard mensal L20 na rota `core:mensal`. O PowerPoint de referência não é lido, convertido ou distribuído em runtime.

## Fonte e referência temporal

- `ApresentacaoMensal` possui competência única (primeiro dia do mês) e vínculo obrigatório com `Acompanhamento`.
- A competência organiza o conteúdo editorial e não recorta os consolidados importados. Capa, controles e rodapé identificam a referência original dos números.
- Físico e financeiro reutilizam `accountability.panel`, incluindo overrides e o filtro de pilares antes dos totais.
- Alterar/reimportar o acompanhamento vinculado muda os números no próximo acesso. Criar outro acompanhamento não altera o vínculo.
- Não há fallback para `Lancamento`, `FinanceiroConsolidado`, `PlanoAnual` ou arquivos locais. Ausência de dado é `None`, exibida como `—`.

## Rotas e interface

- `GET /prestacao/mensal/`: apresentação configurada mais recente, ou estado vazio sem criar registros.
- `GET /prestacao/mensal/?periodo=YYYY-MM-DD`: mês específico; competência válida sem cadastro mostra estado vazio. Parâmetro inválido redireciona para o padrão.
- `GET /prestacao/mensal/?periodo=YYYY-MM-DD&print-pdf=1`: documento independente, sem sidebar/cabeçalho do portal, com o mesmo conteúdo filtrado.
- `/prestacao/mensal/editar/?periodo=YYYY-MM-DD`: edição da referência e do título; sem parâmetro, inicia um novo cadastro propondo o mês atual.
- Rotas de conteúdo permitem cadastrar/editar texto e imagem e excluir somente por POST. A imagem possui endpoint autenticado que verifica o escopo do pilar.
- Admin e Master editam; leitores seguem o RBAC existente. A regra vale no backend e no Django Admin. Cada alteração gera auditoria.

## Apresentação

- Reveal.js 6.0.2 local, licença MIT; tema QuIIN em CSS próprio, Montserrat e JetBrains Mono locais, canvas 1280×720.
- Identidade oficial: `LOGO POSITIVA.png` na capa (280 px) e nos cabeçalhos (180 px); `Logo Selo Positivo.png` branco (140 px) no círculo escuro da capa. Cópias locais em `static/img/presentation/`, com margens transparentes compensadas por CSS e proporções preservadas. Os arquivos originais de `assets/logos/` permanecem intactos.
- Nove slides-base: capa; resumo; PDI; FCRH; ACS; AT; PPI/Infraestrutura; AT e outras fontes; pendências/próximos 30 dias.
- Usuários com escopo restrito veem somente blocos e totais autorizados. Destaques gerais aparecem no resumo e detalhados em slides adicionais; destaques de pilar seguem o respectivo bloco.
- Indicadores e textos extensos geram continuações, sem truncar o conteúdo. Itens são ordenados por ordem e ID.
- `ConteudoApresentacao` armazena tipo, pilar opcional, título, texto, ordem e imagem opcional nos destaques. JPEG/PNG/WebP, até 5 MB, ficam em campo binário no banco. Não há limite de resolução na validação da apresentação.
- Navegação por botões e teclado quando o deck possui foco, contador, tela cheia do contêiner e respeito a movimento reduzido.
- Inicialização/destruição acompanha navegação HTMX; fontes e imagens são aguardadas antes de preparar o PDF.
- PDF pelo diálogo do navegador. Validação em Chromium: um slide por página, sem cortes, com cores de fundo.

## Inicialização

1. Executar `python manage.py migrate`.
2. Acessar `/prestacao/mensal/` como Admin/Master e escolher **Configurar apresentação**.
3. Informar o mês, selecionar um acompanhamento já importado e salvar.
4. Cadastrar os conteúdos e abrir **Ver apresentação**.

Não há associação automática de dados antigos nem criação de conteúdos de demonstração na migração.

## Verificação

- Backend: `python manage.py test apps.reports.tests_presentation apps.core.tests_prestacao.MensalContratoUrlTestes`.
- Browser: `npx playwright test --config=playwright.presentation.config.ts --project=chromium`. A configuração cria uma cópia isolada do SQLite e usa a porta 8012. Fixtures são exclusivos da suíte e removidos ao final.
- Cobertura: paridade com painel e overrides, fonte fixa por mês, atualização viva, ausentes/zeros/projeções, meta superada, RBAC em HTML/PDF/imagens, CRUD e auditoria, upload, paginação, HTMX, tela cheia, mobile, PDF e acessibilidade.

## Fora desta versão

Exportação PPTX, edição livre do layout, publicação congelada e cálculo de resultados mensais a partir de bases ainda não confiáveis.
