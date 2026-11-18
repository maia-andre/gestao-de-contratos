"""Migrações de esquema (Alembic).

Cada fiscal tem o próprio banco SQLite na máquina, então a subida do sistema
precisa levar qualquer banco — vazio, criado antes do Alembic ou já versionado —
até a revisão mais recente, sem perder dado e sem ninguém rodar comando.
"""

import os
import sqlite3
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient

from app import database
from app.main import app

DB_PATH = os.environ["GESTORDECONTRATO_DB_PATH"]
MIGRATIONS_DIR = Path(database.__file__).resolve().parent / "migrations"

TABELAS_DO_SISTEMA = {
    "contratos",
    "membros_equipe",
    "papeis_membro",
    "competencias",
    "reunioes",
    "recebimentos_provisorios",
    "ocorrencias",
    "pendencias_pre_os",
    "terceirizados",
    "parametros_faixas_inss",
    "parametros_gerais",
    "cpfs_conhecidos",
    "itens_checklist_documental",
    "conclusoes_administrativas",
    "relatorios_tecnicos",
    "itens_folha",
    "ciclos_prorrogacao",
    "relatorios_finais",
    "entregas_listagem_semestral",
    "configuracoes_prazos",
}


def _script():
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    return ScriptDirectory.from_config(cfg)


def _head() -> str:
    return _script().get_current_head()


def _tabelas() -> set[str]:
    con = sqlite3.connect(DB_PATH)
    nomes = {linha[0] for linha in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
    return nomes


def _revisao_gravada() -> str | None:
    con = sqlite3.connect(DB_PATH)
    linha = con.execute("SELECT version_num FROM alembic_version").fetchone()
    con.close()
    return linha[0] if linha else None


def _executar(sql: str, *params) -> None:
    database.engine.dispose()
    con = sqlite3.connect(DB_PATH)
    con.execute(sql, params)
    con.commit()
    con.close()


# Estrutura do repositório de migrações


def test_ha_uma_unica_revisao_head():
    # Duas heads significam dois PRs que criaram migração a partir da mesma base;
    # o upgrade "head" falha e nenhuma instância sobe. Melhor quebrar aqui.
    assert len(_script().get_heads()) == 1


def test_models_e_migracoes_descrevem_o_mesmo_esquema():
    database.init_db()
    with database.engine.connect() as conexao:
        diferencas = compare_metadata(MigrationContext.configure(conexao), database.Base.metadata)
    assert diferencas == [], (
        "Os models mudaram sem migração correspondente. Gere uma com "
        "`.venv/bin/alembic revision --autogenerate -m \"...\"` e revise o arquivo."
    )


# Banco vazio


def test_banco_vazio_recebe_todas_as_tabelas_e_fica_na_head():
    database.init_db()
    assert TABELAS_DO_SISTEMA <= _tabelas()
    assert _revisao_gravada() == _head()


def test_subida_pela_aplicacao_migra_o_banco():
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert _revisao_gravada() == _head()


def test_rodar_init_db_duas_vezes_nao_quebra_nem_duplica():
    database.init_db()
    _executar(
        "INSERT INTO parametros_gerais (id, percentual_fgts) VALUES (1, 0.08)"
    )
    database.init_db()

    con = sqlite3.connect(DB_PATH)
    linhas = con.execute("SELECT percentual_fgts FROM parametros_gerais").fetchall()
    versoes = con.execute("SELECT COUNT(*) FROM alembic_version").fetchone()[0]
    con.close()
    assert len(linhas) == 1
    assert versoes == 1


# Banco criado antes do Alembic (create_all + lista de ALTER TABLE)


def _criar_banco_pre_alembic_sem_colunas_novas():
    """Banco como o de uma instância das fases 0–1: tabelas no DDL que o
    create_all gerava, sem alembic_version e sem as colunas que só vieram
    depois (hora/local da reunião, campos do ciclo de prorrogação)."""
    database.engine.dispose()
    con = sqlite3.connect(DB_PATH)
    con.executescript(
        """
        CREATE TABLE contratos (
            id INTEGER NOT NULL, numero VARCHAR NOT NULL, objeto VARCHAR NOT NULL,
            contratada_razao_social VARCHAR NOT NULL, contratada_cnpj VARCHAR NOT NULL,
            vigencia_inicio DATE NOT NULL, vigencia_fim DATE NOT NULL,
            mao_de_obra_exclusiva BOOLEAN NOT NULL, valor_global NUMERIC(14, 2) NOT NULL,
            modalidade VARCHAR NOT NULL, PRIMARY KEY (id)
        );
        CREATE INDEX ix_contratos_id ON contratos (id);
        CREATE TABLE reunioes (
            id INTEGER NOT NULL, contrato_id INTEGER NOT NULL,
            data DATE NOT NULL, participantes VARCHAR NOT NULL, resumo VARCHAR NOT NULL,
            PRIMARY KEY (id), FOREIGN KEY(contrato_id) REFERENCES contratos (id)
        );
        CREATE INDEX ix_reunioes_id ON reunioes (id);
        CREATE TABLE ciclos_prorrogacao (
            id INTEGER NOT NULL, contrato_id INTEGER NOT NULL, estado VARCHAR NOT NULL,
            PRIMARY KEY (id), FOREIGN KEY(contrato_id) REFERENCES contratos (id)
        );
        CREATE INDEX ix_ciclos_prorrogacao_id ON ciclos_prorrogacao (id);

        INSERT INTO contratos VALUES (
            7, '012/2025', 'Limpeza predial', 'Empresa Fictícia Ltda', '00.000.000/0000-00',
            '2025-03-01', '2026-02-28', 1, 480000.00, 'pregao'
        );
        INSERT INTO reunioes (contrato_id, data, participantes, resumo)
            VALUES (7, '2025-03-05', 'Fulano de Tal', 'Reunião inicial.');
        INSERT INTO ciclos_prorrogacao (contrato_id, estado)
            VALUES (7, 'notificacao_enviada');
        """
    )
    con.commit()
    con.close()


def test_banco_pre_alembic_preserva_dados_e_fica_na_head():
    _criar_banco_pre_alembic_sem_colunas_novas()

    database.init_db()

    con = sqlite3.connect(DB_PATH)
    contrato = con.execute("SELECT id, numero, objeto FROM contratos").fetchone()
    reuniao = con.execute("SELECT contrato_id, resumo, hora, local FROM reunioes").fetchone()
    ciclo = con.execute("SELECT estado, data_envio_notificacao FROM ciclos_prorrogacao").fetchone()
    con.close()

    assert contrato == (7, "012/2025", "Limpeza predial")
    assert reuniao == (7, "Reunião inicial.", None, None)
    assert ciclo == ("notificacao_enviada", None)
    assert _revisao_gravada() == _head()


def test_banco_pre_alembic_ganha_as_tabelas_das_fases_seguintes():
    _criar_banco_pre_alembic_sem_colunas_novas()

    database.init_db()

    assert TABELAS_DO_SISTEMA <= _tabelas()


def test_banco_pre_alembic_fica_identico_aos_models_depois_da_subida():
    _criar_banco_pre_alembic_sem_colunas_novas()

    database.init_db()

    with database.engine.connect() as conexao:
        diferencas = compare_metadata(MigrationContext.configure(conexao), database.Base.metadata)
    assert diferencas == []


def test_banco_pre_alembic_continua_utilizavel_pela_aplicacao():
    _criar_banco_pre_alembic_sem_colunas_novas()

    with TestClient(app) as client:
        response = client.get("/contratos/7")
        assert response.status_code == 200
        assert "012/2025" in response.text


# Banco já versionado


def test_banco_ja_na_head_nao_e_reprocessado():
    database.init_db()
    _executar("CREATE TABLE marcador_do_teste (x INTEGER)")
    _executar("INSERT INTO marcador_do_teste VALUES (42)")

    database.init_db()

    con = sqlite3.connect(DB_PATH)
    assert con.execute("SELECT x FROM marcador_do_teste").fetchone() == (42,)
    con.close()
    assert _revisao_gravada() == _head()
