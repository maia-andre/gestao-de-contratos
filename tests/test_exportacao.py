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


def _dados_membro(**overrides):
    dados = {
        "nome": "Maria Silva",
        "matricula_cargo": "12345 — Engenheira",
        "lotacao": "Secretaria de Obras",
        "papeis": ["Fiscal Técnico"],
        "data_designacao": "2026-01-05",
        "substituto": "",
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


def _contar_contratos() -> int:
    db = SessionLocal()
    try:
        return db.query(Contrato).count()
    finally:
        db.close()


def test_exportar_todos_os_contratos():
    with TestClient(app) as client:
        _criar_contrato(client, numero="001/2026")
        contrato_2 = _criar_contrato(client, numero="002/2026")
        client.post(f"/contratos/{contrato_2}/equipe", data=_dados_membro())

        response = client.get("/exportar")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "attachment" in response.headers.get("content-disposition", "")

    corpo = response.json()
    assert "contratos" in corpo
    assert len(corpo["contratos"]) == 2
    numeros = {c["numero"] for c in corpo["contratos"]}
    assert numeros == {"001/2026", "002/2026"}

    contrato_com_equipe = next(c for c in corpo["contratos"] if c["numero"] == "002/2026")
    assert len(contrato_com_equipe["equipe"]) == 1
    assert contrato_com_equipe["equipe"][0]["nome"] == "Maria Silva"
    assert contrato_com_equipe["equipe"][0]["papeis"] == ["Fiscal Técnico"]


def test_exportar_um_contrato_especifico():
    with TestClient(app) as client:
        _criar_contrato(client, numero="001/2026")
        contrato_2 = _criar_contrato(client, numero="002/2026")

        response = client.get(f"/contratos/{contrato_2}/exportar")
    assert response.status_code == 200
    corpo = response.json()
    assert len(corpo["contratos"]) == 1
    assert corpo["contratos"][0]["numero"] == "002/2026"


def test_exportar_contrato_inexistente_retorna_404():
    with TestClient(app) as client:
        response = client.get("/contratos/99999/exportar")
    assert response.status_code == 404


def test_importar_restaura_contratos_e_equipe():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client, numero="900/2026")
        client.post(f"/contratos/{contrato_id}/equipe", data=_dados_membro(nome="Ana Souza"))
        exportado = client.get("/exportar").json()

        # Simula restaurar em outra instância: importa o mesmo arquivo de volta.
        conteudo = json.dumps(exportado).encode("utf-8")
        response = client.post(
            "/importar",
            files={"arquivo": ("contratos.json", conteudo, "application/json")},
            follow_redirects=False,
        )
        assert response.status_code == 303

        listagem = client.get("/contratos")
    assert listagem.text.count("900/2026") == 2  # o original + o importado


def test_importar_nao_apaga_dados_existentes():
    with TestClient(app) as client:
        _criar_contrato(client, numero="EXISTENTE")
        payload = {
            "contratos": [
                {
                    **_dados_contrato_exportado(numero="NOVO"),
                }
            ]
        }
        conteudo = json.dumps(payload).encode("utf-8")
        client.post("/importar", files={"arquivo": ("c.json", conteudo, "application/json")})

        listagem = client.get("/contratos")
    assert "EXISTENTE" in listagem.text
    assert "NOVO" in listagem.text


def test_ce05_importar_arquivo_nao_json_e_rejeitado_sem_apagar_dados():
    with TestClient(app) as client:
        _criar_contrato(client, numero="EXISTENTE")
        antes = _contar_contratos()

        response = client.post(
            "/importar",
            files={"arquivo": ("c.json", b"isto n\xe3o \xe9 json v\xe1lido {{{", "application/json")},
        )
        assert response.status_code == 422
        assert "inválido" in response.text.lower() or "corrompido" in response.text.lower()

        depois = _contar_contratos()
    assert depois == antes


def test_ce05_importar_json_com_esquema_invalido_e_rejeitado_sem_apagar_dados():
    with TestClient(app) as client:
        _criar_contrato(client, numero="EXISTENTE")
        antes = _contar_contratos()

        payload = {"isto_nao_e": "o esquema esperado"}
        conteudo = json.dumps(payload).encode("utf-8")
        response = client.post("/importar", files={"arquivo": ("c.json", conteudo, "application/json")})
        assert response.status_code == 422

        depois = _contar_contratos()
    assert depois == antes


def test_importar_com_um_contrato_invalido_nao_importa_nenhum():
    with TestClient(app) as client:
        _criar_contrato(client, numero="EXISTENTE")
        antes = _contar_contratos()

        payload = {
            "contratos": [
                _dados_contrato_exportado(numero="VALIDO"),
                {"numero": "SEM_CAMPOS"},
            ]
        }
        conteudo = json.dumps(payload).encode("utf-8")
        response = client.post("/importar", files={"arquivo": ("c.json", conteudo, "application/json")})
        assert response.status_code == 422

        listagem = client.get("/contratos")
        depois = _contar_contratos()
    assert depois == antes
    assert "VALIDO" not in listagem.text


def _dados_contrato_exportado(**overrides) -> dict:
    dados = {
        "numero": "001/2026",
        "objeto": "Objeto",
        "contratada_razao_social": "Empresa",
        "contratada_cnpj": "00.000.000/0001-00",
        "vigencia_inicio": "2026-01-01",
        "vigencia_fim": "2026-12-31",
        "mao_de_obra_exclusiva": True,
        "valor_global": "100.00",
        "modalidade": "Pregão",
        "equipe": [],
    }
    dados.update(overrides)
    return dados
