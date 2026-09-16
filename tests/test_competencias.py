from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Contrato
from app.models_fiscalizacao import Competencia


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


def test_listagem_de_competencias_vazia_inicialmente():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.get(f"/contratos/{contrato_id}/competencias")
    assert response.status_code == 200
    assert "Nenhuma competência cadastrada" in response.text


def test_criar_competencia_e_ver_na_listagem():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/competencias",
            data={"mes_ano": "2026-05"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        listagem = client.get(f"/contratos/{contrato_id}/competencias")
    assert "05/2026" in listagem.text


def test_criar_multiplas_competencias_em_meses_diferentes():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(f"/contratos/{contrato_id}/competencias", data={"mes_ano": "2026-05"})
        client.post(f"/contratos/{contrato_id}/competencias", data={"mes_ano": "2026-06"})
        listagem = client.get(f"/contratos/{contrato_id}/competencias")
    assert "05/2026" in listagem.text
    assert "06/2026" in listagem.text


def test_ce16_competencia_duplicada_no_mesmo_contrato_e_rejeitada():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(f"/contratos/{contrato_id}/competencias", data={"mes_ano": "2026-05"})
        response = client.post(f"/contratos/{contrato_id}/competencias", data={"mes_ano": "2026-05"})
    assert response.status_code == 422
    corpo = response.text.lower()
    assert "já existe" in corpo or "já cadastrada" in corpo


def test_mesmo_mes_em_contratos_diferentes_e_permitido():
    with TestClient(app) as client:
        contrato_1 = _criar_contrato(client, numero="001/2026")
        contrato_2 = _criar_contrato(client, numero="002/2026")
        r1 = client.post(
            f"/contratos/{contrato_1}/competencias", data={"mes_ano": "2026-05"}, follow_redirects=False
        )
        r2 = client.post(
            f"/contratos/{contrato_2}/competencias", data={"mes_ano": "2026-05"}, follow_redirects=False
        )
    assert r1.status_code == 303
    assert r2.status_code == 303


def test_abrir_detalhe_de_uma_competencia():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(f"/contratos/{contrato_id}/competencias", data={"mes_ano": "2026-05"})
        db = SessionLocal()
        try:
            competencia_id = db.query(Competencia).first().id
        finally:
            db.close()
        response = client.get(f"/contratos/{contrato_id}/competencias/{competencia_id}")
    assert response.status_code == 200
    assert "05/2026" in response.text


def test_competencia_de_contrato_inexistente_retorna_404():
    with TestClient(app) as client:
        response = client.get("/contratos/99999/competencias")
        response_form = client.get("/contratos/99999/competencias/nova")
        response_post = client.post("/contratos/99999/competencias", data={"mes_ano": "2026-05"})
    assert response.status_code == 404
    assert response_form.status_code == 404
    assert response_post.status_code == 404


def test_competencia_inexistente_retorna_404():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.get(f"/contratos/{contrato_id}/competencias/99999")
    assert response.status_code == 404
