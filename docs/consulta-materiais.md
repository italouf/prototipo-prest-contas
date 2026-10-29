# Consulta de materiais e dashboards compactos

Os quadros físicos de AT, PDI, FCRH e ACS mostram quantidade de materiais ativos,
última inclusão e acesso à página do produto/projeto. A consulta do dashboard usa
COUNT e MAX no banco; não carrega listas completas ocultas. A última inclusão
corresponde a `criado_em`, independente da data de publicação informada.

Os catálogos de gerenciamento mantêm metadados, contagens, situação e ações de
produto/projeto. A manutenção de materiais fica nas páginas de consulta.

## Navegação

- Produtos: `/entregaveis-at/produtos/<uuid>/`.
- Projetos: `/projetos/pilar/<pilar_pk>/<uuid>/`.
- Biblioteca unificada: `/materiais/?acompanhamento=<id>`.

Filtros GET: `q`, `pilar` (AT, PDI, FORMACAO, STARTUPS), `origem`
(`AT:<uuid>` ou `PROJETO:<uuid>`), `tipo`, `ano_material` (ano ou `sem_data`),
`situacao` (vazio para ativos, `arquivados` para responsáveis), `ordem`
(vazio para inclusão recente, `publicacao`, `titulo`), `tamanho` (10, 25, 50)
e `page`. A paginação padrão é 25. Alterar os filtros reinicia a página.

A busca do detalhe procura o título. A busca da biblioteca também procura o
nome do produto/projeto. Os filtros são independentes das datas dos indicadores.
O Book continua destacado no dashboard e no detalhe do projeto, fora da busca.

Materiais de projetos e produtos mantêm suas tabelas e tipos originais. O serviço
`material_search` aplica escopo e filtros em cada consulta antes de UNION ALL,
com identidade composta por fonte e ID. Ordenação, contagem e paginação ficam no
banco. Relatório reúne Relatório técnico e Relatório; Outros reúne OUTRO e OUTROS.
O resultado apresenta o rótulo original do material.

## Permissões e retorno

O centro vem do acompanhamento selecionado. As opções e resultados só incluem
pilares autorizados. Ter acesso apenas a Outras Fontes não concede acesso à
biblioteca nem aos produtos da AT. Materiais/origens arquivados são consultáveis
somente pelos responsáveis autorizados ao respectivo pilar.

Os formulários e endpoints de gravação existentes continuam válidos. O retorno
contextual usa um token assinado com usuário, centro e URL de uma consulta interna,
válido por 24 horas. URLs livres, tokens adulterados ou de outro usuário/centro não
alteram o retorno padrão. Edição, arquivamento e reativação preservam filtros e
página. Voltar do detalhe aberto pela biblioteca retorna à consulta de origem.
Quando um filtro ou arquivamento reduz o total, páginas fora do intervalo são
ajustadas para a última página disponível.

## Relatórios

Imprimir ou exportar o HTML do dashboard mantém o resumo compacto. Cada quadro
oferece relatório completo do seu pilar. A biblioteca e os detalhes oferecem
relatório completo e CSV com todos os resultados dos filtros, ignorando a paginação.
As rotas correspondentes terminam em `relatorio/` e `materiais.csv` nos detalhes,
ou `/materiais/relatorio/` e `/materiais/dados.csv` na biblioteca. Os CSV antigos de
entregáveis por pilar continuam disponíveis com seus contratos anteriores.

Nenhuma migração de schema ou de dados é necessária; materiais, URLs, vínculos,
permissões e auditoria são preservados. Não há escrita no Neon nesta alteração.

## Verificação

`python manage.py test apps.projects` cobre listas com mais de 100 materiais,
filtros, paginação, permissões, retornos, relatórios e gerenciamento sem listas
completas. `node node_modules/@playwright/test/cli.js test
--config=playwright.materials.config.ts` usa banco temporário com 240 materiais
para validar navegação, filtros, edição com retorno, CSV, relatório completo,
PDF e computador/celular. O servidor de teste só cria esse volume quando
`QUIIN_MATERIAL_LIBRARY_E2E=1`; os bancos de uso real não recebem esses dados.
