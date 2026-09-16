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


def test_listagem_de_ocorrencias_vazia_inicialmente():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.get(f"/contratos/{contrato_id}/ocorrencias")
    assert response.status_code == 200
    assert "Nenhuma ocorrência registrada" in response.text


def test_registrar_ocorrencia_e_ver_na_listagem():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/ocorrencias",
            data={
                "data": "2026-03-10",
                "descricao": "Atraso na troca de equipe do turno noturno.",
                "gravidade": "media",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        listagem = client.get(f"/contratos/{contrato_id}/ocorrencias")
    assert "2026-03-10" in listagem.text
    assert "Atraso na troca de equipe do turno noturno." in listagem.text
    assert "Média" in listagem.text


def test_registrar_multiplas_ocorrencias_com_gravidades_diferentes():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(
            f"/contratos/{contrato_id}/ocorrencias",
            data={"data": "2026-03-10", "descricao": "Ocorrência leve.", "gravidade": "leve"},
        )
        client.post(
            f"/contratos/{contrato_id}/ocorrencias",
            data={"data": "2026-04-05", "descricao": "Ocorrência grave.", "gravidade": "grave"},
        )
        listagem = client.get(f"/contratos/{contrato_id}/ocorrencias")
    assert "Ocorrência leve." in listagem.text
    assert "Ocorrência grave." in listagem.text
    assert "Leve" in listagem.text
    assert "Grave" in listagem.text


def test_gravidade_invalida_e_rejeitada():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/ocorrencias",
            data={"data": "2026-03-10", "descricao": "Descrição qualquer.", "gravidade": "catastrofica"},
        )
    assert response.status_code == 422


def test_campo_obrigatorio_ausente_e_rejeitado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/ocorrencias",
            data={"data": "", "descricao": "Descrição qualquer.", "gravidade": "leve"},
        )
    assert response.status_code == 422
    assert "obrigat" in response.text.lower()


def test_ocorrencias_de_contrato_inexistente_retorna_404():
    with TestClient(app) as client:
        response = client.get("/contratos/99999/ocorrencias")
    assert response.status_code == 404
