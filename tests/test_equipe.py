from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Contrato, MembroEquipe


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
        contrato = db.query(Contrato).order_by(Contrato.id.desc()).first()
        return contrato.id
    finally:
        db.close()


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


def test_contrato_pode_ser_salvo_sem_nenhum_membro():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.get(f"/contratos/{contrato_id}")
    assert response.status_code == 200
    assert "Nenhum membro de equipe cadastrado" in response.text


def test_cadastrar_membro_com_um_papel():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/equipe",
            data=_dados_membro(),
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == f"/contratos/{contrato_id}"
        detalhe = client.get(f"/contratos/{contrato_id}")
    assert "Maria Silva" in detalhe.text
    assert "Fiscal Técnico" in detalhe.text


def test_cadastrar_membro_com_multiplos_papeis_acumulaveis():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/equipe",
            data=_dados_membro(nome="João Souza", papeis=["Fiscal Técnico", "Fiscal Administrativo"]),
            follow_redirects=False,
        )
        assert response.status_code == 303
        detalhe = client.get(f"/contratos/{contrato_id}")
    assert "João Souza" in detalhe.text
    assert "Fiscal Técnico" in detalhe.text
    assert "Fiscal Administrativo" in detalhe.text


def test_permite_mais_de_um_fiscal_tecnico_e_mais_de_um_fiscal_administrativo():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(f"/contratos/{contrato_id}/equipe", data=_dados_membro(nome="Fiscal Um", papeis=["Fiscal Técnico"]))
        client.post(f"/contratos/{contrato_id}/equipe", data=_dados_membro(nome="Fiscal Dois", papeis=["Fiscal Técnico"]))
        client.post(f"/contratos/{contrato_id}/equipe", data=_dados_membro(nome="Fiscal Tres", papeis=["Fiscal Administrativo"]))
        client.post(f"/contratos/{contrato_id}/equipe", data=_dados_membro(nome="Fiscal Quatro", papeis=["Fiscal Administrativo"]))
        detalhe = client.get(f"/contratos/{contrato_id}")
    for nome in ["Fiscal Um", "Fiscal Dois", "Fiscal Tres", "Fiscal Quatro"]:
        assert nome in detalhe.text


def test_contrato_pode_nao_ter_fiscal_administrativo():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(f"/contratos/{contrato_id}/equipe", data=_dados_membro(nome="Gestor Um", papeis=["Gestor de Contratos"]))
        detalhe = client.get(f"/contratos/{contrato_id}")
    assert "Gestor Um" in detalhe.text
    assert "Fiscal Administrativo" not in detalhe.text


def test_membro_persiste_no_sqlite():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(f"/contratos/{contrato_id}/equipe", data=_dados_membro())

    db = SessionLocal()
    try:
        membro = db.query(MembroEquipe).filter_by(contrato_id=contrato_id).first()
        assert membro is not None
        assert membro.nome == "Maria Silva"
        assert [p.papel for p in membro.papeis] == ["Fiscal Técnico"]
    finally:
        db.close()


def test_ce03_gestor_e_fiscal_tecnico_na_mesma_pessoa_e_bloqueado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/equipe",
            data=_dados_membro(nome="Ana Souza", papeis=["Gestor de Contratos", "Fiscal Técnico"]),
        )
    assert response.status_code == 422
    corpo = response.text.lower()
    assert "gestor" in corpo
    assert "fiscal" in corpo

    db = SessionLocal()
    try:
        assert db.query(MembroEquipe).filter_by(contrato_id=contrato_id).count() == 0
    finally:
        db.close()


def test_ce03_gestor_e_fiscal_administrativo_na_mesma_pessoa_e_bloqueado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/equipe",
            data=_dados_membro(nome="Ana Souza", papeis=["Gestor de Contratos", "Fiscal Administrativo"]),
        )
    assert response.status_code == 422


def test_membro_precisa_de_pelo_menos_um_papel():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/equipe",
            data=_dados_membro(papeis=[]),
        )
    assert response.status_code == 422
    assert "papel" in response.text.lower()


def test_papel_invalido_e_rejeitado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/equipe",
            data=_dados_membro(papeis=["Papel Inventado"]),
        )
    assert response.status_code == 422


def test_equipe_de_contrato_inexistente_retorna_404():
    with TestClient(app) as client:
        response = client.get("/contratos/99999")
        response_form = client.get("/contratos/99999/equipe/novo")
        response_post = client.post("/contratos/99999/equipe", data=_dados_membro())
    assert response.status_code == 404
    assert response_form.status_code == 404
    assert response_post.status_code == 404
