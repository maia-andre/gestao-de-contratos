"""Ambiente de execução das migrações.

Dois caminhos chegam aqui:

- a subida da aplicação (app/database.py:init_db), que já abriu uma conexão e
  a entrega em config.attributes["connection"];
- a linha de comando (`alembic ...`), que lê alembic.ini e conecta no mesmo
  banco que a aplicação usaria.

render_as_batch=True é obrigatório: o SQLite não sabe alterar coluna nem
restrição de tabela existente, e o modo batch do Alembic resolve isso
recriando a tabela e copiando os dados.
"""

from logging.config import fileConfig

from alembic import context

from app import models, models_fiscalizacao, models_gestor  # noqa: F401  (registra as tabelas em Base.metadata)
from app.database import Base, engine

config = context.config
target_metadata = Base.metadata


def _rodar(conexao) -> None:
    context.configure(
        connection=conexao,
        target_metadata=target_metadata,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise SystemExit(
        "Modo offline (--sql) não é suportado: o esquema inicial consulta o banco "
        "para saber o que já existe."
    )

conexao_da_aplicacao = config.attributes.get("connection")
if conexao_da_aplicacao is not None:
    _rodar(conexao_da_aplicacao)
else:
    if config.config_file_name is not None:
        fileConfig(config.config_file_name, disable_existing_loggers=False)
    with engine.begin() as conexao:
        _rodar(conexao)
