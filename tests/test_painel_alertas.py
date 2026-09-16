from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Contrato
from app.prazos import STATUS_ATENCAO, STATUS_DENTRO_DO_PRAZO, STATUS_VENCIDO


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


# RN-04 — certidões (fronteiras exatas)


def test_certidao_sem_data_de_referencia_vencida():
    from app.alertas import alerta_certidao

    status, _ = alerta_certidao(None, 180, 15, date(2026, 8, 4))
    assert status == STATUS_VENCIDO


def test_certidao_no_dia_do_vencimento_em_atencao():
    from app.alertas import alerta_certidao

    ref = date(2026, 8, 4) - timedelta(days=180)  # vence exatamente hoje
    status, _ = alerta_certidao(ref, 180, 15, date(2026, 8, 4))
    assert status == STATUS_ATENCAO


def test_certidao_um_dia_apos_vencimento_vencida():
    from app.alertas import alerta_certidao

    ref = date(2026, 8, 4) - timedelta(days=181)
    status, _ = alerta_certidao(ref, 180, 15, date(2026, 8, 4))
    assert status == STATUS_VENCIDO


def test_certidao_na_janela_de_antecedencia_em_atencao():
    from app.alertas import alerta_certidao

    ref = date(2026, 8, 4) - timedelta(days=165)  # vence em 15 dias
    status, _ = alerta_certidao(ref, 180, 15, date(2026, 8, 4))
    assert status == STATUS_ATENCAO


def test_certidao_fora_da_janela_dentro_do_prazo():
    from app.alertas import alerta_certidao

    ref = date(2026, 8, 4) - timedelta(days=164)  # vence em 16 dias
    status, _ = alerta_certidao(ref, 180, 15, date(2026, 8, 4))
    assert status == STATUS_DENTRO_DO_PRAZO


# RN-03 — prorrogação (notificação e resposta)


def test_notificacao_fora_da_janela_dentro_do_prazo():
    from app.alertas import alerta_notificacao

    status, _ = alerta_notificacao(date(2026, 12, 31), 90, date(2026, 8, 4))
    assert status == STATUS_DENTRO_DO_PRAZO


def test_notificacao_exatamente_na_janela_em_atencao():
    from app.alertas import alerta_notificacao

    # hoje == fim - 90 dias
    fim = date(2026, 8, 4) + timedelta(days=90)
    status, _ = alerta_notificacao(fim, 90, date(2026, 8, 4))
    assert status == STATUS_ATENCAO


def test_resposta_no_dia_limite_em_atencao():
    from app.alertas import alerta_resposta

    status, _ = alerta_resposta(date(2026, 8, 4), date(2026, 8, 4))
    assert status == STATUS_ATENCAO


def test_resposta_apos_o_limite_vencida():
    from app.alertas import alerta_resposta

    status, _ = alerta_resposta(date(2026, 8, 3), date(2026, 8, 4))
    assert status == STATUS_VENCIDO


# RN-06 — GFD/DARF por mês (CE-07 incluso)


def test_gfd_mes_sem_competencia_atencao_a_partir_do_dia_15():
    from app.alertas import alertas_gfd_darf

    # mês 06/2026 sem competência; hoje 15/07 → Atenção
    alertas = alertas_gfd_darf(
        date(2026, 6, 1), date(2026, 12, 31), 20, date(2026, 7, 15), {}
    )
    assert [(a["ano"], a["mes"], a["status"]) for a in alertas] == [
        (2026, 6, STATUS_ATENCAO)
    ]


def test_gfd_mes_sem_competencia_antes_do_dia_15_sem_alerta():
    from app.alertas import alertas_gfd_darf

    alertas = alertas_gfd_darf(
        date(2026, 6, 1), date(2026, 12, 31), 20, date(2026, 7, 14), {}
    )
    assert alertas == []


def test_gfd_apos_dia_limite_vencido():
    from app.alertas import alertas_gfd_darf

    alertas = alertas_gfd_darf(
        date(2026, 6, 1), date(2026, 12, 31), 20, date(2026, 7, 21), {}
    )
    assert alertas[0]["status"] == STATUS_VENCIDO


def test_gfd_no_dia_limite_ainda_em_atencao():
    from app.alertas import alertas_gfd_darf

    alertas = alertas_gfd_darf(
        date(2026, 6, 1), date(2026, 12, 31), 20, date(2026, 7, 20), {}
    )
    assert alertas[0]["status"] == STATUS_ATENCAO


def test_gfd_mes_regular_sem_alerta():
    from app.alertas import alertas_gfd_darf

    alertas = alertas_gfd_darf(
        date(2026, 6, 1), date(2026, 12, 31), 20, date(2026, 7, 25), {(2026, 6): True}
    )
    assert alertas == []


def test_gfd_competencia_criada_mas_pendente_gera_alerta():
    from app.alertas import alertas_gfd_darf

    alertas = alertas_gfd_darf(
        date(2026, 6, 1), date(2026, 12, 31), 20, date(2026, 7, 25), {(2026, 6): False}
    )
    assert alertas[0]["status"] == STATUS_VENCIDO


def test_gfd_ignora_meses_fora_da_vigencia():
    from app.alertas import alertas_gfd_darf

    # vigência de junho apenas; hoje muito depois → só o mês 06 cobrado
    alertas = alertas_gfd_darf(
        date(2026, 6, 1), date(2026, 6, 30), 20, date(2026, 12, 1), {}
    )
    assert [(a["ano"], a["mes"]) for a in alertas] == [(2026, 6)]


# RN-09 — Relatório Final pendente


def test_relatorio_final_pendente_apos_fim_da_vigencia():
    from app.alertas import relatorio_final_pendente

    assert relatorio_final_pendente(date(2026, 6, 30), False, date(2026, 8, 4)) is True
    assert relatorio_final_pendente(date(2026, 6, 30), True, date(2026, 8, 4)) is False
    assert relatorio_final_pendente(date(2026, 12, 31), False, date(2026, 8, 4)) is False


# Integração — painel (REQ-14, REQ-15, CE-04, CE-06)


def test_painel_mostra_certidoes_sem_registro_com_link():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        painel = client.get("/painel")
    assert "CNDT" in painel.text
    assert "CRF" in painel.text
    assert "sem registro" in painel.text
    assert f"/contratos/{contrato_id}/competencias" in painel.text  # REQ-15


def test_painel_ce04_contrato_ja_dentro_da_janela_de_notificacao():
    hoje = date.today()
    with TestClient(app) as client:
        _criar_contrato(
            client,
            vigencia_inicio=(hoje - timedelta(days=300)).isoformat(),
            vigencia_fim=(hoje + timedelta(days=30)).isoformat(),
        )
        painel = client.get("/painel")
    assert "Notificação de prorrogação a enviar" in painel.text


def test_painel_ce06_mudar_antecedencia_recalcula():
    hoje = date.today()
    with TestClient(app) as client:
        contrato_id = _criar_contrato(
            client,
            vigencia_inicio=(hoje - timedelta(days=100)).isoformat(),
            vigencia_fim=(hoje + timedelta(days=100)).isoformat(),
        )
        antes = client.get("/painel")
        assert "Notificação de prorrogação a enviar" not in antes.text
        client.post(
            f"/contratos/{contrato_id}/configuracoes-prazos",
            data={
                "antecedencia_notificacao_dias": "120",
                "prazo_resposta_dias_uteis": "3",
                "antecedencia_certidoes_dias": "15",
                "antecedencia_semestral_dias": "30",
                "dia_limite_gfd_darf": "20",
            },
        )
        depois = client.get("/painel")
    assert "Notificação de prorrogação a enviar" in depois.text


def test_painel_resposta_em_atraso_e_ciclo_encerrado_some():
    hoje = date.today()
    with TestClient(app) as client:
        contrato_id = _criar_contrato(
            client,
            vigencia_inicio=(hoje - timedelta(days=300)).isoformat(),
            vigencia_fim=(hoje + timedelta(days=30)).isoformat(),
        )
        client.post(
            f"/contratos/{contrato_id}/prorrogacao/envio",
            data={"data_envio": (hoje - timedelta(days=15)).isoformat()},
        )
        painel = client.get("/painel")
        assert "Resposta da contratada em atraso" in painel.text
        # encerramento manual faz os alertas de prorrogação sumirem (REQ-08)
        client.post(f"/contratos/{contrato_id}/prorrogacao/encerrar", data={"observacao": ""})
        depois = client.get("/painel")
    assert "Resposta da contratada" not in depois.text
    assert "Notificação de prorrogação" not in depois.text


def test_painel_relatorio_final_pendente_com_link():
    hoje = date.today()
    with TestClient(app) as client:
        contrato_id = _criar_contrato(
            client,
            vigencia_inicio=(hoje - timedelta(days=400)).isoformat(),
            vigencia_fim=(hoje - timedelta(days=10)).isoformat(),
        )
        painel = client.get("/painel")
        assert "Relatório Final pendente" in painel.text
        assert f"/contratos/{contrato_id}/relatorio-final" in painel.text
        # registrar o parecer remove o alerta
        client.post(
            f"/contratos/{contrato_id}/relatorio-final",
            data={"conceito": "alcancados", "justificativa": "Metas cumpridas.", "licoes": ""},
        )
        depois = client.get("/painel")
    assert "Relatório Final pendente" not in depois.text


def test_painel_gfd_darf_competencia_nao_registrada_ce07():
    hoje = date.today()
    with TestClient(app) as client:
        contrato_id = _criar_contrato(
            client,
            vigencia_inicio=(hoje - timedelta(days=100)).isoformat(),
            vigencia_fim=(hoje + timedelta(days=265)).isoformat(),
        )
        painel = client.get("/painel")
    assert "GFD/DARF" in painel.text
    assert "competência não registrada" in painel.text
    assert f"/contratos/{contrato_id}/competencias" in painel.text


def test_painel_listagem_semestral_vencida_com_link():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)  # marco 01/07/2026, hoje > marco
        painel = client.get("/painel")
    assert "Listagem semestral" in painel.text
    assert f"/contratos/{contrato_id}/listagem-semestral" in painel.text
