from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Contrato
from app.terceirizados import normalizar_cpf


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


def _upload_csv(client, contrato_id, conteudo: str, follow_redirects: bool = True):
    return client.post(
        f"/contratos/{contrato_id}/terceirizados/importar",
        files={"arquivo": ("lista.csv", conteudo.encode("utf-8"), "text/csv")},
        follow_redirects=follow_redirects,
    )


def test_normalizar_cpf_remove_pontuacao():
    assert normalizar_cpf("123.456.789-01") == "12345678901"
    assert normalizar_cpf("12345678901") == "12345678901"


def test_listagem_vazia_inicialmente():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.get(f"/contratos/{contrato_id}/terceirizados")
    assert response.status_code == 200
    assert "Nenhum terceirizado cadastrado" in response.text


def test_importar_csv_valido_lista_terceirizados():
    csv_conteudo = (
        "cpf;nome;cargo;salario_base;data_admissao;data_desligamento\n"
        "123.456.789-01;Maria Silva;Auxiliar de Limpeza;1500.00;2025-01-10;\n"
        "987.654.321-00;João Souza;Porteiro;1800.00;2024-06-01;2026-03-15\n"
    )
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = _upload_csv(client, contrato_id, csv_conteudo, follow_redirects=False)
        assert response.status_code == 303
        listagem = client.get(f"/contratos/{contrato_id}/terceirizados")
    assert "Maria Silva" in listagem.text
    assert "João Souza" in listagem.text


def test_ce01_linha_invalida_no_csv_vai_para_lista_de_erros_sem_travar_as_demais():
    csv_conteudo = (
        "cpf;nome;cargo;salario_base;data_admissao;data_desligamento\n"
        "123.456.789-01;Maria Silva;Auxiliar de Limpeza;1500.00;2025-01-10;\n"
        "123;Nome Incompleto;Cargo X;abc;2025-01-10;\n"
    )
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = _upload_csv(client, contrato_id, csv_conteudo)
        listagem = client.get(f"/contratos/{contrato_id}/terceirizados")
    assert "Linha 3" in response.text
    assert "Maria Silva" in listagem.text
    assert "Nome Incompleto" not in listagem.text


def test_ce02_rn07_cpf_duplicado_no_csv_so_a_primeira_linha_e_importada():
    csv_conteudo = (
        "cpf;nome;cargo;salario_base;data_admissao;data_desligamento\n"
        "123.456.789-01;Maria Silva;Auxiliar de Limpeza;1500.00;2025-01-10;\n"
        "12345678901;Maria Silva Duplicada;Auxiliar de Limpeza;1500.00;2025-01-10;\n"
    )
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = _upload_csv(client, contrato_id, csv_conteudo)
        listagem = client.get(f"/contratos/{contrato_id}/terceirizados")
    assert "CPF duplicado" in response.text
    assert "Maria Silva" in listagem.text
    assert "Maria Silva Duplicada" not in listagem.text


def test_cadastrar_terceirizado_manualmente():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/terceirizados",
            data={
                "cpf": "111.222.333-44",
                "nome": "Ana Souza",
                "cargo": "Recepcionista",
                "salario_base": "2000.00",
                "data_admissao": "2025-02-01",
                "data_desligamento": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        listagem = client.get(f"/contratos/{contrato_id}/terceirizados")
    assert "Ana Souza" in listagem.text


def test_cadastro_manual_com_cpf_invalido_e_rejeitado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/terceirizados",
            data={
                "cpf": "123",
                "nome": "Ana Souza",
                "cargo": "Recepcionista",
                "salario_base": "2000.00",
                "data_admissao": "2025-02-01",
                "data_desligamento": "",
            },
        )
    assert response.status_code == 422
    assert "cpf" in response.text.lower() or "CPF" in response.text


def test_editar_terceirizado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(
            f"/contratos/{contrato_id}/terceirizados",
            data={
                "cpf": "111.222.333-44",
                "nome": "Ana Souza",
                "cargo": "Recepcionista",
                "salario_base": "2000.00",
                "data_admissao": "2025-02-01",
                "data_desligamento": "",
            },
        )
        db = SessionLocal()
        from app.models_fiscalizacao import Terceirizado

        try:
            terceirizado_id = db.query(Terceirizado).first().id
        finally:
            db.close()
        response = client.post(
            f"/contratos/{contrato_id}/terceirizados/{terceirizado_id}/editar",
            data={
                "cpf": "111.222.333-44",
                "nome": "Ana Souza Junior",
                "cargo": "Recepcionista",
                "salario_base": "2200.00",
                "data_admissao": "2025-02-01",
                "data_desligamento": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        listagem = client.get(f"/contratos/{contrato_id}/terceirizados")
    assert "Ana Souza Junior" in listagem.text


def test_remover_terceirizado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(
            f"/contratos/{contrato_id}/terceirizados",
            data={
                "cpf": "111.222.333-44",
                "nome": "Ana Souza",
                "cargo": "Recepcionista",
                "salario_base": "2000.00",
                "data_admissao": "2025-02-01",
                "data_desligamento": "",
            },
        )
        db = SessionLocal()
        from app.models_fiscalizacao import Terceirizado

        try:
            terceirizado_id = db.query(Terceirizado).first().id
        finally:
            db.close()
        response = client.post(
            f"/contratos/{contrato_id}/terceirizados/{terceirizado_id}/remover",
            follow_redirects=False,
        )
        assert response.status_code == 303
        listagem = client.get(f"/contratos/{contrato_id}/terceirizados")
    assert "Ana Souza" not in listagem.text


def test_terceirizados_de_contrato_inexistente_retorna_404():
    with TestClient(app) as client:
        response = client.get("/contratos/99999/terceirizados")
    assert response.status_code == 404
