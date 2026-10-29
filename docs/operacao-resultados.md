# Operação de resultados dos dashboards

## Ativação

Após `python manage.py migrate` e `collectstatic`, Master/Admin acessa **Operação → Lançamentos** e confirma o acompanhamento, a competência de corte dos números importados e a primeira competência de lançamento. Essa referência é deliberadamente manual: o rótulo do arquivo não garante a data dos valores acumulados. Sem essa confirmação, os dashboards continuam usando os dados importados e não aceitam propostas operacionais.

O catálogo contém somente indicadores PE presentes nos dashboards, realizados de projetos PPI com identidade permanente e o realizado de Infraestrutura. AT e Outras Fontes possuem uma carteira financeira independente, cadastrada pelo gestor, com captado e realizado por projeto. Produtos, materiais e entregáveis da AT não participam dessa carteira. PE-09 é quantidade de publicações, preservando sua exclusão atual dos agregados físicos de PD&I. PE-02 e PE-04 aparecem na base financeira.

## Propostas e publicação

Ponto focal lança apenas em seus pilares. Rascunho e proposta enviada não alteram resultados oficiais. O envio bloqueia a edição; a devolução exige justificativa e permite correção. Master/Admin aprova uma proposta enviada ou publica um ajuste direto justificado. Cada correção de um resultado já aprovado cria outra revisão, preservando a anterior. Períodos fechados impedem escrita e aprovação. Aprovação, conciliação, abertura da carteira e fechamento são transacionais; fechamento e publicação compartilham a trava do período.

Os valores informados são acumulados desde o início do ciclo. A posição oficial usa a aprovação da competência mais recente e, dentro dela, a revisão mais recente. Uma aprovação de mês anterior não substitui uma competência posterior. Aprovar a mesma revisão novamente não reaplica seu impacto. Se a base ou o valor de referência mudar desde o envio, a aprovação é bloqueada até devolução e revisão.

O quadro de aprovação consulta dez registros por coluna, com paginação independente e rolagem interna de até 60dvh. Aprovados começam recolhidos e seus registros só são consultados ao expandir. Filtros e páginas seguem na navegação e nas ações de revisão; expansão e aba móvel são lembradas por usuário/competência. A revisão abre em diálogo acessível por teclado, com alternativa de página completa. Não há aprovação por arraste.

## Integridade e leitura

`BaseOperacional.snapshot` preserva a abertura, ajustes existentes, totais e referências anuais. Cada conciliação incrementa a versão e registra os retratos anterior e novo na auditoria. A reimportação preserva essa base e as revisões; novos resultados só entram após conciliação explícita. Chaves de projetos PPI usam o UUID permanente de `projects.Projeto`, não a linha temporária do Excel.

Nos valores financeiros consolidados, aplica-se `total de abertura + soma(realizado aprovado do projeto − abertura do projeto)`. Assim, o acumulado não é somado novamente a cada mês. A abertura de projetos de AT/Outras Fontes distribui o histórico, limitada ao saldo da fonte; a parcela ainda não distribuída aparece separadamente. Cadastrar a carteira não aumenta o total. Um projeto já cadastrado pode ser vinculado a outro acompanhamento com sua abertura explicitamente informada.

`apps.entries.effective` é o leitor compartilhado pelos painéis, tabelas de projetos, apresentação mensal e exportações. O cache existe apenas durante a requisição e é invalidado nas mutações. Consultas mensais exibem a posição acumulada até o fim selecionado. A execução anual só é derivada quando existem referências suficientes; ausência permanece `None`. Não se rateia o acumulado por mês.

Projeto PPI com execução histórica desconhecida exige confirmação da abertura na fonte oficial e conciliação antes do lançamento. Isso evita aprovar uma atualização sem conseguir calcular seu impacto no consolidado. Zero é aceito quando explicitamente confirmado na fonte, inclusive para projetos futuros.

## Limpeza executada em 29/10/2026

Foram removidos 45 lançamentos legados locais e 44 no Neon (`quiin-prod`, branch principal, banco `quiin`). A tabela nova de propostas começa vazia. Os indicadores legados permanecem como referência histórica, sem escrita pelas rotas públicas ou pelo admin de lançamentos. A migração `entries.0002` foi aplicada nos dois bancos.

Backups JSON fora do Git, em `.worktrees/operation-backups/`:

- Local: `local-20261029T195038-3480f23097e3.json` (SHA256 inicia `3480f23097e3`).
- Neon: `neon-legacy-before-retrofit-20261029.json` (SHA256 `c788376430a86c076e6c5dad2eda364d61eb462770493002a00feaa868047ee6`).

A limpeza local usa `limpar_lancamentos_legados`: sem argumentos apenas inventaria; execução exige `--executar --confirmar-quantidade N`, verifica o backup antes de excluir e compara os hashes das tabelas de accountability, projects e planning. No Neon, a mesma exclusão foi executada pelo MCP em uma transação, verificando os 44 registros do backup, os hashes de 15 tabelas preservadas e as auditorias originais. Eventos novos de login também foram preservados. Ambas as limpezas geraram auditoria.

O script `scripts/operation_postgres_sql.py` gera o DDL PostgreSQL da migração sem conectar ao banco. Em deploys posteriores, `migrate` reconhece a migração já aplicada e executa normalmente os eventos `post_migrate`.

## Validação

- Testes de serviço, autorização, concorrência lógica, revisões, reimportação, paridade inicial, consolidação por projeto, percentuais, anualização, competência mensal, exportações e limpeza: `manage.py test apps.entries.tests_operational`.
- Navegação, fluxo ponto focal → gestor, diálogo, paginação e versão móvel em banco temporário: `npx playwright test --config=playwright.operation.config.ts`.
- Os testes antigos em `apps.entries.tests`, `apps.core.tests` e parte de `tests_navegacao` já apresentavam erros de fixtures duplicadas e expectativas de telas desativadas no código anterior. A comparação do conjunto de 39 testes reproduziu os mesmos 31 erros no commit anterior. Os logs de diagnóstico estão em `.worktrees/`.
