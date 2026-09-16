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


def _criar_contrato_com_competencia(client) -> tuple[int, int]:
    client.post("/contratos", data=_dados_contrato())
    db = SessionLocal()
    try:
        contrato_id = db.query(Contrato).order_by(Contrato.id.desc()).first().id
    finally:
        db.close()
    client.post(f"/contratos/{contrato_id}/competencias", data={"mes_ano": "2026-05"})
    db = SessionLocal()
    try:
        competencia_id = db.query(Competencia).filter_by(contrato_id=contrato_id).first().id
    finally:
        db.close()
    return contrato_id, competencia_id


def _url(contrato_id, competencia_id):
    return f"/contratos/{contrato_id}/competencias/{competencia_id}/recebimento-provisorio"


def test_formulario_vazio_quando_ainda_nao_registrado():
    with TestClient(app) as client:
        contrato_id, competencia_id = _criar_contrato_com_competencia(client)
        response = client.get(_url(contrato_id, competencia_id))
    assert response.status_code == 200


def test_registrar_recebimento_aceito():
    with TestClient(app) as client:
        contrato_id, competencia_id = _criar_contrato_com_competencia(client)
        response = client.post(
            _url(contrato_id, competencia_id),
            data={"data": "2026-05-28", "decisao": "aceito", "observacao": ""},
            follow_redirects=False,
        )
        assert response.status_code == 303
        detalhe = client.get(_url(contrato_id, competencia_id))
    assert "2026-05-28" in detalhe.text
    assert "aceito" in detalhe.text.lower()


def test_ce14_recusado_sem_observacao_e_bloqueado():
    with TestClient(app) as client:
        contrato_id, competencia_id = _criar_contrato_com_competencia(client)
        response = client.post(
            _url(contrato_id, competencia_id),
            data={"data": "2026-05-28", "decisao": "recusado", "observacao": ""},
        )
    assert response.status_code == 422
    assert "obrigat" in response.text.lower()


def test_recusado_com_observacao_e_aceito():
    with TestClient(app) as client:
        contrato_id, competencia_id = _criar_contrato_com_competencia(client)
        response = client.post(
            _url(contrato_id, competencia_id),
            data={
                "data": "2026-05-28",
                "decisao": "recusado",
                "observacao": "Serviço não atendeu ao cronograma pactuado.",
            },
            follow_redirects=False,
        )
    assert response.status_code == 303


def test_registrar_de_novo_atualiza_o_existente_em_vez_de_duplicar():
    with TestClient(app) as client:
        contrato_id, competencia_id = _criar_contrato_com_competencia(client)
        client.post(
            _url(contrato_id, competencia_id),
            data={"data": "2026-05-28", "decisao": "aceito", "observacao": ""},
        )
        client.post(
            _url(contrato_id, competencia_id),
            data={"data": "2026-05-29", "decisao": "aceito_com_ressalva", "observacao": "Pequeno atraso."},
        )
        detalhe = client.get(_url(contrato_id, competencia_id))

    db = SessionLocal()
    from app.models_fiscalizacao import RecebimentoProvisorio

    try:
        total = db.query(RecebimentoProvisorio).filter_by(competencia_id=competencia_id).count()
    finally:
        db.close()
    assert total == 1
    assert "2026-05-29" in detalhe.text
    assert "Pequeno atraso." in detalhe.text


def test_decisao_invalida_e_rejeitada():
    with TestClient(app) as client:
        contrato_id, competencia_id = _criar_contrato_com_competencia(client)
        response = client.post(
            _url(contrato_id, competencia_id),
            data={"data": "2026-05-28", "decisao": "talvez", "observacao": ""},
        )
    assert response.status_code == 422


def test_recebimento_de_competencia_inexistente_retorna_404():
    with TestClient(app) as client:
        contrato_id, _ = _criar_contrato_com_competencia(client)
        response = client.get(_url(contrato_id, 99999))
    assert response.status_code == 404
