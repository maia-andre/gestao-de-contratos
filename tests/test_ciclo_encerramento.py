from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Contrato
from app.models_gestor import CicloProrrogacao


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


def _registrar_prorrogacao_completa(client, contrato_id: int, nova_fim: str) -> None:
    client.post(f"/contratos/{contrato_id}/prorrogacao/envio", data={"data_envio": "2026-08-04"})
    client.post(
        f"/contratos/{contrato_id}/prorrogacao/resposta",
        data={"data_resposta": "2026-08-06", "teor": "com_interesse"},
    )
    client.post(
        f"/contratos/{contrato_id}/prorrogacao/aditivo",
        data={"nova_vigencia_fim": nova_fim},
    )


def _ciclos(contrato_id: int) -> list[CicloProrrogacao]:
    db = SessionLocal()
    try:
        return (
            db.query(CicloProrrogacao)
            .filter_by(contrato_id=contrato_id)
            .order_by(CicloProrrogacao.id)
            .all()
        )
    finally:
        db.close()


# REQ-08 — encerramento manual em estado não-final


def test_encerrar_ciclo_em_aguardando_notificacao():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/prorrogacao/encerrar",
            data={"observacao": "Serviço será absorvido por equipe própria."},
            follow_redirects=False,
        )
        assert response.status_code == 303
        pagina = client.get(f"/contratos/{contrato_id}/prorrogacao")
    assert "não haverá prorrogação" in pagina.text
    assert "decisão da administração" in pagina.text
    assert "Serviço será absorvido por equipe própria." in pagina.text
    ciclos = _ciclos(contrato_id)
    assert len(ciclos) == 1
    assert ciclos[0].estado == "encerrado_sem_prorrogacao"


def test_encerrar_sem_observacao_aceito():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/prorrogacao/encerrar",
            data={"observacao": ""},
            follow_redirects=False,
        )
    assert response.status_code == 303


# CE-12 — encerramento no meio do fluxo preserva o histórico consultável


def test_encerrar_apos_envio_preserva_registros():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(
            f"/contratos/{contrato_id}/prorrogacao/envio", data={"data_envio": "2026-08-04"}
        )
        response = client.post(
            f"/contratos/{contrato_id}/prorrogacao/encerrar",
            data={"observacao": ""},
            follow_redirects=False,
        )
        assert response.status_code == 303
        pagina = client.get(f"/contratos/{contrato_id}/prorrogacao")
    assert "não haverá prorrogação" in pagina.text
    assert "04/08/2026" in pagina.text  # envio registrado continua consultável


def test_encerrar_apos_resposta_permitido():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(
            f"/contratos/{contrato_id}/prorrogacao/envio", data={"data_envio": "2026-08-04"}
        )
        client.post(
            f"/contratos/{contrato_id}/prorrogacao/resposta",
            data={"data_resposta": "2026-08-06", "teor": "com_interesse"},
        )
        response = client.post(
            f"/contratos/{contrato_id}/prorrogacao/encerrar",
            data={"observacao": ""},
            follow_redirects=False,
        )
    assert response.status_code == 303


def test_encerrar_ciclo_ja_encerrado_rejeitado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(f"/contratos/{contrato_id}/prorrogacao/encerrar", data={"observacao": ""})
        response = client.post(
            f"/contratos/{contrato_id}/prorrogacao/encerrar", data={"observacao": ""}
        )
    assert response.status_code == 422
    assert "já está encerrado" in response.text


def test_ciclo_encerrado_nao_oferece_formularios_de_registro():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(f"/contratos/{contrato_id}/prorrogacao/encerrar", data={"observacao": ""})
        pagina = client.get(f"/contratos/{contrato_id}/prorrogacao")
    assert f"/contratos/{contrato_id}/prorrogacao/envio" not in pagina.text
    assert f"/contratos/{contrato_id}/prorrogacao/resposta" not in pagina.text
    assert f"/contratos/{contrato_id}/prorrogacao/encerrar" not in pagina.text


# REQ-09 — duração acumulada e histórico de prorrogações


def test_duracao_acumulada_sem_prorrogacao():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        pagina = client.get(f"/contratos/{contrato_id}/prorrogacao")
    assert "Duração acumulada" in pagina.text
    assert "364 dias" in pagina.text  # 01/01/2026 a 31/12/2026


def test_duracao_acumulada_apos_prorrogacao():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _registrar_prorrogacao_completa(client, contrato_id, "2027-12-31")
        pagina = client.get(f"/contratos/{contrato_id}/prorrogacao")
    assert "1 ano e 364 dias" in pagina.text


def test_historico_lista_cada_aditivo():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _registrar_prorrogacao_completa(client, contrato_id, "2027-12-31")
        # segunda prorrogação no novo ciclo
        client.post(
            f"/contratos/{contrato_id}/prorrogacao/envio", data={"data_envio": "2027-08-02"}
        )
        client.post(
            f"/contratos/{contrato_id}/prorrogacao/resposta",
            data={"data_resposta": "2027-08-04", "teor": "com_interesse"},
        )
        client.post(
            f"/contratos/{contrato_id}/prorrogacao/aditivo",
            data={"nova_vigencia_fim": "2028-12-31"},
        )
        pagina = client.get(f"/contratos/{contrato_id}/prorrogacao")
    assert "Histórico de prorrogações" in pagina.text
    assert "31/12/2026" in pagina.text and "31/12/2027" in pagina.text
    assert "31/12/2028" in pagina.text


def test_contrato_sem_prorrogacao_nao_mostra_historico():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        pagina = client.get(f"/contratos/{contrato_id}/prorrogacao")
    assert "Histórico de prorrogações" not in pagina.text


# CE-11 — edição manual da vigência não cria ciclo novo


def test_editar_vigencia_no_contrato_nao_cria_ciclo():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(
            f"/contratos/{contrato_id}/prorrogacao/envio", data={"data_envio": "2026-08-04"}
        )
        client.post(
            f"/contratos/{contrato_id}/editar",
            data=_dados_contrato(vigencia_fim="2027-06-30"),
        )
        pagina = client.get(f"/contratos/{contrato_id}/prorrogacao")
    ciclos = _ciclos(contrato_id)
    assert len(ciclos) == 1
    assert ciclos[0].estado == "notificacao_enviada"  # ciclo corrente permanece
    assert "1 ano e 180 dias" in pagina.text  # duração recalculada sobre a nova data
