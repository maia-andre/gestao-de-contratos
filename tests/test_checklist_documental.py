from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.checklist_documental import calcular_validade_certidao
from app.database import SessionLocal
from app.main import app
from app.models import Contrato
from app.models_fiscalizacao import Competencia, ItemChecklistDocumental


def test_calcular_validade_retorna_none_para_item_sem_regra_de_validade():
    assert calcular_validade_certidao("gfd_paga", date(2026, 1, 1), date(2026, 6, 1)) is None


def test_calcular_validade_retorna_none_quando_data_referencia_ausente():
    assert calcular_validade_certidao("cndt", None, date(2026, 6, 1)) is None


def test_cndt_valido_no_limite_exato_de_180_dias():
    referencia = date(2026, 1, 1)
    hoje = referencia + timedelta(days=180)
    assert calcular_validade_certidao("cndt", referencia, hoje) == "válido"


def test_cndt_vencido_no_dia_seguinte_ao_limite_de_180_dias():
    referencia = date(2026, 1, 1)
    hoje = referencia + timedelta(days=181)
    assert calcular_validade_certidao("cndt", referencia, hoje) == "vencido"


def test_cndt_vencido_com_190_dias_conforme_definicao_de_concluido_da_spec():
    referencia = date(2026, 1, 1)
    hoje = referencia + timedelta(days=190)
    assert calcular_validade_certidao("cndt", referencia, hoje) == "vencido"


def test_crf_fgts_valido_no_limite_exato_de_30_dias():
    referencia = date(2026, 1, 1)
    hoje = referencia + timedelta(days=30)
    assert calcular_validade_certidao("crf_fgts", referencia, hoje) == "válido"


def test_crf_fgts_vencido_no_dia_seguinte_ao_limite_de_30_dias():
    referencia = date(2026, 1, 1)
    hoje = referencia + timedelta(days=31)
    assert calcular_validade_certidao("crf_fgts", referencia, hoje) == "vencido"


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


def _criar_contrato_com_competencia(client) -> tuple[int, int]:
    client.post("/contratos", data=_dados_contrato())
    db = SessionLocal()
    try:
        contrato_id = db.query(Contrato).order_by(Contrato.id.desc()).first().id
    finally:
        db.close()
    client.post(f"/contratos/{contrato_id}/competencias", data={"mes_ano": "2026-05"})
    db = SessionLocal()
    try:
        competencia_id = db.query(Competencia).filter_by(contrato_id=contrato_id).first().id
    finally:
        db.close()
    return contrato_id, competencia_id


def _url_checklist(contrato_id, competencia_id):
    return f"/contratos/{contrato_id}/competencias/{competencia_id}/checklist"


def test_req23_checklist_e_pre_carregado_com_7_itens():
    with TestClient(app) as client:
        contrato_id, competencia_id = _criar_contrato_com_competencia(client)
        pagina = client.get(_url_checklist(contrato_id, competencia_id))
    assert pagina.status_code == 200
    for rotulo in [
        "CNDT",
        "CRF/FGTS",
        "Certidão RFB/PGFN",
        "GFD paga",
        "DARF pago",
        "Holerites do mês",
        "Comprovantes de salário",
    ]:
        assert rotulo in pagina.text


def test_req23_itens_pre_carregados_comecam_pendentes():
    with TestClient(app) as client:
        contrato_id, competencia_id = _criar_contrato_com_competencia(client)
        client.get(_url_checklist(contrato_id, competencia_id))
        db = SessionLocal()
        try:
            itens = db.query(ItemChecklistDocumental).filter_by(competencia_id=competencia_id).all()
        finally:
            db.close()
    assert len(itens) == 7
    assert all(item.status == "pendente" for item in itens)


def test_req23_alternar_status_de_um_item_para_ok_e_de_volta():
    with TestClient(app) as client:
        contrato_id, competencia_id = _criar_contrato_com_competencia(client)
        client.get(_url_checklist(contrato_id, competencia_id))
        db = SessionLocal()
        try:
            item = db.query(ItemChecklistDocumental).filter_by(
                competencia_id=competencia_id, chave="gfd_paga"
            ).first()
            item_id = item.id
        finally:
            db.close()

        resposta = client.post(
            f"{_url_checklist(contrato_id, competencia_id)}/{item_id}/alternar", follow_redirects=False
        )
        assert resposta.status_code == 303
        db = SessionLocal()
        try:
            item = db.get(ItemChecklistDocumental, item_id)
            assert item.status == "ok"
        finally:
            db.close()

        client.post(f"{_url_checklist(contrato_id, competencia_id)}/{item_id}/alternar")
        db = SessionLocal()
        try:
            item = db.get(ItemChecklistDocumental, item_id)
            assert item.status == "pendente"
        finally:
            db.close()


def test_itens_sem_regra_de_validade_nao_mostram_campo_de_data():
    with TestClient(app) as client:
        contrato_id, competencia_id = _criar_contrato_com_competencia(client)
        pagina = client.get(_url_checklist(contrato_id, competencia_id))
        db = SessionLocal()
        try:
            item = db.query(ItemChecklistDocumental).filter_by(
                competencia_id=competencia_id, chave="darf_pago"
            ).first()
            item_id = item.id
        finally:
            db.close()
    assert f"/checklist/{item_id}/data-referencia" not in pagina.text


def test_req24_cndt_informada_ha_190_dias_mostra_vencido():
    hoje = date.today()
    with TestClient(app) as client:
        contrato_id, competencia_id = _criar_contrato_com_competencia(client)
        client.get(_url_checklist(contrato_id, competencia_id))
        db = SessionLocal()
        try:
            item = db.query(ItemChecklistDocumental).filter_by(
                competencia_id=competencia_id, chave="cndt"
            ).first()
            item_id = item.id
        finally:
            db.close()

        resposta = client.post(
            f"{_url_checklist(contrato_id, competencia_id)}/{item_id}/data-referencia",
            data={"data_referencia": (hoje - timedelta(days=190)).isoformat()},
            follow_redirects=False,
        )
        assert resposta.status_code == 303

        pagina = client.get(_url_checklist(contrato_id, competencia_id))
    assert "vencido" in pagina.text


def test_req24_crf_fgts_informada_ha_15_dias_mostra_valido():
    hoje = date.today()
    with TestClient(app) as client:
        contrato_id, competencia_id = _criar_contrato_com_competencia(client)
        client.get(_url_checklist(contrato_id, competencia_id))
        db = SessionLocal()
        try:
            item = db.query(ItemChecklistDocumental).filter_by(
                competencia_id=competencia_id, chave="crf_fgts"
            ).first()
            item_id = item.id
        finally:
            db.close()

        client.post(
            f"{_url_checklist(contrato_id, competencia_id)}/{item_id}/data-referencia",
            data={"data_referencia": (hoje - timedelta(days=15)).isoformat()},
        )

        pagina = client.get(_url_checklist(contrato_id, competencia_id))
    assert "válido" in pagina.text


def test_data_referencia_invalida_e_bloqueada_com_422():
    with TestClient(app) as client:
        contrato_id, competencia_id = _criar_contrato_com_competencia(client)
        client.get(_url_checklist(contrato_id, competencia_id))
        db = SessionLocal()
        try:
            item = db.query(ItemChecklistDocumental).filter_by(
                competencia_id=competencia_id, chave="cndt"
            ).first()
            item_id = item.id
        finally:
            db.close()

        resposta = client.post(
            f"{_url_checklist(contrato_id, competencia_id)}/{item_id}/data-referencia",
            data={"data_referencia": "não é uma data"},
        )
    assert resposta.status_code == 422


def test_checklist_de_competencia_inexistente_retorna_404():
    with TestClient(app) as client:
        contrato_id, _ = _criar_contrato_com_competencia(client)
        response = client.get(_url_checklist(contrato_id, 99999))
    assert response.status_code == 404
