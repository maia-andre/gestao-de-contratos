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


# Colunas acrescentadas a tabelas já existentes em fases anteriores; create_all não
# altera tabela existente, então bancos criados antes precisam do ALTER na subida.
_COLUNAS_NOVAS = [
    ("reunioes", "hora", "VARCHAR"),
    ("reunioes", "local", "VARCHAR"),
    ("ciclos_prorrogacao", "data_envio_notificacao", "DATE"),
    ("ciclos_prorrogacao", "data_resposta", "DATE"),
    ("ciclos_prorrogacao", "teor_resposta", "VARCHAR"),
    ("ciclos_prorrogacao", "data_registro_aditivo", "DATE"),
    ("ciclos_prorrogacao", "vigencia_fim_anterior", "DATE"),
    ("ciclos_prorrogacao", "nova_vigencia_fim", "DATE"),
    ("ciclos_prorrogacao", "data_area_acionada", "DATE"),
    ("ciclos_prorrogacao", "observacao_area", "VARCHAR"),
    ("ciclos_prorrogacao", "data_encerramento", "DATE"),
    ("ciclos_prorrogacao", "observacao_encerramento", "VARCHAR"),
]


def _migrar_colunas_novas() -> None:
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    with engine.begin() as conn:
        for tabela, coluna, tipo in _COLUNAS_NOVAS:
            if not inspector.has_table(tabela):
                continue
            existentes = {col["name"] for col in inspector.get_columns(tabela)}
            if coluna not in existentes:
                conn.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}"))


def init_db() -> None:
    from app import models, models_fiscalizacao, models_gestor  # noqa: F401  (registra as tabelas em Base.metadata)

    with engine.connect():
        pass
    Base.metadata.create_all(bind=engine)
    _migrar_colunas_novas()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
