from datetime import date

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
        return db.query(Contrato).order_by(Contrato.id.desc()).first().id
    finally:
        db.close()


def _criar_membro(client, contrato_id: int, nome: str, papeis: list[str]) -> int:
    client.post(
        f"/contratos/{contrato_id}/equipe",
        data={
            "nome": nome,
            "matricula_cargo": f"999 — {nome}",
            "lotacao": "Secretaria de Administração",
            "papeis": papeis,
            "data_designacao": "2026-01-05",
            "substituto": "",
        },
    )
    db = SessionLocal()
    try:
        return (
            db.query(MembroEquipe)
            .filter_by(contrato_id=contrato_id, nome=nome)
            .first()
            .id
        )
    finally:
        db.close()


# REQ-03 — seleção do emissor com papel Gestor pré-selecionado


def test_selecao_preseleciona_membro_com_papel_gestor():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _criar_membro(client, contrato_id, "Ana Fiscal", ["Fiscal Técnico"])
        gestor_id = _criar_membro(client, contrato_id, "Bruno Gestor", ["Gestor de Contratos"])
        response = client.get(f"/contratos/{contrato_id}/notificacao-prorrogacao")
    assert response.status_code == 200
    assert f'<option value="{gestor_id}" selected>' in response.text
    assert "Bruno Gestor" in response.text
    assert "Ana Fiscal" in response.text


def test_selecao_sem_gestor_nao_preseleciona_ninguem():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _criar_membro(client, contrato_id, "Ana Fiscal", ["Fiscal Técnico"])
        _criar_membro(client, contrato_id, "Caio Fiscal", ["Fiscal Administrativo"])
        response = client.get(f"/contratos/{contrato_id}/notificacao-prorrogacao")
    assert response.status_code == 200
    assert "selected" not in response.text
    assert "Ana Fiscal" in response.text
    assert "Caio Fiscal" in response.text


def test_selecao_com_dois_gestores_nao_preseleciona_ninguem():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _criar_membro(client, contrato_id, "Bruno Gestor", ["Gestor de Contratos"])
        _criar_membro(client, contrato_id, "Dora Gestora", ["Gestor de Contratos"])
        response = client.get(f"/contratos/{contrato_id}/notificacao-prorrogacao")
    assert response.status_code == 200
    assert "selected" not in response.text


# REQ-03 — conteúdo do documento


def test_documento_contem_identificacao_vigencia_prazo_emissao_e_emissor():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        gestor_id = _criar_membro(client, contrato_id, "Bruno Gestor", ["Gestor de Contratos"])
        response = client.get(
            f"/contratos/{contrato_id}/notificacao-prorrogacao",
            params={"emissor_id": gestor_id},
        )
    assert response.status_code == 200
    texto = response.text
    assert "Notificação de Prorrogação" in texto
    assert "001/2026" in texto
    assert "Serviço de limpeza predial" in texto
    assert "Limpa Tudo Serviços Ltda" in texto
    assert "12.345.678/0001-90" in texto
    assert "31/12/2026" in texto  # fim da vigência
    assert "3 dias úteis" in texto  # prazo de resposta configurado (padrão)
    assert date.today().strftime("%d/%m/%Y") in texto  # data de emissão
    assert "Bruno Gestor" in texto
    assert "999 — Bruno Gestor" in texto
    assert "documento__assinatura" in texto


def test_documento_reflete_prazo_de_resposta_configurado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        gestor_id = _criar_membro(client, contrato_id, "Bruno Gestor", ["Gestor de Contratos"])
        client.post(
            f"/contratos/{contrato_id}/configuracoes-prazos",
            data={
                "antecedencia_notificacao_dias": "90",
                "prazo_resposta_dias_uteis": "5",
                "antecedencia_certidoes_dias": "15",
                "antecedencia_semestral_dias": "30",
                "dia_limite_gfd_darf": "20",
            },
        )
        response = client.get(
            f"/contratos/{contrato_id}/notificacao-prorrogacao",
            params={"emissor_id": gestor_id},
        )
    assert "5 dias úteis" in response.text


def test_documento_usa_singular_para_prazo_de_um_dia():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        gestor_id = _criar_membro(client, contrato_id, "Bruno Gestor", ["Gestor de Contratos"])
        client.post(
            f"/contratos/{contrato_id}/configuracoes-prazos",
            data={
                "antecedencia_notificacao_dias": "90",
                "prazo_resposta_dias_uteis": "1",
                "antecedencia_certidoes_dias": "15",
                "antecedencia_semestral_dias": "30",
                "dia_limite_gfd_darf": "20",
            },
        )
        response = client.get(
            f"/contratos/{contrato_id}/notificacao-prorrogacao",
            params={"emissor_id": gestor_id},
        )
    assert "1 dia útil" in response.text
    assert "1 dias úteis" not in response.text


# CE-03 — bloqueio sem equipe; emissor forjado rejeitado


def test_contrato_sem_equipe_bloqueia_geracao():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.get(f"/contratos/{contrato_id}/notificacao-prorrogacao")
    assert response.status_code == 422
    assert "não tem equipe cadastrada" in response.text


def test_emissor_de_outro_contrato_rejeitado():
    with TestClient(app) as client:
        contrato_a = _criar_contrato(client)
        contrato_b = _criar_contrato(client, numero="002/2026")
        membro_de_b = _criar_membro(client, contrato_b, "Eva Externa", ["Fiscal Técnico"])
        _criar_membro(client, contrato_a, "Ana Fiscal", ["Fiscal Técnico"])
        response = client.get(
            f"/contratos/{contrato_a}/notificacao-prorrogacao",
            params={"emissor_id": membro_de_b},
        )
    assert response.status_code == 404


def test_contrato_inexistente_retorna_404():
    with TestClient(app) as client:
        response = client.get("/contratos/9999/notificacao-prorrogacao")
    assert response.status_code == 404


# Ponto de acesso: página do ciclo oferece o link


def test_pagina_do_ciclo_tem_link_para_notificacao():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.get(f"/contratos/{contrato_id}/prorrogacao")
    assert f"/contratos/{contrato_id}/notificacao-prorrogacao" in response.text
