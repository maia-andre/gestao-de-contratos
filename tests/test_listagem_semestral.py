from datetime import date, timedelta

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


# RN-05 — soma de meses com fixação de dia e geração de marcos


def test_somar_meses_fixa_dia_no_fim_do_mes():
    from app.routers.listagem_semestral import somar_meses

    assert somar_meses(date(2026, 3, 31), 6) == date(2026, 9, 30)
    assert somar_meses(date(2026, 8, 31), 6) == date(2027, 2, 28)
    assert somar_meses(date(2026, 1, 15), 6) == date(2026, 7, 15)


def test_marcos_de_vigencia_de_12_meses():
    from app.routers.listagem_semestral import datas_dos_marcos

    marcos = datas_dos_marcos(date(2026, 1, 1), date(2026, 12, 31))
    assert marcos == [date(2026, 7, 1)]


def test_marcos_de_vigencia_de_13_meses():
    from app.routers.listagem_semestral import datas_dos_marcos

    marcos = datas_dos_marcos(date(2026, 1, 1), date(2027, 1, 31))
    assert marcos == [date(2026, 7, 1), date(2027, 1, 1)]


# CE-05 — vigência curta não tem marco


def test_vigencia_menor_que_6_meses_sem_marco():
    from app.routers.listagem_semestral import datas_dos_marcos

    assert datas_dos_marcos(date(2026, 1, 1), date(2026, 5, 31)) == []


def test_pagina_de_vigencia_curta_mostra_ausencia_de_marcos():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(
            client, vigencia_inicio="2026-01-01", vigencia_fim="2026-05-31"
        )
        response = client.get(f"/contratos/{contrato_id}/listagem-semestral")
    assert response.status_code == 200
    assert "Nenhum marco semestral dentro da vigência" in response.text


# REQ-13 — marcos na página, entrega registrada, cumprimento e histórico


def test_marco_passado_sem_entrega_fica_vencido():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)  # marco 01/07/2026, hoje > marco
        response = client.get(f"/contratos/{contrato_id}/listagem-semestral")
    assert "01/07/2026" in response.text
    assert "Vencido" in response.text


def test_entrega_dentro_do_semestre_cumpre_o_marco():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/listagem-semestral",
            data={"data": "2026-06-15", "observacao": "Listagem entregue via protocolo 123"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        pagina = client.get(f"/contratos/{contrato_id}/listagem-semestral")
    assert "Cumprido" in pagina.text
    assert "Vencido" not in pagina.text
    assert "15/06/2026" in pagina.text
    assert "Listagem entregue via protocolo 123" in pagina.text


def test_entrega_fora_do_semestre_nao_cumpre_o_marco():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        # marco é 01/07/2026; entrega em 20/07 cai fora do semestre (01/01–01/07]
        client.post(
            f"/contratos/{contrato_id}/listagem-semestral",
            data={"data": "2026-07-20", "observacao": ""},
        )
        pagina = client.get(f"/contratos/{contrato_id}/listagem-semestral")
    assert "Vencido" in pagina.text
    assert "20/07/2026" in pagina.text  # mas a entrega fica no histórico


def test_marco_proximo_fica_em_atencao():
    hoje = date.today()
    inicio = hoje - timedelta(days=170)  # marco ~ hoje + 11 a 14 dias
    with TestClient(app) as client:
        contrato_id = _criar_contrato(
            client,
            vigencia_inicio=inicio.isoformat(),
            vigencia_fim=(inicio + timedelta(days=365)).isoformat(),
        )
        response = client.get(f"/contratos/{contrato_id}/listagem-semestral")
    assert "Atenção" in response.text


def test_marco_distante_fica_dentro_do_prazo():
    hoje = date.today()
    inicio = hoje - timedelta(days=60)  # marco ~ hoje + 122 dias
    with TestClient(app) as client:
        contrato_id = _criar_contrato(
            client,
            vigencia_inicio=inicio.isoformat(),
            vigencia_fim=(inicio + timedelta(days=365)).isoformat(),
        )
        response = client.get(f"/contratos/{contrato_id}/listagem-semestral")
    assert "Dentro do prazo" in response.text


def test_antecedencia_configurada_muda_o_status():
    hoje = date.today()
    inicio = hoje - timedelta(days=60)  # marco ~ hoje + 122 dias
    with TestClient(app) as client:
        contrato_id = _criar_contrato(
            client,
            vigencia_inicio=inicio.isoformat(),
            vigencia_fim=(inicio + timedelta(days=365)).isoformat(),
        )
        client.post(
            f"/contratos/{contrato_id}/configuracoes-prazos",
            data={
                "antecedencia_notificacao_dias": "90",
                "prazo_resposta_dias_uteis": "3",
                "antecedencia_certidoes_dias": "15",
                "antecedencia_semestral_dias": "150",
                "dia_limite_gfd_darf": "20",
            },
        )
        response = client.get(f"/contratos/{contrato_id}/listagem-semestral")
    assert "Atenção" in response.text


def test_entrega_sem_data_rejeitada():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/listagem-semestral", data={"data": "", "observacao": ""}
        )
    assert response.status_code == 422
    assert "Data da entrega é obrigatória." in response.text


def test_entrega_com_data_invalida_rejeitada():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.post(
            f"/contratos/{contrato_id}/listagem-semestral",
            data={"data": "ontem", "observacao": ""},
        )
    assert response.status_code == 422
    assert "Data da entrega inválida." in response.text


def test_contrato_inexistente_retorna_404():
    with TestClient(app) as client:
        response = client.get("/contratos/9999/listagem-semestral")
    assert response.status_code == 404


# REQ-12 — ponto de acesso na tela do contrato


def test_tela_do_contrato_tem_link_para_listagem_semestral():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.get(f"/contratos/{contrato_id}")
    assert f"/contratos/{contrato_id}/listagem-semestral" in response.text
