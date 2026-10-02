# Contrato de importação financeira REFAT

Novos uploads financeiros usam `mockup/exemplos_arquivos/FINANCEIRO GERAL - REFAT.xlsx`.
O tipo é identificado pelos objetos Table do Excel. O nome do arquivo, os nomes e
a ordem das abas, a posição das tabelas e a ordem das colunas podem mudar.

## Objetos obrigatórios

| Tabela | Dados | Origem persistida |
| --- | --- | --- |
| `tbl_ConsolidadoPrograma` | Consolidados PPI por ação | TAB. 1 |
| `tbl_VisaoGeral` | Consolidados e valores anuais por ação | TAB. 1.1 |
| `tbl_ProjetosPDI` | Projetos PDI | TAB. 2 |
| `tbl_VisaoPDI` | Reconciliação PDI | TAB. 3 |
| `tbl_ProjetosFCRH` | Projetos FORMACAO | TAB. 4 |
| `tbl_VisaoFCRH` | Reconciliação FORMACAO | TAB. 5 |
| `tbl_ProjetosACS` | Projetos STARTUPS | TAB. 6 |
| `tbl_VisaoACS` | Reconciliação STARTUPS | TAB. 8 |
| `tbl_CaptaoATeOutros` | Captação AT e OUTRASFONTES | TAB. 9 |

O nome `tbl_CaptaoATeOutros` é o nome efetivo do objeto no modelo. As origens TAB.*
são identificadores internos para manter a compatibilidade dos acompanhamentos
já importados. O arquivo antigo de aba única é rejeitado em novos uploads.

## Colunas e registros

O registro `TABELAS_FINANCEIRO`, em `apps/accountability/parsers/financeiro_geral.py`,
declara os cabeçalhos funcionais, aliases e tipos. Cabeçalhos são comparados sem
acentos, diferenças de caixa, espaços repetidos ou quebras de linha; qualificadores
de mês podem ser atualizados mantendo o significado e o ano da projeção.

Cada coluna funcional obrigatória deve corresponder a exatamente um cabeçalho.
Cabeçalhos da planilha e metadados Table precisam concordar. Colunas auxiliares,
tabelas adicionais e conteúdo fora dos objetos não alimentam o payload.

- PDI não tem `ITEM`: a sequência permanece nula.
- FCRH e ACS usam `ITEM` quando presente. ACS não exige início do projeto.
- Linhas `TOTAL`, `TOTAL GERAL` e `TOTAL GERAL - ATUAL` são excluídas pelo rótulo
  correspondente. A leitura continua após elas. Linhas de totais nativas são
  excluídas por `totalsRowCount`.
- Valores anuais são originados exclusivamente pelos cabeçalhos de realizado
  2024–2026 e projetado 2026–2027. Zero é um valor informado; vazio é ausência.
- `PROJETADO TOTAL` permanece um valor consolidado, com `ano=None`.
- Nome de projeto duplicado na mesma origem e pilar desconhecido rejeitam o upload.

## Fórmulas e apresentação

O leitor utiliza os resultados de fórmulas salvos no Excel. Erros de fórmula e
fórmulas sem resultado salvo geram valores nulos e avisos com aba, tabela, campo
e célula. Valores preenchidos incompatíveis com o tipo e erros estruturais rejeitam
a importação. Os avisos aparecem no resultado do upload e no histórico.

O dashboard mantém os cálculos gerenciais de saldo, percentual e farol. A tabela
anual inclui `PROJETADO 2027`. Quando o projetado total está ausente, sua apresentação
usa a soma das projeções anuais disponíveis; quando todas estão ausentes, mostra
ausência de dados. O executado anual nunca é inferido das datas dos projetos.

O total PPI é um campo explícito do DTO, independente do índice de uma linha.
Quantidade de projetos é obtida dos registros persistidos por pilar. As tabelas
de reconciliação não entram novamente na soma dos consolidados.

## Dashboards financeiros PDI, Formação FCRH e ACS

Os três pilares compartilham os cards e o layout de visão financeira e projetos.
Seus KPIs usam os respectivos resumos: `TAB. 3` (`tbl_VisaoPDI`), `TAB. 5`
(`tbl_VisaoFCRH`) e `TAB. 8` (`tbl_VisaoACS`). O card de recurso usa o cabeçalho
de cada tabela: `RECURSO PPI AFCCT / PDI`, `RECURSO PPI FCRH` e `TOTAL ACS`.
Os demais cards apresentam realizado, diferença em relação ao PPI e percentual
executado. A diferença é exibida como valor
positivo (módulo), preservando o sinal original no snapshot. Sua barra mostra
essa diferença como percentual do recurso PPI. O card de recurso PPI não
exibe barra nem farol.
O percentual executado continua sendo realizado dividido pelo recurso PPI.
O painel apresenta o ciclo completo, inclusive quando a URL contém um ano.

A visão financeira exibe as seis colunas de cada tabela de resumo. Os projetos
usam as onze colunas de `tbl_ProjetosPDI`, as doze de `tbl_ProjetosFCRH` e as onze
de `tbl_ProjetosACS`, com todos os projetos na ordem de importação. FCRH e ACS
incluem ITEM; ACS não tem início de projeto. O total geral
dos projetos é calculado pela soma dos valores importados, sem incluir linhas
de total na contagem. Cabeçalhos de realizado e projetado usam seus nomes
funcionais, sem fixar o mês de corte no frontend. Ausências aparecem como `—`.
Os downloads HTML e CSV incluem as duas tabelas.

O gráfico anual, o detalhamento anual e a prestação mensal não são exibidos
nessa visão. O bloco de quantidade de projetos não é exibido nesses três pilares.

## Atualização do arquivo e reimportação

Inclua novos projetos dentro da tabela correspondente, confirmando que o Excel
expandiu o objeto. Recalcule e salve as fórmulas antes de enviar. Os valores dos
consolidados vêm de suas respectivas tabelas; alterações nos projetos precisam
estar refletidas nos resultados salvos do documento.

Reimporte com o mesmo centro e período para substituir o snapshot financeiro.
Reenvios não duplicam fatos; projetos removidos do objeto saem do snapshot.
Outras fontes e overrides são preservados. Falhas de gravação restauram os fatos
anteriores e registram o erro no histórico.

O modelo corrigido de referência produz 13 resumos e 33 projetos: 18 PDI,
8 FCRH e 7 ACS. O recurso PPI soma R$ 60.000.000,00; o realizado PPI soma
R$ 34.975.229,95. Campos anuais vazios geram aviso de indisponibilidade.

## Validação

Executar `python manage.py test apps.accountability --noinput`. A suíte inclui o
arquivo real, mudanças de aba e posição, inversão de colunas, expansão de tabelas,
inclusão/remoção de projetos, lacunas e fórmulas inválidas, rejeição do formato
antigo, valores anuais de 2027, HTML exportado, isolamento, overrides e rollback.
