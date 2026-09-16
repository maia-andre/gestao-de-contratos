from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Contrato, MembroEquipe
from app.models_fiscalizacao import Competencia, PendenciaPreOS, RelatorioTecnico


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


def _criar_contrato_com_competencia_e_fiscal(client, mes_ano="2026-05") -> tuple[int, int, int]:
    client.post("/contratos", data=_dados_contrato())
    db = SessionLocal()
    try:
        contrato_id = db.query(Contrato).order_by(Contrato.id.desc()).first().id
    finally:
        db.close()

    client.post(f"/contratos/{contrato_id}/competencias", data={"mes_ano": mes_ano})
    db = SessionLocal()
    try:
        ano, mes = (int(p) for p in mes_ano.split("-"))
        competencia_id = db.query(Competencia).filter_by(contrato_id=contrato_id, ano=ano, mes=mes).first().id
    finally:
        db.close()

    client.post(f"/contratos/{contrato_id}/equipe", data=_dados_membro())
    db = SessionLocal()
    try:
        fiscal_id = db.query(MembroEquipe).filter_by(contrato_id=contrato_id, nome="Maria Silva").first().id
    finally:
        db.close()

    return contrato_id, competencia_id, fiscal_id


def _url_relatorio(contrato_id, competencia_id):
    return f"/contratos/{contrato_id}/competencias/{competencia_id}/relatorio-tecnico"


def _marcar_pendencias_pre_os_ok(client, contrato_id):
    client.get(f"/contratos/{contrato_id}/pendencias-pre-os")
    db = SessionLocal()
    try:
        ids = [item.id for item in db.query(PendenciaPreOS).filter_by(contrato_id=contrato_id).all()]
    finally:
        db.close()
    for item_id in ids:
        client.post(f"/contratos/{contrato_id}/pendencias-pre-os/{item_id}/alternar")


def test_req09_select_de_fiscal_responsavel_so_lista_fiscais_tecnicos_do_contrato():
    with TestClient(app) as client:
        contrato_id, competencia_id, fiscal_id = _criar_contrato_com_competencia_e_fiscal(client)
        client.post(
            f"/contratos/{contrato_id}/equipe",
            data=_dados_membro(nome="Beto Administrativo", papeis=["Fiscal Administrativo"]),
        )
        pagina = client.get(_url_relatorio(contrato_id, competencia_id))
    assert f'<option value="{fiscal_id}"' in pagina.text
    assert "Maria Silva" in pagina.text
    assert "Beto Administrativo" not in pagina.text


def test_req09_conclusao_sugerida_regular_quando_pendencias_ok_e_sem_ocorrencias():
    with TestClient(app) as client:
        contrato_id, competencia_id, _ = _criar_contrato_com_competencia_e_fiscal(client)
        _marcar_pendencias_pre_os_ok(client, contrato_id)
        pagina = client.get(_url_relatorio(contrato_id, competencia_id))
    assert 'value="regular" selected' in pagina.text


def test_rn10_irregular_quando_ha_ocorrencia_grave_dentro_do_mes_da_competencia():
    with TestClient(app) as client:
        contrato_id, competencia_id, _ = _criar_contrato_com_competencia_e_fiscal(client, "2026-05")
        client.post(
            f"/contratos/{contrato_id}/ocorrencias",
            data={"data": "2026-05-15", "descricao": "Atraso grave no cronograma", "gravidade": "grave"},
        )
        pagina = client.get(_url_relatorio(contrato_id, competencia_id))
    assert 'value="irregular" selected' in pagina.text


def test_rn10_ocorrencia_grave_fora_do_mes_da_competencia_nao_torna_irregular():
    with TestClient(app) as client:
        contrato_id, competencia_id, _ = _criar_contrato_com_competencia_e_fiscal(client, "2026-05")
        _marcar_pendencias_pre_os_ok(client, contrato_id)
        client.post(
            f"/contratos/{contrato_id}/ocorrencias",
            data={"data": "2026-04-10", "descricao": "Ocorrência de abril", "gravidade": "grave"},
        )
        pagina = client.get(_url_relatorio(contrato_id, competencia_id))
    assert 'value="regular" selected' in pagina.text


def test_rn10_irregular_quando_recebimento_provisorio_recusado():
    with TestClient(app) as client:
        contrato_id, competencia_id, _ = _criar_contrato_com_competencia_e_fiscal(client)
        client.post(
            f"/contratos/{contrato_id}/competencias/{competencia_id}/recebimento-provisorio",
            data={"data": "2026-05-30", "decisao": "recusado", "observacao": "Serviço incompleto."},
        )
        pagina = client.get(_url_relatorio(contrato_id, competencia_id))
    assert 'value="irregular" selected' in pagina.text


def test_rn10_regular_com_ressalvas_quando_recebimento_aceito_com_ressalva():
    with TestClient(app) as client:
        contrato_id, competencia_id, _ = _criar_contrato_com_competencia_e_fiscal(client)
        _marcar_pendencias_pre_os_ok(client, contrato_id)
        client.post(
            f"/contratos/{contrato_id}/competencias/{competencia_id}/recebimento-provisorio",
            data={"data": "2026-05-30", "decisao": "aceito_com_ressalva", "observacao": ""},
        )
        pagina = client.get(_url_relatorio(contrato_id, competencia_id))
    assert 'value="regular_com_ressalvas" selected' in pagina.text


def test_req09_registrar_avaliacao_conclusao_e_ateste_com_sucesso():
    with TestClient(app) as client:
        contrato_id, competencia_id, fiscal_id = _criar_contrato_com_competencia_e_fiscal(client)

        resposta = client.post(
            _url_relatorio(contrato_id, competencia_id),
            data={
                "avaliacao": "Cronograma dentro do previsto, qualidade adequada.",
                "conclusao": "regular",
                "fiscal_responsavel_id": str(fiscal_id),
                "data_ateste": "2026-06-01",
            },
            follow_redirects=False,
        )
        assert resposta.status_code == 303

        db = SessionLocal()
        try:
            salvo = db.query(RelatorioTecnico).filter_by(competencia_id=competencia_id).first()
            assert salvo.avaliacao == "Cronograma dentro do previsto, qualidade adequada."
            assert salvo.conclusao == "regular"
            assert salvo.fiscal_responsavel_id == fiscal_id
        finally:
            db.close()


def test_req09_fiscal_responsavel_que_nao_e_fiscal_tecnico_do_contrato_e_bloqueado_com_422():
    with TestClient(app) as client:
        contrato_id, competencia_id, _ = _criar_contrato_com_competencia_e_fiscal(client)
        client.post(
            f"/contratos/{contrato_id}/equipe",
            data=_dados_membro(nome="Beto Administrativo", papeis=["Fiscal Administrativo"]),
        )
        db = SessionLocal()
        try:
            beto_id = db.query(MembroEquipe).filter_by(nome="Beto Administrativo").first().id
        finally:
            db.close()

        resposta = client.post(
            _url_relatorio(contrato_id, competencia_id),
            data={
                "avaliacao": "Texto",
                "conclusao": "regular",
                "fiscal_responsavel_id": str(beto_id),
                "data_ateste": "2026-06-01",
            },
        )
    assert resposta.status_code == 422


def test_req09_avaliacao_ausente_e_bloqueada_com_422():
    with TestClient(app) as client:
        contrato_id, competencia_id, fiscal_id = _criar_contrato_com_competencia_e_fiscal(client)

        resposta = client.post(
            _url_relatorio(contrato_id, competencia_id),
            data={
                "avaliacao": "",
                "conclusao": "regular",
                "fiscal_responsavel_id": str(fiscal_id),
                "data_ateste": "2026-06-01",
            },
        )
    assert resposta.status_code == 422


def test_req27_relatorio_contem_identificacao_avaliacao_conclusao_e_ateste():
    with TestClient(app) as client:
        contrato_id, competencia_id, fiscal_id = _criar_contrato_com_competencia_e_fiscal(client)
        client.post(
            _url_relatorio(contrato_id, competencia_id),
            data={
                "avaliacao": "Execução conforme cronograma pactuado.",
                "conclusao": "regular",
                "fiscal_responsavel_id": str(fiscal_id),
                "data_ateste": "2026-06-01",
            },
        )
        pagina = client.get(_url_relatorio(contrato_id, competencia_id))
    assert "001/2026" in pagina.text
    assert "05/2026" in pagina.text
    assert "Execução conforme cronograma pactuado." in pagina.text
    assert "Maria Silva" in pagina.text
    assert "2026-06-01" in pagina.text


def test_relatorio_tecnico_de_competencia_inexistente_retorna_404():
    with TestClient(app) as client:
        contrato_id, _, _ = _criar_contrato_com_competencia_e_fiscal(client)
        resposta = client.get(_url_relatorio(contrato_id, 99999))
    assert resposta.status_code == 404
