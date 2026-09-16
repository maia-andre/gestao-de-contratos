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


def test_listagem_vazia_inicialmente():
    with TestClient(app) as client:
        response = client.get("/contratos")
    assert response.status_code == 200
    assert "Nenhum contrato cadastrado" in response.text


def test_formulario_cadastro_em_portugues():
    with TestClient(app) as client:
        response = client.get("/contratos/novo")
    assert response.status_code == 200
    corpo = response.text.lower()
    for rotulo in [
        "número",
        "objeto",
        "razão social",
        "cnpj",
        "vigência",
        "mão de obra exclusiva",
        "valor global",
        "modalidade",
    ]:
        assert rotulo in corpo


def test_cadastrar_contrato_e_ver_na_listagem():
    with TestClient(app) as client:
        response = client.post("/contratos", data=_dados_validos(), follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/contratos"

        listagem = client.get("/contratos")
    assert "001/2026" in listagem.text
    assert "Limpa Tudo Serviços Ltda" in listagem.text
    assert "Pregão eletrônico" in listagem.text


def test_suporta_multiplos_contratos_simultaneos():
    with TestClient(app) as client:
        client.post("/contratos", data=_dados_validos(numero="001/2026"))
        client.post(
            "/contratos",
            data=_dados_validos(numero="002/2026", contratada_razao_social="Outra Empresa Ltda"),
        )
        listagem = client.get("/contratos")
    assert "001/2026" in listagem.text
    assert "002/2026" in listagem.text
    assert "Outra Empresa Ltda" in listagem.text


def test_contrato_persiste_no_sqlite():
    with TestClient(app) as client:
        client.post("/contratos", data=_dados_validos(numero="777/2026"))

    db = SessionLocal()
    try:
        contrato = db.query(Contrato).filter_by(numero="777/2026").first()
        assert contrato is not None
        assert contrato.contratada_cnpj == "12.345.678/0001-90"
        assert contrato.mao_de_obra_exclusiva is True
    finally:
        db.close()


def test_ce01_data_fim_anterior_ao_inicio_e_rejeitada():
    with TestClient(app) as client:
        response = client.post(
            "/contratos",
            data=_dados_validos(vigencia_inicio="2026-06-01", vigencia_fim="2026-01-01"),
        )
        listagem = client.get("/contratos")
    assert response.status_code == 422
    assert "anterior" in response.text.lower()
    assert "Nenhum contrato cadastrado" in listagem.text


def test_data_fim_igual_a_data_inicio_e_aceita():
    with TestClient(app) as client:
        response = client.post(
            "/contratos",
            data=_dados_validos(numero="888/2026", vigencia_inicio="2026-05-01", vigencia_fim="2026-05-01"),
            follow_redirects=False,
        )
    assert response.status_code == 303


def test_ce02_valor_negativo_e_rejeitado():
    with TestClient(app) as client:
        response = client.post("/contratos", data=_dados_validos(valor_global="-1"))
        listagem = client.get("/contratos")
    assert response.status_code == 422
    assert "negativo" in response.text.lower()
    assert "Nenhum contrato cadastrado" in listagem.text


def test_valor_global_zero_e_aceito():
    with TestClient(app) as client:
        response = client.post(
            "/contratos",
            data=_dados_validos(numero="999/2026", valor_global="0"),
            follow_redirects=False,
        )
    assert response.status_code == 303


def test_campo_obrigatorio_ausente_e_rejeitado():
    with TestClient(app) as client:
        response = client.post("/contratos", data=_dados_validos(numero=""))
        listagem = client.get("/contratos")
    assert response.status_code == 422
    assert "obrigat" in response.text.lower()
    assert "Nenhum contrato cadastrado" in listagem.text
