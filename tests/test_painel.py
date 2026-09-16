from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app


def _dados_contrato(**overrides):
    hoje = date.today()
    dados = {
        "numero": "001/2026",
        "objeto": "Objeto",
        "contratada_razao_social": "Empresa",
        "contratada_cnpj": "00.000.000/0001-00",
        "vigencia_inicio": (hoje - timedelta(days=30)).isoformat(),
        "vigencia_fim": (hoje + timedelta(days=200)).isoformat(),
        "mao_de_obra_exclusiva": "sim",
        "valor_global": "100",
        "modalidade": "Pregão",
    }
    dados.update(overrides)
    return dados


def test_painel_vazio_inicialmente():
    with TestClient(app) as client:
        response = client.get("/painel")
    assert response.status_code == 200
    assert "Nenhum contrato cadastrado" in response.text


def test_painel_lista_contrato_dentro_do_prazo():
    hoje = date.today()
    with TestClient(app) as client:
        client.post(
            "/contratos",
            data=_dados_contrato(numero="D1", vigencia_fim=(hoje + timedelta(days=200)).isoformat()),
        )
        response = client.get("/painel")
    assert "D1" in response.text
    assert "Dentro do prazo" in response.text
    assert "200" in response.text


def test_painel_marca_atencao_no_limite_exato_de_90_dias():
    hoje = date.today()
    with TestClient(app) as client:
        client.post(
            "/contratos",
            data=_dados_contrato(numero="D2", vigencia_fim=(hoje + timedelta(days=90)).isoformat()),
        )
        response = client.get("/painel")
    assert "D2" in response.text
    assert "Atenção" in response.text


def test_painel_marca_dentro_do_prazo_com_91_dias():
    hoje = date.today()
    with TestClient(app) as client:
        client.post(
            "/contratos",
            data=_dados_contrato(numero="D3", vigencia_fim=(hoje + timedelta(days=91)).isoformat()),
        )
        response = client.get("/painel")
    assert "D3" in response.text
    assert "Dentro do prazo" in response.text


def test_painel_marca_atencao_quando_vigencia_vence_hoje():
    hoje = date.today()
    with TestClient(app) as client:
        client.post(
            "/contratos",
            data=_dados_contrato(numero="D5", vigencia_fim=hoje.isoformat()),
        )
        response = client.get("/painel")
    assert "D5" in response.text
    assert "Atenção" in response.text


def test_ce04_contrato_com_vigencia_vencida_aparece_vencido_com_dias_negativos():
    hoje = date.today()
    with TestClient(app) as client:
        client.post(
            "/contratos",
            data=_dados_contrato(
                numero="D4",
                vigencia_inicio=(hoje - timedelta(days=400)).isoformat(),
                vigencia_fim=(hoje - timedelta(days=10)).isoformat(),
            ),
        )
        response = client.get("/painel")
    assert "D4" in response.text
    assert "Vencido" in response.text
    assert "-10" in response.text


def test_painel_lista_multiplos_contratos_simultaneos():
    hoje = date.today()
    with TestClient(app) as client:
        client.post(
            "/contratos",
            data=_dados_contrato(numero="M1", vigencia_fim=(hoje + timedelta(days=10)).isoformat()),
        )
        client.post(
            "/contratos",
            data=_dados_contrato(numero="M2", vigencia_fim=(hoje + timedelta(days=300)).isoformat()),
        )
        response = client.get("/painel")
    assert "M1" in response.text
    assert "M2" in response.text
