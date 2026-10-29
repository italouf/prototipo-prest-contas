# Manual de operação — Lançamentos e aprovação de resultados

**Sistema:** SIG QuIIN  
**Público:** pontos focais, Master/Admin e responsáveis pelo acompanhamento dos resultados  
**Versão:** 1.0 — 29/10/2026

## 1. Para que serve esta área

A área **Operação → Lançamentos** registra propostas de atualização dos resultados apresentados em **Visão Geral** e nos dashboards dos pilares.

O fluxo habitual é:

**Preencher → salvar rascunho ou enviar para análise → revisar → aprovar → atualizar os dashboards.**

Salvar ou enviar uma proposta não altera os resultados oficiais. A publicação ocorre após a aprovação por Master/Admin. Esses perfis também podem realizar um ajuste direto, com justificativa obrigatória.

O catálogo de lançamentos utiliza os indicadores atuais dos dashboards. Os lançamentos do sistema legado deixaram de ser utilizados nessa operação.

## 2. O que cada perfil pode fazer

| Atividade | Ponto focal | Master/Admin | Liderança / Auditor |
| --- | --- | --- | --- |
| Consultar dashboards | Conforme os pilares autorizados | Sim | Conforme as permissões de consulta |
| Preencher e salvar propostas | Apenas nos pilares autorizados | Sim | Não |
| Enviar propostas para análise | Apenas nos pilares autorizados | Sim | Não |
| Aprovar ou devolver propostas | Não | Sim | Não |
| Publicar ajuste direto justificado | Não | Sim | Não |
| Confirmar ou conciliar a base inicial | Não | Sim | Não |
| Cadastrar projetos financeiros de AT/Outras Fontes | Não | Sim | Não |

A consulta à auditoria é disponibilizada a Master/Admin e Auditor. O perfil Auditor não possui acesso ao painel operacional de aprovação.

## 3. Conceitos necessários antes de lançar

### Acompanhamento, competência e mês da apresentação

| Termo | Significado | Exemplo |
| --- | --- | --- |
| **Acompanhamento** | Conjunto de dados importados que será atualizado pela operação | Acompanhamento QuIIN selecionado no filtro |
| **Competência do lançamento** | Mês ao qual o resultado informado se refere | `10/2026` para os resultados até outubro |
| **Competência de corte** | Referência dos valores que já estavam na base quando a operação foi iniciada | `09/2026` se o histórico confirmado vai até setembro |
| **Mês da apresentação mensal** | Mês em que a prestação de contas é apresentada | `11/2026`, apresentando a competência anterior, `10/2026` |

**Exemplo da rotina mensal:** ao preparar a prestação de novembro de 2026 com os dados de outubro, registre os resultados na competência **10/2026**. O mês da apresentação continua sendo **11/2026**.

O nome ou rótulo do acompanhamento, por si só, não confirma até qual mês seus valores estão atualizados. Por isso, a competência de corte precisa ser conferida pelo gestor.

### Base inicial

A base inicial preserva os resultados importados e os ajustes existentes no momento da confirmação. Ela é o ponto de partida dos lançamentos e possui uma versão identificada na tela.

Confirmar essa base não significa cadastrar novamente os resultados históricos.

### Acumulado vigente e novo acumulado

**Todos os lançamentos devem informar o total acumulado desde o início do ciclo 2024–2027 até a competência escolhida.**

Não preencha apenas o movimento do mês e não some outra vez o acumulado anterior.

| Situação | Acumulado vigente | Ocorrido no mês | Novo acumulado a informar |
| --- | --- | --- | --- |
| Quantidade de projetos | 15 | Mais 3 projetos | **18** |
| Realizado de um projeto | R$ 100.000,00 | Mais R$ 20.000,00 executados | **120000,00** |
| Captação de um projeto da AT | R$ 200.000,00 | Mais R$ 50.000,00 captados | **250000,00** |
| Indicador percentual | 0,51% | Aumento de 0,09 ponto percentual | **0,60** |

Se o resultado não mudou, seu acumulado permanece igual. O sistema não soma os valores acumulados dos diferentes meses.

## 4. Primeiro acesso — configuração por Master/Admin

Esta etapa deve ser realizada antes de começar a rotina de propostas para o acompanhamento selecionado.

1. Acesse **Operação → Lançamentos**.
2. Selecione o **Acompanhamento** correto e clique em **Filtrar**, quando necessário.
3. Na tela **Confirmar a base de resultados**, informe a **Competência de corte dos dados importados**.
4. Informe a **Competência inicial de lançamento**, igual ou posterior ao corte.
5. Registre uma justificativa que identifique a referência conferida, quando pertinente.
6. Clique em **Confirmar base inicial**.

**Exemplo:** histórico confirmado até `09/2026`; primeira atualização mensal em `10/2026`.

Se a competência inicial ainda não existir, a configuração a cria e a abre. Se ela já existir, confira seu estado: a confirmação da base não substitui a reabertura de uma competência fechada. A gestão de períodos cabe a Master/Admin.

Sem a confirmação da base, o ponto focal deve solicitar essa configuração ao gestor. Os dashboards continuam utilizando os dados importados enquanto a operação não é ativada.

## 5. O que pode ser lançado

| Área | Resultados disponíveis para lançamento |
| --- | --- |
| **Físico** | Indicadores do PE presentes nos dashboards, conforme o pilar e a unidade |
| **Financeiro — PD&I, FCRH e ACS** | Realizado acumulado de cada projeto financeiro disponível no catálogo |
| **Financeiro — Infraestrutura** | Realizado acumulado do pilar |
| **Financeiro — AT e Outras Fontes** | Captado e realizado acumulados por projeto da carteira financeira própria |
| **Indicadores percentuais de recursos** | Indicadores PE-02 e PE-04, disponíveis na base financeira |

**Publicações PE-09:** o lançamento é uma quantidade inteira de publicações. Sua exclusão dos agregados físicos atuais de PD&I foi preservada; portanto, atualizar esse indicador não significa aumentar o agregado de projetos e pedidos de PI.

Metas, orçamentos e projeções permanecem no fluxo de planejamento/administração. Eles não são cadastrados como resultados mensais nesta área.

## 6. Como localizar um indicador ou projeto

1. Acesse **Operação → Lançamentos**.
2. Confira o acompanhamento e selecione a **Competência**.
3. Escolha a **Base de análise**: Física, Financeira ou Todas.
4. Escolha o **Pilar** autorizado.
5. Se necessário, preencha **Buscar projeto ou indicador**.
6. Clique em **Filtrar**.

A tabela apresenta:

| Coluna | Como interpretar |
| --- | --- |
| **Projeto / indicador** | Item que será atualizado e seu pilar |
| **Base / unidade** | Natureza do lançamento: quantidade, percentual ou valor em reais |
| **Acumulado vigente** | Resultado oficial disponível para a competência consultada |
| **Última proposta** | Valor da revisão mais recente daquela competência, que pode ainda não estar aprovado |
| **Status** | Situação da proposta mais recente |
| **Ação** | Acesso a **Lançar / corrigir** |

O catálogo possui paginação de 25 indicadores. Use **Anterior** e **Próxima** quando o item não estiver na primeira página.

Também é possível iniciar a atualização a partir dos dashboards pelos atalhos **Propor atualização**, para ponto focal, ou **Ajustar resultados**, para gestor.

## 7. Como preencher e salvar um lançamento

1. Localize o item e clique em **Lançar / corrigir**.
2. Confira o nome, o pilar, o acompanhamento e a competência apresentados.
3. Leia o **Acumulado vigente**.
4. Preencha **Novo acumulado do ciclo** com o total atualizado até aquela competência.
5. Preencha **Comentário / justificativa de correção** com a explicação do resultado e a referência de conferência, quando houver.
6. Escolha **Salvar rascunho** ou **Enviar para análise**.

### Formato dos valores

| Tipo | Como preencher | Exemplo |
| --- | --- | --- |
| Quantidade | Número inteiro, sem unidade | `18` |
| Monetário | Valor em reais, sem `R$`, preferencialmente sem separador de milhar | `125000,50` |
| Percentual | Percentual como aparece para o usuário, sem `%` | `0,51` significa **0,51%** |

Para valores monetários, utilize no máximo duas casas decimais. Quantidades não aceitam frações. Valores negativos não são aceitos.

Uma redução do acumulado exige justificativa. Por exemplo: corrigir de `18` para `17` requer explicar o motivo da retificação.

### Qual botão utilizar

| Botão | Efeito |
| --- | --- |
| **Salvar rascunho** | Guarda o preenchimento para continuar depois; não publica o resultado |
| **Enviar para análise** | Encaminha a proposta ao gestor e bloqueia sua edição enquanto aguarda revisão |
| **Publicar ajuste direto** | Disponível a Master/Admin; publica uma revisão aprovada com justificativa obrigatória |

O envio é feito por indicador ou projeto. Salvar um item não envia automaticamente os demais.

## 8. Status e possibilidade de edição

| Status | Significado | Próximo passo |
| --- | --- | --- |
| **Sem proposta** | Ainda não existe proposta para o item naquela competência | Preencher o lançamento |
| **Rascunho** | Preenchimento salvo, ainda não enviado | Revisar e enviar para análise |
| **Enviado / Em análise** | Proposta aguardando decisão do gestor | Aguardar aprovação ou devolução; a edição fica bloqueada |
| **Devolvido** | Gestor solicitou correção e registrou o motivo | Ler a justificativa, corrigir e reenviar |
| **Aprovado** | Resultado homologado e disponível para os leitores oficiais | Se houver erro, criar uma nova revisão |

Uma competência fechada impede novos salvamentos e aprovações, mesmo que a proposta tenha sido preenchida anteriormente.

## 9. Como revisar e aprovar — Master/Admin

1. Acesse **Operação → Aprovação**.
2. Confira a competência e o acompanhamento.
3. Utilize os filtros de pilar, base de análise e busca para localizar a proposta.
4. Na coluna **Em análise**, clique em **Revisar proposta**.
5. Compare **Acumulado vigente**, **Proposto** e **Variação no resultado**.
6. Confira o comentário e o histórico disponível.
7. Escolha **Aprovar e publicar** ou **Devolver com justificativa**.

**Para aprovar:** clique em **Aprovar e publicar**. Após a confirmação, o resultado passa a alimentar os dashboards e as exportações correspondentes.

**Para devolver:** preencha **Justificativa para devolução** e clique em **Devolver com justificativa**. Especifique o que deve ser corrigido para que o ponto focal consiga reenviar a proposta.

Exemplo de justificativa: “O acumulado inclui duas publicações ainda não confirmadas. Ajustar a quantidade e informar a referência de conferência.”

Se o valor vigente ou a versão da base tiver mudado desde o envio, o sistema bloqueia a aprovação automática. Nesse caso, devolva a proposta para que ela seja revisada e reenviada com a referência atual.

### Navegação do painel de aprovação

O painel possui quatro colunas: **Em análise**, **Devolvidos**, **Rascunhos** e **Aprovados**.

- Cada coluna consulta até dez registros por página.
- Use **Anterior** e **Próxima** na própria coluna.
- A rolagem dos cartões ocorre dentro da coluna, evitando uma página excessivamente longa.
- **Aprovados** começa recolhida; clique em **Expandir** para consultar os registros e em **Recolher** para ocultá-los.
- No celular, selecione a aba do status desejado.
- Use **Fechar** ou a tecla **Esc** para fechar o diálogo de revisão.

Aprovar e devolver são ações explícitas nos detalhes da proposta. Arrastar um cartão não realiza essas operações.

## 10. Como corrigir uma proposta devolvida ou um resultado aprovado

### Proposta devolvida

1. Consulte o motivo da devolução no painel ou nos detalhes do lançamento.
2. Acesse **Operação → Lançamentos**, mantendo a competência e o acompanhamento corretos.
3. Clique em **Lançar / corrigir**.
4. Atualize o acumulado e o comentário.
5. Clique em **Enviar para análise** novamente.

O resultado oficial permanece inalterado até a nova aprovação.

### Resultado já aprovado

1. Localize o mesmo item na competência que precisa de correção.
2. Clique em **Lançar / corrigir**.
3. Informe o acumulado correto e explique a retificação.
4. Envie para análise, ou utilize o ajuste direto se for Master/Admin e houver justificativa.

O sistema cria uma nova revisão. A revisão aprovada anterior permanece registrada no histórico.

Se a competência estiver fechada, solicite sua reabertura justificada ao gestor antes de tentar corrigir.

**Atenção às competências posteriores:** corrigir um mês antigo não substitui o acumulado de um mês posterior já aprovado. Se a correção também afetar meses seguintes, confira e retifique as competências correspondentes.

## 11. Projetos financeiros de AT e Outras Fontes

A carteira financeira é independente dos **Produtos da AT**, dos materiais e dos entregáveis. Cadastrar um produto ou adicionar um relatório à biblioteca não cria um projeto financeiro.

### Cadastro e valores de abertura — Master/Admin

1. Em **Operação → Lançamentos**, selecione o acompanhamento correto.
2. Clique em **Cadastrar projeto financeiro de AT/Outras Fontes**.
3. Selecione a **Fonte**: AT ou Outras Fontes.
4. Informe o **Nome do projeto**.
5. Informe **Captado acumulado na abertura (R$)** e **Realizado acumulado na abertura (R$)**, referentes ao histórico da base confirmada.
6. Clique em **Cadastrar projeto e abertura**.

Para um projeto iniciado depois do corte da base, informe explicitamente zero nos valores de abertura que ainda não existiam naquela referência. Valores já realizados ou captados após o corte deverão ser lançados na competência correspondente.

Para um projeto que já existia na data de corte, confira seus valores históricos antes do cadastro. A abertura não pode exceder o saldo histórico disponível da fonte.

### Por que o cadastro não aumenta o total da fonte

O cadastro distribui um histórico que já estava contabilizado no consolidado.

**Exemplo:** a AT possui R$ 1.000.000,00 captados na base. Ao cadastrar um projeto com abertura de R$ 200.000,00:

| Composição após o cadastro | Valor |
| --- | --- |
| Projeto cadastrado | R$ 200.000,00 |
| Saldo histórico ainda não distribuído | R$ 800.000,00 |
| **Total captado da AT** | **R$ 1.000.000,00** |

Depois, se o captado desse projeto passar para R$ 250.000,00 e a atualização for aprovada, o total da fonte passa para **R$ 1.050.000,00**. O impacto é de R$ 50.000,00.

O quadro **Carteira financeira · AT e Outras Fontes** apresenta os projetos e a parcela de **Saldo histórico não distribuído**.

## 12. Como os dashboards são atualizados

### Indicadores físicos e percentuais

O resultado homologado do indicador passa a ser utilizado nos respectivos quadros e cálculos. Metas, saldos, percentuais de execução e faróis seguem as regras de cada dashboard.

### Realizado financeiro por projeto

A aprovação atualiza o realizado do projeto e seu impacto no pilar e nos consolidados correspondentes. O sistema considera a diferença entre o novo acumulado do projeto e sua abertura histórica para evitar dupla contagem.

**Exemplo:** projeto com abertura de R$ 100.000,00 passa para R$ 120.000,00. O consolidado aumenta R$ 20.000,00.

### Ordem de prevalência dos resultados

A posição atual utiliza a competência aprovada mais recente. Dentro dessa competência, utiliza a revisão aprovada mais recente. Sem aprovação aplicável, permanece a referência da base inicial, quando disponível.

Uma proposta nova em rascunho ou em análise não substitui uma revisão já aprovada.

### Consultas mensais, anuais e apresentação

Consultas mensais operacionais apresentam a posição acumulada até o mês final selecionado, conforme a referência disponível. Isso não representa automaticamente apenas o movimento daquele mês.

A execução anual só é calculada quando existem referências históricas suficientes. Um campo sem referência pode aparecer como **—**; isso não significa zero.

Os resultados homologados também alimentam as exportações e os números da apresentação mensal vinculada ao mesmo acompanhamento. A apresentação utiliza dados vivos: selecionar seu mês não congela os números. Confira o acompanhamento e a referência dos dados antes de apresentar ou exportar.

## 13. Reimportação e conciliação da base — Master/Admin

Uma reimportação não apaga os resultados operacionais aprovados nem substitui automaticamente a abertura confirmada.

Use **Conciliar base** quando for necessário conferir uma nova referência importada ou incorporar alterações na abertura do catálogo.

1. Confira os dados da fonte oficial e conclua a importação necessária.
2. Acesse **Operação → Lançamentos** e selecione o acompanhamento.
3. Clique em **Conciliar base**.
4. Informe as competências de corte e inicial compatíveis com a referência conferida.
5. Preencha a justificativa obrigatória da conciliação.
6. Clique em **Conciliar base** para confirmar.
7. Revise as propostas pendentes que tenham sido preparadas na versão anterior.

A conciliação cria uma nova versão da base e registra a alteração na auditoria. Resultados já aprovados continuam prevalecendo. Propostas enviadas que ficaram desatualizadas devem ser devolvidas e reenviadas antes de serem aprovadas.

A conciliação é uma configuração da referência dos dados; ela não precisa ser executada a cada lançamento mensal.

## 14. Dúvidas e situações frequentes

| Situação | Como proceder |
| --- | --- |
| A tela pede confirmação da base | Solicite a configuração inicial a Master/Admin |
| Não encontro o indicador | Confira acompanhamento, pilar, base, busca e paginação; o catálogo contém os itens atuais dos dashboards |
| AT/Outras Fontes não apresenta projetos financeiros | Solicite ao gestor o cadastro da carteira financeira própria |
| O campo está bloqueado depois do envio | Aguarde a revisão; se precisar corrigir, solicite a devolução ao gestor |
| O período está fechado | Solicite reabertura justificada ao gestor |
| A competência é anterior ao corte da base | Confira o mês selecionado; uma referência histórica anterior exige análise e conciliação pelo gestor |
| O acumulado diminuiu e o sistema exige justificativa | Explique a correção no comentário antes de salvar ou enviar |
| A aprovação informa que o valor vigente mudou | Devolva a proposta e peça a revisão com a referência atual |
| O projeto tem execução histórica indisponível | Confirme a abertura na planilha oficial e solicite importação/conciliação; o sistema não presume zero |
| A abertura do projeto excede o saldo da fonte | Confira os valores históricos e as distribuições já realizadas; solicite conciliação se necessário |
| Salvei ou enviei, mas o dashboard não mudou | Confira o status: somente aprovação ou ajuste direto publicado altera o resultado oficial |
| Foi aprovado, mas continuo vendo outro valor | Confira acompanhamento, filtros, competência e eventuais aprovações posteriores; atualize a consulta |
| A quantidade de publicações mudou, mas o agregado de PD&I não | PE-09 possui linha própria e permanece excluído do agregado físico atual de PD&I |
| O detalhamento anual mostra **—** | Falta referência histórica suficiente; não interprete esse campo como zero |

## 15. Roteiro de conferência mensal

### Ponto focal

1. Confirmar acompanhamento, competência, pilar e base de análise.
2. Conferir o acumulado vigente e o total atualizado até o mês de competência.
3. Preencher os itens necessários e explicar correções.
4. Enviar cada proposta para análise.
5. Acompanhar devoluções e reenviar os itens corrigidos.

### Master/Admin

1. Confirmar que a competência está aberta e a base está adequada à operação.
2. Filtrar e revisar as propostas em análise.
3. Aprovar os itens conferidos ou devolver com orientação objetiva.
4. Conferir os resultados publicados nos dashboards do mesmo acompanhamento.
5. Validar a referência dos dados utilizados na prestação mensal e nas exportações.
6. Encerrar a competência pelo fluxo de gestão de períodos, quando a conferência estiver concluída.

## Referência complementar

Para detalhes de implementação, integridade, migração e backups, consulte [Operação de resultados dos dashboards](operacao-resultados.md).
