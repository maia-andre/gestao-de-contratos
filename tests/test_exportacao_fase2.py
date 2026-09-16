import json

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Contrato
from app.models_fiscalizacao import Reuniao


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


def _arquivo_com_reuniao(reuniao: dict) -> bytes:
    payload = {
        "contratos": [
            {
                **{
                    "numero": "010/2026",
                    "objeto": "Objeto importado",
                    "contratada_razao_social": "Empresa Importada",
                    "contratada_cnpj": "11.111.111/0001-11",
                    "vigencia_inicio": "2026-01-01",
                    "vigencia_fim": "2026-12-31",
                    "mao_de_obra_exclusiva": True,
                    "valor_global": "1000.00",
                    "modalidade": "Pregão",
                },
                "equipe": [],
                "terceirizados": [],
                "reunioes": [reuniao],
                "pendencias_pre_os": [],
                "ocorrencias": [],
                "cpfs_conhecidos": [],
                "competencias": [],
            }
        ]
    }
    return json.dumps(payload).encode("utf-8")


def test_exportacao_inclui_hora_e_local_da_reuniao():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(
            f"/contratos/{contrato_id}/reunioes",
            data={
                "data": "2026-02-05",
                "hora": "14:30",
                "local": "Sala 3",
                "participantes": "João Silva",
                "resumo": "Pauta inicial.",
            },
        )
        corpo = client.get("/exportar").json()

    reuniao = corpo["contratos"][0]["reunioes"][0]
    assert reuniao["hora"] == "14:30"
    assert reuniao["local"] == "Sala 3"


def test_roundtrip_restaura_hora_e_local():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(
            f"/contratos/{contrato_id}/reunioes",
            data={
                "data": "2026-02-05",
                "hora": "14:30",
                "local": "Sala 3",
                "participantes": "João Silva",
                "resumo": "Pauta inicial.",
            },
        )
        exportado = client.get("/exportar").json()
        resposta = client.post(
            "/importar",
            files={"arquivo": ("contratos.json", json.dumps(exportado).encode("utf-8"), "application/json")},
            follow_redirects=False,
        )
        assert resposta.status_code == 303

    db = SessionLocal()
    try:
        reunioes = db.query(Reuniao).order_by(Reuniao.id).all()
        assert len(reunioes) == 2
        importada = reunioes[-1]
        assert importada.hora == "14:30"
        assert importada.local == "Sala 3"
    finally:
        db.close()


def test_importar_arquivo_da_fase1_sem_hora_e_local_funciona():
    conteudo = _arquivo_com_reuniao(
        {"data": "2026-01-10", "participantes": "Maria Silva", "resumo": "Reunião antiga."}
    )
    with TestClient(app) as client:
        resposta = client.post(
            "/importar",
            files={"arquivo": ("contratos.json", conteudo, "application/json")},
            follow_redirects=False,
        )
        assert resposta.status_code == 303

    db = SessionLocal()
    try:
        reuniao = db.query(Reuniao).order_by(Reuniao.id.desc()).first()
        assert reuniao.resumo == "Reunião antiga."
        assert reuniao.hora is None
        assert reuniao.local is None
    finally:
        db.close()


def test_importar_reuniao_com_hora_invalida_e_rejeitado():
    conteudo = _arquivo_com_reuniao(
        {
            "data": "2026-01-10",
            "hora": "99:99",
            "participantes": "Maria Silva",
            "resumo": "Reunião.",
        }
    )
    with TestClient(app) as client:
        resposta = client.post(
            "/importar",
            files={"arquivo": ("contratos.json", conteudo, "application/json")},
        )
        assert resposta.status_code == 422
        assert "hora inválida" in resposta.text

    db = SessionLocal()
    try:
        assert db.query(Contrato).count() == 0
    finally:
        db.close()
