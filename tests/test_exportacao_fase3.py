import io
import json

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


def _montar_cenario_fase3(client, contrato_id: int) -> None:
    """Configuração alterada, ciclo com aditivo (gera histórico + novo ciclo), parecer e entrega."""
    client.post(
        f"/contratos/{contrato_id}/configuracoes-prazos",
        data={
            "antecedencia_notificacao_dias": "120",
            "prazo_resposta_dias_uteis": "5",
            "antecedencia_certidoes_dias": "10",
            "antecedencia_semestral_dias": "45",
            "dia_limite_gfd_darf": "25",
        },
    )
    client.post(f"/contratos/{contrato_id}/prorrogacao/envio", data={"data_envio": "2026-08-04"})
    client.post(
        f"/contratos/{contrato_id}/prorrogacao/resposta",
        data={"data_resposta": "2026-08-06", "teor": "com_interesse"},
    )
    client.post(
        f"/contratos/{contrato_id}/prorrogacao/aditivo",
        data={"nova_vigencia_fim": "2027-12-31"},
    )
    client.post(
        f"/contratos/{contrato_id}/relatorio-final",
        data={
            "conceito": "parcialmente",
            "justificativa": "Atendido com ressalvas.",
            "licoes": "Rever dimensionamento da equipe.",
        },
    )
    client.post(
        f"/contratos/{contrato_id}/listagem-semestral",
        data={"data": "2026-06-15", "observacao": "Protocolo 789"},
    )


def _exportar(client, contrato_id: int) -> dict:
    resposta = client.get(f"/contratos/{contrato_id}/exportar")
    assert resposta.status_code == 200
    return json.loads(resposta.content)


def _importar(client, payload: dict):
    arquivo = io.BytesIO(json.dumps(payload).encode("utf-8"))
    return client.post(
        "/importar",
        files={"arquivo": ("backup.json", arquivo, "application/json")},
        follow_redirects=False,
    )


def _contrato_base_importacao(**extras) -> dict:
    base = {
        "numero": "020/2026",
        "objeto": "Objeto importado",
        "contratada_razao_social": "Empresa Importada",
        "contratada_cnpj": "11.111.111/0001-11",
        "vigencia_inicio": "2026-01-01",
        "vigencia_fim": "2026-12-31",
        "mao_de_obra_exclusiva": True,
        "valor_global": "1000.00",
        "modalidade": "Pregão",
        "equipe": [],
        "terceirizados": [],
        "reunioes": [],
        "pendencias_pre_os": [],
        "ocorrencias": [],
        "cpfs_conhecidos": [],
        "competencias": [],
    }
    base.update(extras)
    return base


# REQ-16 — export contém os dados novos


def test_export_inclui_dados_da_fase3():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _montar_cenario_fase3(client, contrato_id)
        dados = _exportar(client, contrato_id)

    exportado = dados["contratos"][0]
    assert exportado["configuracoes_prazos"]["antecedencia_notificacao_dias"] == 120
    assert exportado["configuracoes_prazos"]["dia_limite_gfd_darf"] == 25

    ciclos = exportado["ciclos_prorrogacao"]
    assert len(ciclos) == 2
    assert ciclos[0]["estado"] == "aditivo_assinado"
    assert ciclos[0]["data_envio_notificacao"] == "2026-08-04"
    assert ciclos[0]["teor_resposta"] == "com_interesse"
    assert ciclos[0]["vigencia_fim_anterior"] == "2026-12-31"
    assert ciclos[0]["nova_vigencia_fim"] == "2027-12-31"
    assert ciclos[1]["estado"] == "aguardando_notificacao"

    assert exportado["relatorio_final"] == {
        "conceito": "parcialmente",
        "justificativa": "Atendido com ressalvas.",
        "licoes": "Rever dimensionamento da equipe.",
    }
    assert exportado["entregas_listagem_semestral"] == [
        {"data": "2026-06-15", "observacao": "Protocolo 789"}
    ]


# REQ-16 — round-trip restaura tudo (import cria contrato novo)


def test_round_trip_restaura_dados_da_fase3():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _montar_cenario_fase3(client, contrato_id)
        dados = _exportar(client, contrato_id)

        resposta = _importar(client, dados)
        assert resposta.status_code == 303

        db = SessionLocal()
        try:
            novo_id = db.query(Contrato).order_by(Contrato.id.desc()).first().id
        finally:
            db.close()
        assert novo_id != contrato_id

        config = client.get(f"/contratos/{novo_id}/configuracoes-prazos")
        assert 'name="antecedencia_notificacao_dias" value="120"' in config.text
        assert 'name="dia_limite_gfd_darf" value="25"' in config.text

        ciclo = client.get(f"/contratos/{novo_id}/prorrogacao")
        assert "Aguardando notificação" in ciclo.text  # ciclo corrente restaurado
        assert "Histórico de prorrogações" in ciclo.text
        assert "31/12/2026" in ciclo.text and "31/12/2027" in ciclo.text

        parecer = client.get(f"/contratos/{novo_id}/relatorio-final")
        assert "Atendido com ressalvas." in parecer.text
        assert "Rever dimensionamento da equipe." in parecer.text

        listagem = client.get(f"/contratos/{novo_id}/listagem-semestral")
        assert "15/06/2026" in listagem.text
        assert "Protocolo 789" in listagem.text


# CE-08 — arquivo de fase anterior importa com padrões e ciclo novo


def test_importar_arquivo_de_fase_anterior():
    with TestClient(app) as client:
        payload = {"contratos": [_contrato_base_importacao()]}  # sem chaves da Fase 3
        resposta = _importar(client, payload)
        assert resposta.status_code == 303

        db = SessionLocal()
        try:
            novo_id = db.query(Contrato).order_by(Contrato.id.desc()).first().id
        finally:
            db.close()

        config = client.get(f"/contratos/{novo_id}/configuracoes-prazos")
        assert 'name="antecedencia_notificacao_dias" value="90"' in config.text

        ciclo = client.get(f"/contratos/{novo_id}/prorrogacao")
        assert "Aguardando notificação" in ciclo.text


# Entradas inválidas nos blocos novos


def test_importar_ciclo_com_estado_invalido_rejeitado():
    with TestClient(app) as client:
        payload = {
            "contratos": [
                _contrato_base_importacao(
                    ciclos_prorrogacao=[{"estado": "estado_inexistente"}]
                )
            ]
        }
        resposta = _importar(client, payload)
    assert resposta.status_code == 422
    assert "estado de ciclo inválido" in resposta.text


def test_importar_configuracao_invalida_rejeitada():
    with TestClient(app) as client:
        payload = {
            "contratos": [
                _contrato_base_importacao(
                    configuracoes_prazos={
                        "antecedencia_notificacao_dias": 90,
                        "prazo_resposta_dias_uteis": 3,
                        "antecedencia_certidoes_dias": 15,
                        "antecedencia_semestral_dias": 30,
                        "dia_limite_gfd_darf": 40,
                    }
                )
            ]
        }
        resposta = _importar(client, payload)
    assert resposta.status_code == 422


def test_importar_relatorio_final_com_conceito_invalido_rejeitado():
    with TestClient(app) as client:
        payload = {
            "contratos": [
                _contrato_base_importacao(
                    relatorio_final={"conceito": "otimo", "justificativa": "x", "licoes": None}
                )
            ]
        }
        resposta = _importar(client, payload)
    assert resposta.status_code == 422


def test_importar_entrega_sem_data_rejeitada():
    with TestClient(app) as client:
        payload = {
            "contratos": [
                _contrato_base_importacao(
                    entregas_listagem_semestral=[{"observacao": "sem data"}]
                )
            ]
        }
        resposta = _importar(client, payload)
    assert resposta.status_code == 422
