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


def _avancar_ate_resposta(client, contrato_id: int, teor: str) -> None:
    client.post(
        f"/contratos/{contrato_id}/prorrogacao/envio", data={"data_envio": "2026-08-04"}
    )
    client.post(
        f"/contratos/{contrato_id}/prorrogacao/resposta",
        data={"data_resposta": "2026-08-06", "teor": teor},
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


# REQ-06 / RN-08 — aditivo assinado atualiza vigência e abre novo ciclo


def test_aditivo_atualiza_vigencia_e_abre_novo_ciclo():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _avancar_ate_resposta(client, contrato_id, "com_interesse")
        response = client.post(
            f"/contratos/{contrato_id}/prorrogacao/aditivo",
            data={"nova_vigencia_fim": "2027-12-31"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        detalhe = client.get(f"/contratos/{contrato_id}")
        assert "2027-12-31" in detalhe.text  # vigência atualizada

        pagina_ciclo = client.get(f"/contratos/{contrato_id}/prorrogacao")
        assert "Aguardando notificação" in pagina_ciclo.text  # novo ciclo

        painel = client.get("/painel")
        assert "2027-12-31" in painel.text  # painel reflete a nova vigência

    ciclos = _ciclos(contrato_id)
    assert len(ciclos) == 2
    encerrado, novo = ciclos
    assert encerrado.estado == "aditivo_assinado"
    assert str(encerrado.nova_vigencia_fim) == "2027-12-31"
    assert str(encerrado.vigencia_fim_anterior) == "2026-12-31"
    assert novo.estado == "aguardando_notificacao"


def test_aditivo_sem_resposta_com_interesse_rejeitado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(
            f"/contratos/{contrato_id}/prorrogacao/envio", data={"data_envio": "2026-08-04"}
        )
        response = client.post(
            f"/contratos/{contrato_id}/prorrogacao/aditivo",
            data={"nova_vigencia_fim": "2027-12-31"},
        )
    assert response.status_code == 422
    assert "resposta com interesse" in response.text


def test_aditivo_apos_resposta_sem_interesse_rejeitado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _avancar_ate_resposta(client, contrato_id, "sem_interesse")
        response = client.post(
            f"/contratos/{contrato_id}/prorrogacao/aditivo",
            data={"nova_vigencia_fim": "2027-12-31"},
        )
    assert response.status_code == 422


def test_aditivo_sem_data_ou_data_invalida_rejeitado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _avancar_ate_resposta(client, contrato_id, "com_interesse")
        resposta_vazia = client.post(
            f"/contratos/{contrato_id}/prorrogacao/aditivo", data={"nova_vigencia_fim": ""}
        )
        resposta_invalida = client.post(
            f"/contratos/{contrato_id}/prorrogacao/aditivo",
            data={"nova_vigencia_fim": "amanhã"},
        )
    assert resposta_vazia.status_code == 422
    assert "Nova data de fim de vigência é obrigatória." in resposta_vazia.text
    assert resposta_invalida.status_code == 422
    assert "Nova data de fim de vigência inválida." in resposta_invalida.text


# CE-02 / RN-07 — nova data deve ser posterior à vigente


def test_aditivo_com_data_igual_ou_anterior_rejeitado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _avancar_ate_resposta(client, contrato_id, "com_interesse")
        for data in ("2026-12-31", "2026-06-30"):
            response = client.post(
                f"/contratos/{contrato_id}/prorrogacao/aditivo",
                data={"nova_vigencia_fim": data},
            )
            assert response.status_code == 422
            assert "posterior à data de fim vigente" in response.text
    # nada mudou no contrato
    db = SessionLocal()
    try:
        assert str(db.get(Contrato, contrato_id).vigencia_fim) == "2026-12-31"
    finally:
        db.close()


def test_aditivo_um_dia_apos_o_fim_vigente_aceito():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _avancar_ate_resposta(client, contrato_id, "com_interesse")
        response = client.post(
            f"/contratos/{contrato_id}/prorrogacao/aditivo",
            data={"nova_vigencia_fim": "2027-01-01"},
            follow_redirects=False,
        )
    assert response.status_code == 303


# RN-10 / CE-10 — limite de 10 anos: aviso sem bloqueio


def test_aditivo_no_limite_exato_de_10_anos_sem_aviso():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)  # vigência inicia 2026-01-01
        _avancar_ate_resposta(client, contrato_id, "com_interesse")
        response = client.post(
            f"/contratos/{contrato_id}/prorrogacao/aditivo",
            data={"nova_vigencia_fim": "2036-01-01"},  # exatamente 10 anos
        )
    assert "ultrapassa 10 anos" not in response.text


def test_aditivo_que_ultrapassa_10_anos_avisa_e_registra():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _avancar_ate_resposta(client, contrato_id, "com_interesse")
        response = client.post(
            f"/contratos/{contrato_id}/prorrogacao/aditivo",
            data={"nova_vigencia_fim": "2036-01-02"},  # 10 anos + 1 dia
        )
        assert "ultrapassa 10 anos" in response.text
        detalhe = client.get(f"/contratos/{contrato_id}")
    assert "2036-01-02" in detalhe.text  # registro efetivado mesmo com aviso
    ciclos = _ciclos(contrato_id)
    assert ciclos[0].estado == "aditivo_assinado"
    assert len(ciclos) == 2


# REQ-07 — acionamento da área demandante encerra o ciclo


def test_area_demandante_acionada_encerra_ciclo():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _avancar_ate_resposta(client, contrato_id, "sem_interesse")
        response = client.post(
            f"/contratos/{contrato_id}/prorrogacao/area-demandante",
            data={"data_acionamento": "2026-08-10", "observacao": "Memorando 12/2026 à SEURBS"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        pagina = client.get(f"/contratos/{contrato_id}/prorrogacao")
    assert "Área demandante acionada" in pagina.text
    assert "10/08/2026" in pagina.text
    assert "Memorando 12/2026 à SEURBS" in pagina.text
    ciclos = _ciclos(contrato_id)
    assert len(ciclos) == 1  # encerramento sem novo ciclo
    assert ciclos[0].estado == "area_acionada"


def test_area_demandante_sem_observacao_aceita():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _avancar_ate_resposta(client, contrato_id, "sem_interesse")
        response = client.post(
            f"/contratos/{contrato_id}/prorrogacao/area-demandante",
            data={"data_acionamento": "2026-08-10", "observacao": ""},
            follow_redirects=False,
        )
    assert response.status_code == 303


def test_area_demandante_sem_data_rejeitada():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _avancar_ate_resposta(client, contrato_id, "sem_interesse")
        response = client.post(
            f"/contratos/{contrato_id}/prorrogacao/area-demandante",
            data={"data_acionamento": "", "observacao": ""},
        )
    assert response.status_code == 422
    assert "Data do acionamento é obrigatória." in response.text


def test_area_demandante_fora_de_ordem_rejeitada():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _avancar_ate_resposta(client, contrato_id, "com_interesse")
        response = client.post(
            f"/contratos/{contrato_id}/prorrogacao/area-demandante",
            data={"data_acionamento": "2026-08-10", "observacao": ""},
        )
    assert response.status_code == 422
    assert "resposta sem interesse" in response.text
