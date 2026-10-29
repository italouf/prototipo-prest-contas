# Entregáveis da AT

O dashboard utiliza agora resumo por produto e páginas de consulta paginadas.
Consulte [Consulta de materiais](consulta-materiais.md) para os fluxos de busca,
biblioteca, retorno contextual e relatórios completos.

O quadro aparece somente no Físico do dashboard combinado AT e Outras Fontes,
após a visão gerencial. Mostra Produto, Materiais do produto e Ações. A carteira
de produtos ativos pertence ao centro do acompanhamento selecionado, é completa
e não acompanha os filtros de mês/ano. Não há coluna nem cadastro de Book na AT.

## Produtos e materiais

`ProdutoAT` tem UUID, centro, nome normalizado único por centro, ordem de exibição,
situação e metadados de criação/edição. O catálogo inicial inclui os oito produtos
da lista fornecida e Propriedade Intelectual (PI), na última posição.
`codigo_padrao` é uma chave interna estável e não editável dos produtos iniciais;
produtos novos têm essa chave nula. Inicializações repetidas não alteram nomes,
ordem ou situação dos produtos existentes.

`MaterialProdutoAT` pertence a um produto, com título, tipo, URL HTTP/HTTPS e data
de publicação/entrega opcional. Os tipos são Apresentação, Relatório, Boletim,
Documento, Certificado, Artigo e Outros. PI é um produto, utilizando esses mesmos
tipos. Os tipos e cadastros de materiais dos projetos permanecem independentes.

Os responsáveis podem adicionar, renomear e ordenar produtos. A ordem inicial
é de 0 a 8; novos produtos começam após o maior valor existente. Empates são
ordenados por nome e UUID. Nomes equivalentes por normalização Unicode,
maiúsculas/minúsculas e espaços não podem ser duplicados no mesmo centro.

Arquivar um produto preserva seus materiais. Reativá-lo restaura sua exibição com
os materiais ativos. Materiais também podem ser arquivados e reativados. As
operações ficam na auditoria, com usuário, valores e vínculos correspondentes.

## Acesso e exportação

As rotas estão sob `/entregaveis-at/`, namespace `deliverables_at`, e recebem o
acompanhamento pela query string. A autorização usa a AT explicitamente: acesso
somente a Outras Fontes não permite ver produtos, materiais, formulários ou CSV
da AT. Master/Admin e pontos focais vinculados à AT podem editar; Liderança e
Auditor leem conforme o escopo existente. Gravações usam POST com CSRF e validam
o centro do produto e do material no servidor.

Após salvar, o sistema retorna ao Físico, preserva os filtros e abre o quadro.
HTML exportado e impressão mostram produtos e materiais sem controles de edição.
O CSV próprio inclui Produto, Material, Tipo, Data e URL; produtos sem material
mantêm uma linha com os campos do material vazios.
Não há upload; o servidor não busca os links externos.

## Migração e inicialização

`projects.0003_produtoat_materialprodutoat_and_more` cria as duas tabelas e suas
restrições; `projects.0004_produtos_at_iniciais` popula os centros existentes com
as nove categorias, sem documentos ou URLs fictícios. O evento `post_save` de
novos centros chama o inicializador em transação; fixtures com `raw=True` não
acionam esse preenchimento. `AppConfig.ready()` apenas registra o evento, sem
consultar o banco.

Na implantação, execute `python manage.py migrate` e, em seguida,
`python manage.py sincronizar_produtos_at`. A segunda rotina também cobre
centros criados pela versão anterior durante a atualização, preservando
produtos renomeados, ordenados ou arquivados.

Os produtos não possuem vínculo com projetos, snapshots financeiros ou KPIs.
Reimportações e trocas de acompanhamento do mesmo centro preservam os materiais;
nenhuma operação de cadastro altera metas ou execução física/financeira.

As migrações são aditivas. No Neon, o SQL é gerado pelo backend PostgreSQL do
Django e aplicado por MCP em transação, com conferência de hashes dos registros
financeiros, KPIs, projetos e entregáveis existentes. Evidências e backup local
ficam em `.worktrees/entregaveis-at/`.

## Validação

`python manage.py test apps.projects` inclui catálogo, tipos, permissões, isolamento
entre centros, edição, arquivamento, reimportação e exportação. O cenário Chromium
`produtos da AT` em `tests/e2e/overview_metas.spec.ts` verifica os formulários,
ordenação, filtros, CSV, computador, celular e impressão em banco temporário.
