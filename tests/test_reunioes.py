from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Contrato


def _dados_contrato(**overrides):
    dados = {
        "numero": "001/2026",
        "objeto": "Serviço de limpeza predial",
        "contratada_razao_social": "Limpa Tudo Serviços Ltda",
        "contratada_cnpj": "12.345.678/0001-90",
        "vigencia_inicio": "2026-01-01",
        "vigencia_fim": "2026-12-31",
        "mao_de_obra_exclusiva": "sim",
        "valor_global": "150000.00",
        "modalidade": "Pregão eletrônico",
    }
    dados.update(overrides)
    return dados


def _criar_contrato(client, **overrides) -> int:
    client.post("/contratos", data=_dados_contrato(**overrides))
    db = SessionLocal()
    try:
        return db.query(Contrato).order_by(Contrato.id.desc()).first().id
    finally:
        db.close()


def test_listagem_de_reunioes_vazia_inicialmente():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.get(f"/contratos/{contrato_id}/reunioes")
    assert response.status_code == 200
    assert "Nenhuma reunião registrada" in response.text


def test_cadastrar_reuniao_e_ver_na_listagem():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/reunioes",
            data={
                "data": "2026-02-05",
                "participantes": "João Silva (Fiscal Técnico); Maria Oliveira (representante da contratada)",
                "resumo": "Alinhamento inicial do escopo e cronograma.",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        listagem = client.get(f"/contratos/{contrato_id}/reunioes")
    assert "2026-02-05" in listagem.text
    assert "Maria Oliveira" in listagem.text
    assert "Alinhamento inicial do escopo e cronograma." in listagem.text


def test_cadastrar_multiplas_reunioes_no_mesmo_contrato():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(
            f"/contratos/{contrato_id}/reunioes",
            data={"data": "2026-02-05", "participantes": "João Silva", "resumo": "Reunião inicial."},
        )
        client.post(
            f"/contratos/{contrato_id}/reunioes",
            data={"data": "2026-05-10", "participantes": "João Silva", "resumo": "Realinhamento de prazo."},
        )
        listagem = client.get(f"/contratos/{contrato_id}/reunioes")
    assert "Reunião inicial." in listagem.text
    assert "Realinhamento de prazo." in listagem.text


def test_campo_obrigatorio_ausente_e_rejeitado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/reunioes",
            data={"data": "", "participantes": "João Silva", "resumo": "Resumo qualquer."},
        )
    assert response.status_code == 422
    assert "obrigat" in response.text.lower()


def test_reunioes_de_contrato_inexistente_retorna_404():
    with TestClient(app) as client:
        response = client.get("/contratos/99999/reunioes")
    assert response.status_code == 404


def test_cadastrar_reuniao_com_hora_e_local():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/reunioes",
            data={
                "data": "2026-02-05",
                "hora": "14:30",
                "local": "Sala de reuniões da Secretaria",
                "participantes": "João Silva",
                "resumo": "Pauta: alinhamento inicial.",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        listagem = client.get(f"/contratos/{contrato_id}/reunioes")
    assert "14:30" in listagem.text
    assert "Sala de reuniões da Secretaria" in listagem.text


def test_hora_invalida_e_rejeitada():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/reunioes",
            data={
                "data": "2026-02-05",
                "hora": "25:99",
                "participantes": "João Silva",
                "resumo": "Resumo qualquer.",
            },
        )
    assert response.status_code == 422
    assert "Hora inválida" in response.text


def _id_ultima_reuniao() -> int:
    from app.models_fiscalizacao import Reuniao

    db = SessionLocal()
    try:
        return db.query(Reuniao).order_by(Reuniao.id.desc()).first().id
    finally:
        db.close()


def test_editar_reuniao_existente():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(
            f"/contratos/{contrato_id}/reunioes",
            data={"data": "2026-02-05", "participantes": "João Silva", "resumo": "Pauta prevista."},
        )
        reuniao_id = _id_ultima_reuniao()

        form_edicao = client.get(f"/contratos/{contrato_id}/reunioes/{reuniao_id}/editar")
        assert form_edicao.status_code == 200
        assert "Pauta prevista." in form_edicao.text

        response = client.post(
            f"/contratos/{contrato_id}/reunioes/{reuniao_id}/editar",
            data={
                "data": "2026-02-05",
                "hora": "10:00",
                "local": "Auditório",
                "participantes": "João Silva",
                "resumo": "Deliberações registradas após a reunião.",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        listagem = client.get(f"/contratos/{contrato_id}/reunioes")
    assert "Deliberações registradas após a reunião." in listagem.text
    assert "Pauta prevista." not in listagem.text
    assert "Auditório" in listagem.text


def test_editar_reuniao_com_campo_obrigatorio_vazio_e_rejeitado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(
            f"/contratos/{contrato_id}/reunioes",
            data={"data": "2026-02-05", "participantes": "João Silva", "resumo": "Resumo."},
        )
        reuniao_id = _id_ultima_reuniao()
        response = client.post(
            f"/contratos/{contrato_id}/reunioes/{reuniao_id}/editar",
            data={"data": "2026-02-05", "participantes": "João Silva", "resumo": ""},
        )
    assert response.status_code == 422
    assert "obrigat" in response.text.lower()


def test_editar_reuniao_inexistente_retorna_404():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.get(f"/contratos/{contrato_id}/reunioes/99999/editar")
    assert response.status_code == 404


def test_banco_de_fase_anterior_ganha_colunas_novas_na_subida():
    import sqlite3

    from app import database

    database.engine.dispose()
    db_path = database.DATABASE_URL.replace("sqlite:///", "")
    conexao = sqlite3.connect(db_path)
    conexao.execute(
        "CREATE TABLE reunioes (id INTEGER PRIMARY KEY, contrato_id INTEGER NOT NULL, "
        "data DATE NOT NULL, participantes VARCHAR NOT NULL, resumo VARCHAR NOT NULL)"
    )
    conexao.execute(
        "INSERT INTO reunioes (contrato_id, data, participantes, resumo) "
        "VALUES (1, '2026-02-05', 'João Silva', 'Reunião antiga.')"
    )
    conexao.commit()
    conexao.close()

    database.init_db()

    conexao = sqlite3.connect(db_path)
    colunas = {linha[1] for linha in conexao.execute("PRAGMA table_info(reunioes)")}
    linha = conexao.execute("SELECT hora, local, resumo FROM reunioes").fetchone()
    conexao.close()
    assert {"hora", "local"} <= colunas
    assert linha == (None, None, "Reunião antiga.")
