from fastapi.testclient import TestClient

from app.main import app


def test_tela_de_parametros_vem_pre_carregada_com_valores_2026():
    with TestClient(app) as client:
        response = client.get("/parametros")
    assert response.status_code == 200
    assert "7,5" in response.text or "0.0750" in response.text or "0,075" in response.text
    assert "8475,55" in response.text or "8475.55" in response.text


def test_editar_parametro_e_persistido():
    with TestClient(app) as client:
        client.get("/parametros")
        response = client.post(
            "/parametros",
            data={
                "aliquota_1": "0.10",
                "limite_1": "1621.00",
                "aliquota_2": "0.09",
                "limite_2": "2902.84",
                "aliquota_3": "0.12",
                "limite_3": "4354.27",
                "aliquota_4": "0.14",
                "limite_4": "8475.55",
                "percentual_fgts": "0.08",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        pagina = client.get("/parametros")
    assert 'value="0.1000"' in pagina.text


def _dados_parametros_validos(**overrides):
    dados = {
        "aliquota_1": "0.0750",
        "limite_1": "1621.00",
        "aliquota_2": "0.0900",
        "limite_2": "2902.84",
        "aliquota_3": "0.1200",
        "limite_3": "4354.27",
        "aliquota_4": "0.1400",
        "limite_4": "8475.55",
        "percentual_fgts": "0.0800",
    }
    dados.update(overrides)
    return dados


def test_aliquota_negativa_e_rejeitada_sem_alterar_parametros_existentes():
    with TestClient(app) as client:
        client.get("/parametros")
        response = client.post("/parametros", data=_dados_parametros_validos(aliquota_1="-0.5"))
        assert response.status_code == 422
        assert "entre 0 e 1" in response.text.lower() or "inválid" in response.text.lower()

        pagina = client.get("/parametros")
    assert 'value="0.0750"' in pagina.text
    assert 'value="-0.5"' not in pagina.text


def test_aliquota_maior_que_1_e_rejeitada():
    with TestClient(app) as client:
        client.get("/parametros")
        response = client.post("/parametros", data=_dados_parametros_validos(aliquota_2="1.5"))
    assert response.status_code == 422


def test_limites_fora_de_ordem_crescente_sao_rejeitados_sem_alterar_parametros_existentes():
    with TestClient(app) as client:
        client.get("/parametros")
        response = client.post(
            "/parametros", data=_dados_parametros_validos(limite_1="3000.00", limite_2="2902.84")
        )
        assert response.status_code == 422
        assert "crescente" in response.text.lower()

        pagina = client.get("/parametros")
    assert 'value="1621.00"' in pagina.text


def test_percentual_fgts_fora_de_0_a_1_e_rejeitado():
    with TestClient(app) as client:
        client.get("/parametros")
        response = client.post("/parametros", data=_dados_parametros_validos(percentual_fgts="-0.1"))
    assert response.status_code == 422


def test_parametros_validos_no_limite_de_0_e_1_sao_aceitos():
    with TestClient(app) as client:
        client.get("/parametros")
        response = client.post(
            "/parametros",
            data=_dados_parametros_validos(aliquota_1="0", percentual_fgts="1"),
            follow_redirects=False,
        )
    assert response.status_code == 303
