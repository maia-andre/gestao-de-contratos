import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def _database_url() -> str:
    db_path = os.environ.get(
        "GESTORDECONTRATO_DB_PATH",
        str(Path(__file__).resolve().parent.parent / "gestordecontrato.db"),
    )
    return f"sqlite:///{db_path}"


DATABASE_URL = _database_url()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def init_db() -> None:
    """Leva o banco até a revisão mais recente do esquema (app/migrations).

    Cada fiscal tem o próprio banco na máquina e ninguém roda comando de
    migração: a subida da aplicação faz isso. Vale para banco vazio, para banco
    criado antes do Alembic (a revisão 0001 cuida dele) e para banco já
    versionado, em que só as revisões pendentes rodam.
    """
    from alembic import command
    from alembic.config import Config

    configuracao = Config()
    configuracao.set_main_option("script_location", str(MIGRATIONS_DIR))
    with engine.begin() as conexao:
        configuracao.attributes["connection"] = conexao
        command.upgrade(configuracao, "head")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
