"""Esquema inicial: as 20 tabelas das fases 0 a 3.

Revisão: 0001
Anterior: (nenhuma)
Criada em: 2026-11-17

Esta revisão é diferente das próximas porque precisa servir a dois tipos de banco:

- banco vazio: cria tudo;
- banco criado ANTES do Alembic (create_all + lista de ALTER TABLE que vivia em
  app/database.py): cria só as tabelas que faltam e acrescenta as colunas que
  vieram depois — exatamente o que a subida antiga fazia.

Por isso cada tabela, índice e coluna é conferido antes de ser criado. Depois
desta revisão o banco está no mesmo estado, venha de onde vier, e as revisões
seguintes podem ser comuns (geradas por `alembic revision --autogenerate`).

As definições estão congeladas aqui de propósito, sem importar app/models*.py:
uma migração descreve o esquema do momento em que foi escrita, e os models vão
continuar mudando.
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _fk(coluna: str, alvo: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([coluna], [alvo])


def _dinheiro() -> sa.Numeric:
    return sa.Numeric(precision=14, scale=2)


def _aliquota() -> sa.Numeric:
    return sa.Numeric(precision=6, scale=4)


def _tabelas() -> list:
    """Definições novas a cada chamada: um sa.Column só pode pertencer a uma tabela."""
    # Ordem respeita as chaves estrangeiras: quem é referenciado vem antes.
    return [
        ("contratos", [
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("numero", sa.String(), nullable=False),
            sa.Column("objeto", sa.String(), nullable=False),
            sa.Column("contratada_razao_social", sa.String(), nullable=False),
            sa.Column("contratada_cnpj", sa.String(), nullable=False),
            sa.Column("vigencia_inicio", sa.Date(), nullable=False),
            sa.Column("vigencia_fim", sa.Date(), nullable=False),
            sa.Column("mao_de_obra_exclusiva", sa.Boolean(), nullable=False),
            sa.Column("valor_global", _dinheiro(), nullable=False),
            sa.Column("modalidade", sa.String(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        ]),
        ("parametros_faixas_inss", [
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("ordem", sa.Integer(), nullable=False),
            sa.Column("limite_superior", _dinheiro(), nullable=False),
            sa.Column("aliquota", _aliquota(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("ordem"),
        ]),
        ("parametros_gerais", [
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("percentual_fgts", _aliquota(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        ]),
        ("membros_equipe", [
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("contrato_id", sa.Integer(), nullable=False),
            sa.Column("nome", sa.String(), nullable=False),
            sa.Column("matricula_cargo", sa.String(), nullable=False),
            sa.Column("lotacao", sa.String(), nullable=False),
            sa.Column("data_designacao", sa.Date(), nullable=False),
            sa.Column("substituto", sa.String(), nullable=True),
            _fk("contrato_id", "contratos.id"),
            sa.PrimaryKeyConstraint("id"),
        ]),
        ("papeis_membro", [
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("membro_id", sa.Integer(), nullable=False),
            sa.Column("papel", sa.String(), nullable=False),
            _fk("membro_id", "membros_equipe.id"),
            sa.PrimaryKeyConstraint("id"),
        ]),
        ("competencias", [
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("contrato_id", sa.Integer(), nullable=False),
            sa.Column("ano", sa.Integer(), nullable=False),
            sa.Column("mes", sa.Integer(), nullable=False),
            _fk("contrato_id", "contratos.id"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("contrato_id", "ano", "mes", name="uq_competencia_contrato_ano_mes"),
        ]),
        ("reunioes", [
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("contrato_id", sa.Integer(), nullable=False),
            sa.Column("data", sa.Date(), nullable=False),
            sa.Column("hora", sa.String(), nullable=True),
            sa.Column("local", sa.String(), nullable=True),
            sa.Column("participantes", sa.String(), nullable=False),
            sa.Column("resumo", sa.String(), nullable=False),
            _fk("contrato_id", "contratos.id"),
            sa.PrimaryKeyConstraint("id"),
        ]),
        ("recebimentos_provisorios", [
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("competencia_id", sa.Integer(), nullable=False),
            sa.Column("data", sa.Date(), nullable=False),
            sa.Column("decisao", sa.String(), nullable=False),
            sa.Column("observacao", sa.String(), nullable=True),
            _fk("competencia_id", "competencias.id"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("competencia_id"),
        ]),
        ("ocorrencias", [
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("contrato_id", sa.Integer(), nullable=False),
            sa.Column("data", sa.Date(), nullable=False),
            sa.Column("descricao", sa.String(), nullable=False),
            sa.Column("gravidade", sa.String(), nullable=False),
            _fk("contrato_id", "contratos.id"),
            sa.PrimaryKeyConstraint("id"),
        ]),
        ("pendencias_pre_os", [
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("contrato_id", sa.Integer(), nullable=False),
            sa.Column("item", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            _fk("contrato_id", "contratos.id"),
            sa.PrimaryKeyConstraint("id"),
        ]),
        ("terceirizados", [
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("contrato_id", sa.Integer(), nullable=False),
            sa.Column("cpf", sa.String(), nullable=False),
            sa.Column("nome", sa.String(), nullable=False),
            sa.Column("cargo", sa.String(), nullable=False),
            sa.Column("salario_base", _dinheiro(), nullable=False),
            sa.Column("data_admissao", sa.Date(), nullable=False),
            sa.Column("data_desligamento", sa.Date(), nullable=True),
            _fk("contrato_id", "contratos.id"),
            sa.PrimaryKeyConstraint("id"),
        ]),
        ("cpfs_conhecidos", [
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("contrato_id", sa.Integer(), nullable=False),
            sa.Column("cpf", sa.String(), nullable=False),
            sa.Column("nome", sa.String(), nullable=False),
            sa.Column("motivo", sa.String(), nullable=False),
            sa.Column("competencia_referencia_ano", sa.Integer(), nullable=False),
            sa.Column("competencia_referencia_mes", sa.Integer(), nullable=False),
            _fk("contrato_id", "contratos.id"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("contrato_id", "cpf", name="uq_cpf_conhecido_contrato_cpf"),
        ]),
        ("itens_checklist_documental", [
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("competencia_id", sa.Integer(), nullable=False),
            sa.Column("chave", sa.String(), nullable=False),
            sa.Column("rotulo", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("data_referencia", sa.Date(), nullable=True),
            _fk("competencia_id", "competencias.id"),
            sa.PrimaryKeyConstraint("id"),
        ]),
        ("conclusoes_administrativas", [
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("competencia_id", sa.Integer(), nullable=False),
            sa.Column("conclusao", sa.String(), nullable=False),
            _fk("competencia_id", "competencias.id"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("competencia_id"),
        ]),
        ("relatorios_tecnicos", [
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("competencia_id", sa.Integer(), nullable=False),
            sa.Column("avaliacao", sa.String(), nullable=False),
            sa.Column("conclusao", sa.String(), nullable=False),
            sa.Column("fiscal_responsavel_id", sa.Integer(), nullable=False),
            sa.Column("data_ateste", sa.Date(), nullable=False),
            _fk("competencia_id", "competencias.id"),
            _fk("fiscal_responsavel_id", "membros_equipe.id"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("competencia_id"),
        ]),
        ("itens_folha", [
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("competencia_id", sa.Integer(), nullable=False),
            sa.Column("cpf", sa.String(), nullable=False),
            sa.Column("nome", sa.String(), nullable=False),
            sa.Column("cargo", sa.String(), nullable=False),
            sa.Column("salario_base", _dinheiro(), nullable=False),
            sa.Column("total_vencimentos", _dinheiro(), nullable=False),
            sa.Column("base_inss", _dinheiro(), nullable=False),
            sa.Column("base_fgts", _dinheiro(), nullable=False),
            sa.Column("inss_descontado", _dinheiro(), nullable=False),
            sa.Column("fgts_depositado", _dinheiro(), nullable=False),
            sa.Column("liquido", _dinheiro(), nullable=False),
            _fk("competencia_id", "competencias.id"),
            sa.PrimaryKeyConstraint("id"),
        ]),
        ("ciclos_prorrogacao", [
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("contrato_id", sa.Integer(), nullable=False),
            sa.Column("estado", sa.String(), nullable=False),
            sa.Column("data_envio_notificacao", sa.Date(), nullable=True),
            sa.Column("data_resposta", sa.Date(), nullable=True),
            sa.Column("teor_resposta", sa.String(), nullable=True),
            sa.Column("data_registro_aditivo", sa.Date(), nullable=True),
            sa.Column("vigencia_fim_anterior", sa.Date(), nullable=True),
            sa.Column("nova_vigencia_fim", sa.Date(), nullable=True),
            sa.Column("data_area_acionada", sa.Date(), nullable=True),
            sa.Column("observacao_area", sa.String(), nullable=True),
            sa.Column("data_encerramento", sa.Date(), nullable=True),
            sa.Column("observacao_encerramento", sa.String(), nullable=True),
            _fk("contrato_id", "contratos.id"),
            sa.PrimaryKeyConstraint("id"),
        ]),
        ("relatorios_finais", [
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("contrato_id", sa.Integer(), nullable=False),
            sa.Column("conceito", sa.String(), nullable=False),
            sa.Column("justificativa", sa.String(), nullable=False),
            sa.Column("licoes", sa.String(), nullable=True),
            _fk("contrato_id", "contratos.id"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("contrato_id"),
        ]),
        ("entregas_listagem_semestral", [
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("contrato_id", sa.Integer(), nullable=False),
            sa.Column("data", sa.Date(), nullable=False),
            sa.Column("observacao", sa.String(), nullable=True),
            _fk("contrato_id", "contratos.id"),
            sa.PrimaryKeyConstraint("id"),
        ]),
        ("configuracoes_prazos", [
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("contrato_id", sa.Integer(), nullable=False),
            sa.Column("antecedencia_notificacao_dias", sa.Integer(), nullable=False),
            sa.Column("prazo_resposta_dias_uteis", sa.Integer(), nullable=False),
            sa.Column("antecedencia_certidoes_dias", sa.Integer(), nullable=False),
            sa.Column("antecedencia_semestral_dias", sa.Integer(), nullable=False),
            sa.Column("dia_limite_gfd_darf", sa.Integer(), nullable=False),
            _fk("contrato_id", "contratos.id"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("contrato_id"),
        ]),
    ]


# Colunas acrescentadas em fases anteriores a tabelas que já existiam. É a lista
# que vivia em app/database.py (_COLUNAS_NOVAS); bancos criados antes dessas
# fases ainda podem estar sem elas. Todas são anuláveis, então ADD COLUMN basta.
COLUNAS_ACRESCENTADAS = [
    ("reunioes", "hora", sa.String()),
    ("reunioes", "local", sa.String()),
    ("ciclos_prorrogacao", "data_envio_notificacao", sa.Date()),
    ("ciclos_prorrogacao", "data_resposta", sa.Date()),
    ("ciclos_prorrogacao", "teor_resposta", sa.String()),
    ("ciclos_prorrogacao", "data_registro_aditivo", sa.Date()),
    ("ciclos_prorrogacao", "vigencia_fim_anterior", sa.Date()),
    ("ciclos_prorrogacao", "nova_vigencia_fim", sa.Date()),
    ("ciclos_prorrogacao", "data_area_acionada", sa.Date()),
    ("ciclos_prorrogacao", "observacao_area", sa.String()),
    ("ciclos_prorrogacao", "data_encerramento", sa.Date()),
    ("ciclos_prorrogacao", "observacao_encerramento", sa.String()),
]


def upgrade() -> None:
    inspetor = sa.inspect(op.get_bind())
    existentes = set(inspetor.get_table_names())

    for nome, definicao in _tabelas():
        if nome not in existentes:
            op.create_table(nome, *definicao)
            indices = set()
        else:
            indices = {indice["name"] for indice in inspetor.get_indexes(nome)}
        if f"ix_{nome}_id" not in indices:
            op.create_index(f"ix_{nome}_id", nome, ["id"], unique=False)

    inspetor = sa.inspect(op.get_bind())  # recarrega: tabelas novas acabaram de nascer
    for tabela, coluna, tipo in COLUNAS_ACRESCENTADAS:
        colunas = {c["name"] for c in inspetor.get_columns(tabela)}
        if coluna not in colunas:
            op.add_column(tabela, sa.Column(coluna, tipo, nullable=True))


def downgrade() -> None:
    # Voltar daqui significaria apagar todas as tabelas — ou seja, todos os
    # contratos, folhas e relatórios da instância. Não existe caso de uso para
    # isso; quem precisar de banco limpo apaga o arquivo .db.
    raise NotImplementedError("A revisão inicial não tem volta: ela apagaria todos os dados.")
