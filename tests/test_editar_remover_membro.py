from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Contrato, MembroEquipe, PapelMembro


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


def _criar_membro(client, contrato_id: int, **overrides) -> int:
    client.post(f"/contratos/{contrato_id}/equipe", data=_dados_membro(**overrides))
    db = SessionLocal()
    try:
        return (
            db.query(MembroEquipe)
            .filter_by(contrato_id=contrato_id)
            .order_by(MembroEquipe.id.desc())
            .first()
            .id
        )
    finally:
        db.close()


def test_formulario_edicao_membro_vem_pre_preenchido():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        membro_id = _criar_membro(client, contrato_id, substituto="Pedro Alves")
        response = client.get(f"/contratos/{contrato_id}/equipe/{membro_id}/editar")
    assert response.status_code == 200
    assert 'value="Maria Silva"' in response.text
    assert 'value="12345 — Engenheira"' in response.text
    assert 'value="Secretaria de Obras"' in response.text
    assert 'value="2026-01-05"' in response.text
    assert 'value="Pedro Alves"' in response.text
    assert 'value="Fiscal Técnico" checked' in response.text


def test_editar_membro_atualiza_dados():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        membro_id = _criar_membro(client, contrato_id)
        response = client.post(
            f"/contratos/{contrato_id}/equipe/{membro_id}/editar",
            data=_dados_membro(nome="Maria Silva Souza", papeis=["Fiscal Administrativo"]),
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == f"/contratos/{contrato_id}"
        detalhe = client.get(f"/contratos/{contrato_id}")
    assert "Maria Silva Souza" in detalhe.text
    assert "Maria Silva<" not in detalhe.text


def test_editar_membro_persiste_no_sqlite():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        membro_id = _criar_membro(client, contrato_id)
        client.post(
            f"/contratos/{contrato_id}/equipe/{membro_id}/editar",
            data=_dados_membro(lotacao="Secretaria de Educação"),
        )

    db = SessionLocal()
    try:
        membro = db.get(MembroEquipe, membro_id)
        assert membro.lotacao == "Secretaria de Educação"
    finally:
        db.close()


def test_editar_membro_revalida_ce03():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        membro_id = _criar_membro(client, contrato_id, papeis=["Fiscal Técnico"])
        response = client.post(
            f"/contratos/{contrato_id}/equipe/{membro_id}/editar",
            data=_dados_membro(papeis=["Gestor de Contratos", "Fiscal Técnico"]),
        )
    assert response.status_code == 422
    assert "não pode acumular" in response.text.lower()

    db = SessionLocal()
    try:
        membro = db.get(MembroEquipe, membro_id)
        assert [p.papel for p in membro.papeis] == ["Fiscal Técnico"]
    finally:
        db.close()


def test_editar_membro_papel_invalido_e_rejeitado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        membro_id = _criar_membro(client, contrato_id)
        response = client.post(
            f"/contratos/{contrato_id}/equipe/{membro_id}/editar",
            data=_dados_membro(papeis=["Diretor Geral"]),
        )
    assert response.status_code == 422


def test_remover_membro():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        membro_id = _criar_membro(client, contrato_id)
        response = client.post(
            f"/contratos/{contrato_id}/equipe/{membro_id}/remover",
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == f"/contratos/{contrato_id}"
        detalhe = client.get(f"/contratos/{contrato_id}")
    assert "Nenhum membro de equipe cadastrado" in detalhe.text


def test_remover_membro_persiste_no_sqlite_incluindo_papeis():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        membro_id = _criar_membro(client, contrato_id)
        client.post(f"/contratos/{contrato_id}/equipe/{membro_id}/remover")

    db = SessionLocal()
    try:
        assert db.get(MembroEquipe, membro_id) is None
        assert db.query(PapelMembro).filter_by(membro_id=membro_id).count() == 0
    finally:
        db.close()


def test_remover_um_membro_mantem_os_outros():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        membro_1 = _criar_membro(client, contrato_id, nome="Fiscal Um")
        membro_2 = _criar_membro(client, contrato_id, nome="Fiscal Dois")
        client.post(f"/contratos/{contrato_id}/equipe/{membro_1}/remover")
        detalhe = client.get(f"/contratos/{contrato_id}")
    assert "Fiscal Um" not in detalhe.text
    assert "Fiscal Dois" in detalhe.text


def test_editar_remover_membro_de_contrato_inexistente_retorna_404():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        membro_id = _criar_membro(client, contrato_id)
        response_get = client.get(f"/contratos/99999/equipe/{membro_id}/editar")
        response_post = client.post(f"/contratos/99999/equipe/{membro_id}/editar", data=_dados_membro())
        response_remover = client.post(f"/contratos/99999/equipe/{membro_id}/remover")
    assert response_get.status_code == 404
    assert response_post.status_code == 404
    assert response_remover.status_code == 404


def test_editar_remover_membro_inexistente_retorna_404():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response_get = client.get(f"/contratos/{contrato_id}/equipe/99999/editar")
        response_post = client.post(f"/contratos/{contrato_id}/equipe/99999/editar", data=_dados_membro())
        response_remover = client.post(f"/contratos/{contrato_id}/equipe/99999/remover")
    assert response_get.status_code == 404
    assert response_post.status_code == 404
    assert response_remover.status_code == 404


def test_editar_membro_de_outro_contrato_retorna_404():
    with TestClient(app) as client:
        contrato_1 = _criar_contrato(client, numero="001/2026")
        contrato_2 = _criar_contrato(client, numero="002/2026")
        membro_id = _criar_membro(client, contrato_1)
        response = client.get(f"/contratos/{contrato_2}/equipe/{membro_id}/editar")
    assert response.status_code == 404
