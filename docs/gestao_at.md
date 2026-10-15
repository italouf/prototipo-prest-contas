# Gestão da AT e áreas operacionais

O arquivo `mockup/SIG_QuIIN_5.html` é somente referência e não é carregado pela aplicação.

## Rotas

- `/gestao-at/associados/` e `/gestao-at/acompanhamento/`: carteira, planos, vigência e utilização.
- `/gestao-at/associados/<id>/`: cotas e benefícios do associado.
- `/gestao-at/solicitacoes/`: filtros, prazo e atendimento por responsável técnico.
- `/lancamentos/<periodo>/<pilar>/`: formulário mensal e importação operacional.
- `/aprovacao/<periodo>/`: quadro de validação e histórico.
- `/auditoria/` e `/auditoria/exportar.csv`: trilha real e exportação filtrada.
- `/talentos/organograma/`: formação, competências, carga semanal e alocações.

As URLs de prestação mensal/semestral, relatórios mensais e CRM continuam registradas. Exibem o aviso de construção. A implementação anterior está preservada nas funções com sufixo `_legado` e em `FunilATLegadoView`. O Admin continua em `/admin/`.

## Regras

Master/Admin gerenciam a carteira. Pontos focais vinculados ao pilar AT também podem cadastrar associados, registrar pedidos e atualizar benefícios. Técnicos dos outros pilares acompanham solicitações destinadas aos pilares a que têm acesso. Liderança e Auditor têm acesso de leitura conforme os vínculos existentes.

Uma solicitação passa por Recebida, Encaminhada, Em andamento, Respondida e Concluída. É possível responder diretamente, mas não regredir o atendimento. A primeira resposta exige texto e fixa sua data; observações posteriores não alteram o tempo de resposta. Acima de dez dias corridos sem resposta, o pedido é destacado. O registro de resposta não envia e-mail.

O uso de benefícios é limitado às cotas do plano. Percentuais de utilização consideram a média das cotas quantitativas; planos sem cotas consideram estudos e grupos de trabalho. Vigência, reuniões e usos iniciais estão identificados como demonstrativos.

Enviados/aprovados não podem ser alterados pelo formulário de lançamento. Devolução exige justificativa. Escritas operacionais e revisões usam transações e bloqueios para preservar a sequência. Importações operacionais aceitam XLSX ou CSV UTF-8, com cabeçalho `codigo;valor;comentario`, dentro do período e pilar autorizados, e gravam rascunhos.

Alocações não podem ultrapassar as horas disponíveis nas datas sobrepostas. Remover um colaborador arquiva seu cadastro, preservando a trilha e suas alocações.

## Dados e deploy

`apps/gestao_at/data/prototipo.json` guarda os dados extraídos do guia. A migração `gestao_at.0002` cria seis planos, 13 associados e oito solicitações, com seus benefícios e históricos. Complementa a formação dos três talentos demonstrativos existentes. Não substitui cadastros ou atendimentos já editados.

O build do Render aplica `python manage.py migrate` e coleta os novos estáticos. Não executar `seed_demo` em produção: esse comando antigo usa `update_or_create` em dados que já podem ter sido alterados. Para completar apenas os dados novos de AT, há `python manage.py seed_prototipo_at`, que preserva as edições.

As migrações `audit.0002/0003`, `talentos.0002/0003` e `gestao_at.0001/0002` são aditivas. Os campos acrescentados a tabelas existentes têm defaults no banco para compatibilidade durante a troca de versão. A aplicação usa `DATABASE_URL` para PostgreSQL e SQLite quando ela não está definida.

O Blueprint `render.yaml` conserva o serviço e o comando de inicialização existentes e adiciona `/health/` como verificação de disponibilidade.

O release deve incluir as migrações, JSON, templates e estáticos novos. Também deve incluir os arquivos dos dashboards dos pilares que ainda estavam fora do controle de versão ao iniciar esta alteração. O HTML de referência e a remoção do mockup anterior não são necessários ao runtime.
