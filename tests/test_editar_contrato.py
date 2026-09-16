from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Contrato


def _dados_validos(**overrides):
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
    client.post("/contratos", data=_dados_validos(**overrides))
    db = SessionLocal()
    try:
        contrato = db.query(Contrato).order_by(Contrato.id.desc()).first()
        return contrato.id
    finally:
        db.close()


def test_formulario_edicao_vem_pre_preenchido():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.get(f"/contratos/{contrato_id}/editar")
    assert response.status_code == 200
    assert 'value="001/2026"' in response.text
    assert "Limpa Tudo Serviços Ltda" in response.text
    assert 'value="2026-01-01"' in response.text
    assert 'value="2026-12-31"' in response.text


def test_editar_contrato_atualiza_dados_na_listagem():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/editar",
            data=_dados_validos(numero="001/2026-REV1", objeto="Objeto revisado"),
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/contratos"

        listagem = client.get("/contratos")
    assert "001/2026-REV1" in listagem.text
    assert "Objeto revisado" in listagem.text
    assert "001/2026<" not in listagem.text


def test_editar_contrato_persiste_no_sqlite():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(
            f"/contratos/{contrato_id}/editar",
            data=_dados_validos(valor_global="777.77"),
        )

    db = SessionLocal()
    try:
        contrato = db.get(Contrato, contrato_id)
        assert str(contrato.valor_global) == "777.77"
    finally:
        db.close()


def test_editar_contrato_ce01_data_fim_anterior_ao_inicio_e_rejeitada():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/editar",
            data=_dados_validos(vigencia_inicio="2026-06-01", vigencia_fim="2026-01-01"),
        )
    assert response.status_code == 422
    assert "anterior" in response.text.lower()

    db = SessionLocal()
    try:
        contrato = db.get(Contrato, contrato_id)
        assert contrato.vigencia_inicio.isoformat() == "2026-01-01"
        assert contrato.vigencia_fim.isoformat() == "2026-12-31"
    finally:
        db.close()


def test_editar_contrato_ce02_valor_negativo_e_rejeitado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/editar",
            data=_dados_validos(valor_global="-5"),
        )
    assert response.status_code == 422
    assert "negativo" in response.text.lower()

    db = SessionLocal()
    try:
        contrato = db.get(Contrato, contrato_id)
        assert str(contrato.valor_global) == "150000.00"
    finally:
        db.close()


def test_editar_contrato_inexistente_retorna_404():
    with TestClient(app) as client:
        response_get = client.get("/contratos/99999/editar")
        response_post = client.post("/contratos/99999/editar", data=_dados_validos())
    assert response_get.status_code == 404
    assert response_post.status_code == 404
