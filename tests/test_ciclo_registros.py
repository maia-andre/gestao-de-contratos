import os
import sqlite3
from datetime import date

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


def _configurar_prazo_resposta(client, contrato_id: int, dias: int) -> None:
    client.post(
        f"/contratos/{contrato_id}/configuracoes-prazos",
        data={
            "antecedencia_notificacao_dias": "90",
            "prazo_resposta_dias_uteis": str(dias),
            "antecedencia_certidoes_dias": "15",
            "antecedencia_semestral_dias": "30",
            "dia_limite_gfd_darf": "20",
        },
    )


# RN-02 — soma de dias úteis (segunda a sexta, sem feriados)


def test_somar_dias_uteis_dentro_da_semana():
    from app.routers.prorrogacao import somar_dias_uteis

    # terça 04/08/2026 + 3 dias úteis = sexta 07/08/2026
    assert somar_dias_uteis(date(2026, 8, 4), 3) == date(2026, 8, 7)


def test_somar_dias_uteis_atravessa_fim_de_semana():
    from app.routers.prorrogacao import somar_dias_uteis

    # sexta 07/08/2026 + 3 dias úteis = quarta 12/08/2026
    assert somar_dias_uteis(date(2026, 8, 7), 3) == date(2026, 8, 12)


def test_somar_dias_uteis_a_partir_de_sabado():
    from app.routers.prorrogacao import somar_dias_uteis

    # sábado 08/08/2026 + 1 dia útil = segunda 10/08/2026
    assert somar_dias_uteis(date(2026, 8, 8), 1) == date(2026, 8, 10)


# REQ-04 — registrar envio; data-limite exibida no ciclo


def test_registrar_envio_avanca_estado_e_mostra_data_limite():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/prorrogacao/envio",
            data={"data_envio": "2026-08-04"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        pagina = client.get(f"/contratos/{contrato_id}/prorrogacao")
    assert "Notificação enviada" in pagina.text
    assert "04/08/2026" in pagina.text  # data do envio
    assert "07/08/2026" in pagina.text  # data-limite: +3 dias úteis (padrão)


def test_data_limite_atravessa_fim_de_semana():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(
            f"/contratos/{contrato_id}/prorrogacao/envio",
            data={"data_envio": "2026-08-07"},
        )
        pagina = client.get(f"/contratos/{contrato_id}/prorrogacao")
    assert "12/08/2026" in pagina.text


def test_data_limite_usa_prazo_configurado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _configurar_prazo_resposta(client, contrato_id, 1)
        client.post(
            f"/contratos/{contrato_id}/prorrogacao/envio",
            data={"data_envio": "2026-08-08"},  # sábado
        )
        pagina = client.get(f"/contratos/{contrato_id}/prorrogacao")
    assert "10/08/2026" in pagina.text  # segunda


def test_envio_sem_data_rejeitado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/prorrogacao/envio", data={"data_envio": ""}
        )
    assert response.status_code == 422
    assert "Data do envio é obrigatória." in response.text


def test_envio_com_data_invalida_rejeitado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/prorrogacao/envio", data={"data_envio": "ontem"}
        )
    assert response.status_code == 422
    assert "Data do envio inválida." in response.text


def test_envio_duplicado_rejeitado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(
            f"/contratos/{contrato_id}/prorrogacao/envio",
            data={"data_envio": "2026-08-04"},
        )
        response = client.post(
            f"/contratos/{contrato_id}/prorrogacao/envio",
            data={"data_envio": "2026-08-05"},
        )
    assert response.status_code == 422
    assert "envio da notificação já foi registrado" in response.text


# REQ-05 — registrar resposta (com/sem interesse)


def test_registrar_resposta_com_interesse():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(
            f"/contratos/{contrato_id}/prorrogacao/envio",
            data={"data_envio": "2026-08-04"},
        )
        response = client.post(
            f"/contratos/{contrato_id}/prorrogacao/resposta",
            data={"data_resposta": "2026-08-06", "teor": "com_interesse"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        pagina = client.get(f"/contratos/{contrato_id}/prorrogacao")
    assert "com interesse" in pagina.text
    assert "06/08/2026" in pagina.text


def test_registrar_resposta_sem_interesse():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(
            f"/contratos/{contrato_id}/prorrogacao/envio",
            data={"data_envio": "2026-08-04"},
        )
        client.post(
            f"/contratos/{contrato_id}/prorrogacao/resposta",
            data={"data_resposta": "2026-08-06", "teor": "sem_interesse"},
        )
        pagina = client.get(f"/contratos/{contrato_id}/prorrogacao")
    assert "sem interesse" in pagina.text


def test_resposta_com_teor_invalido_rejeitada():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(
            f"/contratos/{contrato_id}/prorrogacao/envio",
            data={"data_envio": "2026-08-04"},
        )
        response = client.post(
            f"/contratos/{contrato_id}/prorrogacao/resposta",
            data={"data_resposta": "2026-08-06", "teor": "talvez"},
        )
    assert response.status_code == 422
    assert "Teor da resposta inválido." in response.text


def test_resposta_sem_data_rejeitada():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(
            f"/contratos/{contrato_id}/prorrogacao/envio",
            data={"data_envio": "2026-08-04"},
        )
        response = client.post(
            f"/contratos/{contrato_id}/prorrogacao/resposta",
            data={"data_resposta": "", "teor": "com_interesse"},
        )
    assert response.status_code == 422
    assert "Data da resposta é obrigatória." in response.text


# CE-01 / RN-01 — registros fora de ordem rejeitados


def test_resposta_sem_envio_rejeitada():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/prorrogacao/resposta",
            data={"data_resposta": "2026-08-06", "teor": "com_interesse"},
        )
    assert response.status_code == 422
    assert "antes de registrar o envio da notificação" in response.text


def test_resposta_duplicada_rejeitada():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(
            f"/contratos/{contrato_id}/prorrogacao/envio",
            data={"data_envio": "2026-08-04"},
        )
        client.post(
            f"/contratos/{contrato_id}/prorrogacao/resposta",
            data={"data_resposta": "2026-08-06", "teor": "com_interesse"},
        )
        response = client.post(
            f"/contratos/{contrato_id}/prorrogacao/resposta",
            data={"data_resposta": "2026-08-07", "teor": "sem_interesse"},
        )
    assert response.status_code == 422
    assert "resposta já foi registrada" in response.text


def test_envio_apos_resposta_rejeitado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(
            f"/contratos/{contrato_id}/prorrogacao/envio",
            data={"data_envio": "2026-08-04"},
        )
        client.post(
            f"/contratos/{contrato_id}/prorrogacao/resposta",
            data={"data_resposta": "2026-08-06", "teor": "com_interesse"},
        )
        response = client.post(
            f"/contratos/{contrato_id}/prorrogacao/envio",
            data={"data_envio": "2026-08-07"},
        )
    assert response.status_code == 422


# Migração — banco de fase anterior com tabela ciclos_prorrogacao sem as colunas novas


def test_banco_com_tabela_antiga_ganha_colunas_novas():
    db_path = os.environ["GESTORDECONTRATO_DB_PATH"]
    con = sqlite3.connect(db_path)
    con.execute(
        "CREATE TABLE ciclos_prorrogacao ("
        "id INTEGER PRIMARY KEY, contrato_id INTEGER NOT NULL, estado VARCHAR NOT NULL)"
    )
    con.commit()
    con.close()

    with TestClient(app) as client:  # startup roda init_db + migração
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/prorrogacao/envio",
            data={"data_envio": "2026-08-04"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    con = sqlite3.connect(db_path)
    colunas = {linha[1] for linha in con.execute("PRAGMA table_info(ciclos_prorrogacao)")}
    con.close()
    assert {"data_envio_notificacao", "data_resposta", "teor_resposta"} <= colunas
