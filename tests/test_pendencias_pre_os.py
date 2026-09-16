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


def test_checklist_vem_pre_carregado_com_2_itens_pendentes():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.get(f"/contratos/{contrato_id}/pendencias-pre-os")
    assert response.status_code == 200
    assert "Contratada designou preposto" in response.text
    assert "Documentação inicial entregue" in response.text
    assert response.text.count("pendente") >= 2


def test_alternar_item_para_ok():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.get(f"/contratos/{contrato_id}/pendencias-pre-os")

        db = SessionLocal()
        from app.models_fiscalizacao import PendenciaPreOS

        try:
            item = (
                db.query(PendenciaPreOS)
                .filter_by(contrato_id=contrato_id, item="Contratada designou preposto")
                .first()
            )
            item_id = item.id
        finally:
            db.close()

        response = client.post(
            f"/contratos/{contrato_id}/pendencias-pre-os/{item_id}/alternar", follow_redirects=False
        )
        assert response.status_code == 303

        db = SessionLocal()
        try:
            item = db.get(PendenciaPreOS, item_id)
            assert item.status == "ok"
        finally:
            db.close()


def test_alternar_de_volta_para_pendente():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.get(f"/contratos/{contrato_id}/pendencias-pre-os")

        db = SessionLocal()
        from app.models_fiscalizacao import PendenciaPreOS

        try:
            item_id = db.query(PendenciaPreOS).filter_by(contrato_id=contrato_id).first().id
        finally:
            db.close()

        client.post(f"/contratos/{contrato_id}/pendencias-pre-os/{item_id}/alternar")
        client.post(f"/contratos/{contrato_id}/pendencias-pre-os/{item_id}/alternar")

        db = SessionLocal()
        try:
            item = db.get(PendenciaPreOS, item_id)
            assert item.status == "pendente"
        finally:
            db.close()


def test_acessar_checklist_duas_vezes_nao_duplica_itens():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.get(f"/contratos/{contrato_id}/pendencias-pre-os")
        client.get(f"/contratos/{contrato_id}/pendencias-pre-os")

    db = SessionLocal()
    from app.models_fiscalizacao import PendenciaPreOS

    try:
        total = db.query(PendenciaPreOS).filter_by(contrato_id=contrato_id).count()
    finally:
        db.close()
    assert total == 2


def test_pendencias_de_contrato_inexistente_retorna_404():
    with TestClient(app) as client:
        response = client.get("/contratos/99999/pendencias-pre-os")
    assert response.status_code == 404


def test_alternar_item_de_outro_contrato_retorna_404():
    with TestClient(app) as client:
        contrato_1 = _criar_contrato(client, numero="001/2026")
        contrato_2 = _criar_contrato(client, numero="002/2026")
        client.get(f"/contratos/{contrato_1}/pendencias-pre-os")

        db = SessionLocal()
        from app.models_fiscalizacao import PendenciaPreOS

        try:
            item_id = db.query(PendenciaPreOS).filter_by(contrato_id=contrato_1).first().id
        finally:
            db.close()

        response = client.post(f"/contratos/{contrato_2}/pendencias-pre-os/{item_id}/alternar")
    assert response.status_code == 404
