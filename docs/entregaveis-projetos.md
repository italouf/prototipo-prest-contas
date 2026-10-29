# Entregáveis dos projetos

O dashboard utiliza agora resumo por projeto e páginas de consulta paginadas.
Consulte [Consulta de materiais](consulta-materiais.md) para os fluxos de busca,
biblioteca, retorno contextual e relatórios completos.

O quadro existe exclusivamente no Físico de PDI, FCRH e ACS, entre a visão
gerencial e o detalhamento anual. Mostra a carteira completa de projetos
ativos do centro e pilar selecionados, independentemente das datas dos KPIs.
Trocar de acompanhamento dentro do mesmo centro mantém essa carteira.

## Cadastros e identidade

`apps.projects.Projeto` tem UUID permanente e referências ao centro de
competência e pilar. O nome normalizado (Unicode NFKC, casefold, espaços
consolidados) é único dentro desse escopo, inclusive entre arquivados.
O código EMBRAPII é opcional e informativo: números de sequência presentes
no arquivo não são identidade confiável para associar documentos.

`ReferenciaImportacaoProjeto` guarda centro, pilar, origem e nome normalizado
do arquivo. A importação resolve primeiro essa referência; na ausência,
reutiliza um cadastro com o mesmo nome normalizado ou cria um projeto.
`ProjetoFinanceiro.projeto` aponta para o cadastro permanente. Apagar e
recriar snapshots financeiros não apaga materiais, projetos ou referências.
Renomear o cadastro físico não altera suas referências anteriores.

Um nome novo na origem não é associado por semelhança. Em **Gerenciar projetos
e materiais**, o responsável pode associar a referência importada ao cadastro
correto no mesmo centro e pilar. Essa ação atualiza o vínculo nos snapshots
existentes e nas futuras importações, sem transferir os materiais do cadastro
anterior. O cadastro anterior pode ser arquivado separadamente.

Projetos podem ser cadastrados no Físico antes da inclusão no financeiro.
Quando o nome correspondente aparecer na importação, o cadastro será reutilizado.

## Materiais e Book

`MaterialProjeto` pertence a um único projeto: título, tipo, URL HTTP/HTTPS e
data opcional. Os tipos são artigo, relatório técnico, material de formação,
certificado, protótipo/demonstração, software/repositório e outro.

`BookPrograma` pertence ao centro, com apenas uma versão vigente, garantida
por índice único parcial no banco. Publicar um Book cria uma versão e arquiva
a anterior em transação, com bloqueio do centro. O histórico permite arquivar
ou tornar uma versão anterior vigente. Todos os projetos dos três pilares,
inclusive novos, herdam o Book por consulta ao centro; não há cópias por projeto.

Links abrem em nova aba e não são buscados pelo servidor. Arquivos continuam
hospedados no serviço escolhido pelo responsável; não há upload nesta versão.
Nenhum dado fictício é criado. Ausência de data, material ou Book é explícita.
Cadastrar documentos não modifica metas, executado ou percentuais de KPIs.

## Permissões e rotas

Rotas HTML ficam sob `/projetos/pilar/<pilar_pk>/`, com formulários GET e gravações
POST com CSRF. O acompanhamento selecionado acompanha a query string e determina
o centro. Os retornos preservam datas e abrem o quadro no Físico.

Master/Admin gerenciam todos os cadastros. PontoFocal gerencia projetos,
materiais e associações nos pilares autorizados; só Master/Admin publicam e
alteram a vigência do Book geral. Liderança e Auditor têm leitura conforme o
escopo existente. Views validam centro e pilar dos objetos, além do perfil.

Criação, edição, associação, arquivamento e reativação ficam em `AuditLog`.
Arquivamentos são reversíveis e não excluem documentos.

HTML exportado e impressão incluem o quadro sem controles de edição. O CSV
próprio em `entregaveis.csv` repete o projeto por material, mantém linhas dos
projetos sem materiais e inclui o Book vigente. O CSV de indicadores é preservado.

## Migração e operação

A sequência é `projects.0001_initial`,
`accountability.0007_projetofinanceiro_projeto` e
`projects.0002_vincular_catalogo`. A FK é anulável para compatibilidade com a
versão anterior durante implantação. O preenchimento inicial preserva todos
os campos preexistentes dos snapshots.

Execute `python manage.py migrate` na implantação. Caso a versão anterior
tenha recebido importações entre a migração e a publicação do código, execute
`python manage.py sincronizar_catalogo_projetos`. O comando é idempotente e
preenche apenas vínculos ausentes, sem alterar números ou datas financeiras.

No Neon, o esquema foi gerado pelo backend PostgreSQL do Django e aplicado
por MCP em transação, junto dos vínculos e registros de migração. A operação
confere o hash dos campos financeiros antes e depois, revertendo em caso de
divergência. Evidências e backup local ficam em `.worktrees/entregaveis/`.

Validação: `python manage.py test apps.projects`. O fluxo Chromium está em
`tests/e2e/overview_metas.spec.ts`, cenário `entregáveis físicos`, usando banco
temporário. As verificações cobrem reimportação, remoção de snapshots,
identidade, Book compartilhado, autorização, datas, links, auditoria e exportação.
