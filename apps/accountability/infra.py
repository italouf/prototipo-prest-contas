"""Contrato do detalhamento financeiro de Infraestrutura.

A lista é compartilhada pelo parser, pelo modelo, pelo dashboard e pelo
gerador do arquivo REFAT v3. Alterar aqui exige atualizar o template Excel
(comando ``gerar_refat_infra``) e reimportar os acompanhamentos.
"""

CATEGORIAS_INFRA = (
    "Obras civis",
    "Laboratórios e salas técnicas",
    "Equipamentos e instrumentação",
    "TI, Data Center e HPC",
    "Serviços e manutenção",
    "Outros",
)

ABA_INFRA = "db_infra"
NOME_TABELA_PROJETOS_INFRA = "tbl_ProjetosINFRA"
NOME_TABELA_VISAO_INFRA = "tbl_VisaoINFRA"
ORIGEM_PROJETOS_INFRA = "TAB. 10"
ORIGEM_VISAO_INFRA = "TAB. 11"
