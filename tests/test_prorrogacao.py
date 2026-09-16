from datetime import date

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


def _criar_contrato_direto_no_banco() -> int:
    """Simula um contrato de fase anterior, criado antes do ciclo existir."""
    db = SessionLocal()
    try:
        contrato = Contrato(
            numero="099/2025",
            objeto="Vigilância patrimonial",
            contratada_razao_social="Segurança Total Ltda",
            contratada_cnpj="98.765.432/0001-10",
            vigencia_inicio=date(2025, 1, 1),
            vigencia_fim=date(2026, 6, 30),
            mao_de_obra_exclusiva=True,
            valor_global=200000,
            modalidade="Pregão eletrônico",
        )
        db.add(contrato)
        db.commit()
        return contrato.id
    finally:
        db.close()


# REQ-01 — ciclo em "aguardando notificação", estado visível na tela do contrato


def test_contrato_novo_exibe_ciclo_aguardando_notificacao():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.get(f"/contratos/{contrato_id}")
    assert response.status_code == 200
    assert "Aguardando notificação" in response.text


def test_contrato_de_fase_anterior_ganha_ciclo_automaticamente():
    with TestClient(app) as client:
        contrato_id = _criar_contrato_direto_no_banco()
        response = client.get(f"/contratos/{contrato_id}")
        assert response.status_code == 200
        assert "Aguardando notificação" in response.text

        pagina_ciclo = client.get(f"/contratos/{contrato_id}/prorrogacao")
    assert pagina_ciclo.status_code == 200
    assert "Aguardando notificação" in pagina_ciclo.text


def test_pagina_do_ciclo_mostra_estado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.get(f"/contratos/{contrato_id}/prorrogacao")
    assert response.status_code == 200
    assert "Aguardando notificação" in response.text


def test_ciclo_nao_e_duplicado_em_acessos_repetidos():
    from app.models_gestor import CicloProrrogacao

    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.get(f"/contratos/{contrato_id}")
        client.get(f"/contratos/{contrato_id}/prorrogacao")
        client.get(f"/contratos/{contrato_id}")
        db = SessionLocal()
        try:
            ciclos = db.query(CicloProrrogacao).filter_by(contrato_id=contrato_id).count()
        finally:
            db.close()
    assert ciclos == 1


def test_pagina_do_ciclo_de_contrato_inexistente_retorna_404():
    with TestClient(app) as client:
        response = client.get("/contratos/9999/prorrogacao")
    assert response.status_code == 404


# REQ-02 — configurações de prazos com padrões, editáveis e persistidas


def test_configuracoes_mostram_padroes():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.get(f"/contratos/{contrato_id}/configuracoes-prazos")
    assert response.status_code == 200
    assert 'name="antecedencia_notificacao_dias" value="90"' in response.text
    assert 'name="prazo_resposta_dias_uteis" value="3"' in response.text
    assert 'name="antecedencia_certidoes_dias" value="15"' in response.text
    assert 'name="antecedencia_semestral_dias" value="30"' in response.text
    assert 'name="dia_limite_gfd_darf" value="20"' in response.text


def test_editar_configuracoes_persiste_valores():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/configuracoes-prazos",
            data={
                "antecedencia_notificacao_dias": "120",
                "prazo_resposta_dias_uteis": "5",
                "antecedencia_certidoes_dias": "10",
                "antecedencia_semestral_dias": "45",
                "dia_limite_gfd_darf": "25",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        recarregada = client.get(f"/contratos/{contrato_id}/configuracoes-prazos")
    assert 'name="antecedencia_notificacao_dias" value="120"' in recarregada.text
    assert 'name="prazo_resposta_dias_uteis" value="5"' in recarregada.text
    assert 'name="antecedencia_certidoes_dias" value="10"' in recarregada.text
    assert 'name="antecedencia_semestral_dias" value="45"' in recarregada.text
    assert 'name="dia_limite_gfd_darf" value="25"' in recarregada.text


def test_configuracao_com_valor_nao_numerico_rejeitada():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/configuracoes-prazos",
            data={
                "antecedencia_notificacao_dias": "noventa",
                "prazo_resposta_dias_uteis": "3",
                "antecedencia_certidoes_dias": "15",
                "antecedencia_semestral_dias": "30",
                "dia_limite_gfd_darf": "20",
            },
        )
    assert response.status_code == 422
    assert "Antecedência da notificação" in response.text


def test_configuracao_com_valor_zerado_ou_negativo_rejeitada():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/configuracoes-prazos",
            data={
                "antecedencia_notificacao_dias": "0",
                "prazo_resposta_dias_uteis": "-1",
                "antecedencia_certidoes_dias": "15",
                "antecedencia_semestral_dias": "30",
                "dia_limite_gfd_darf": "20",
            },
        )
    assert response.status_code == 422


def test_configuracao_rejeitada_nao_altera_valores_gravados():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        client.post(
            f"/contratos/{contrato_id}/configuracoes-prazos",
            data={
                "antecedencia_notificacao_dias": "0",
                "prazo_resposta_dias_uteis": "3",
                "antecedencia_certidoes_dias": "15",
                "antecedencia_semestral_dias": "30",
                "dia_limite_gfd_darf": "20",
            },
        )
        recarregada = client.get(f"/contratos/{contrato_id}/configuracoes-prazos")
    assert 'name="antecedencia_notificacao_dias" value="90"' in recarregada.text


def test_dia_limite_fora_do_intervalo_rejeitado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        for dia in ("0", "29"):
            response = client.post(
                f"/contratos/{contrato_id}/configuracoes-prazos",
                data={
                    "antecedencia_notificacao_dias": "90",
                    "prazo_resposta_dias_uteis": "3",
                    "antecedencia_certidoes_dias": "15",
                    "antecedencia_semestral_dias": "30",
                    "dia_limite_gfd_darf": dia,
                },
            )
            assert response.status_code == 422
            assert "entre 1 e 28" in response.text


def test_dia_limite_nos_limites_do_intervalo_aceito():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        for dia in ("1", "28"):
            response = client.post(
                f"/contratos/{contrato_id}/configuracoes-prazos",
                data={
                    "antecedencia_notificacao_dias": "90",
                    "prazo_resposta_dias_uteis": "3",
                    "antecedencia_certidoes_dias": "15",
                    "antecedencia_semestral_dias": "30",
                    "dia_limite_gfd_darf": dia,
                },
                follow_redirects=False,
            )
            assert response.status_code == 303


def test_campo_de_configuracao_ausente_rejeitado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/configuracoes-prazos",
            data={
                "antecedencia_notificacao_dias": "90",
                "prazo_resposta_dias_uteis": "3",
            },
        )
    assert response.status_code == 422


def test_configuracoes_de_contrato_inexistente_retorna_404():
    with TestClient(app) as client:
        response = client.get("/contratos/9999/configuracoes-prazos")
    assert response.status_code == 404


# REQ-12 — pontos de acesso na tela do contrato


def test_tela_do_contrato_tem_links_para_ciclo_e_configuracoes():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.get(f"/contratos/{contrato_id}")
    assert f"/contratos/{contrato_id}/prorrogacao" in response.text
    assert f"/contratos/{contrato_id}/configuracoes-prazos" in response.text
