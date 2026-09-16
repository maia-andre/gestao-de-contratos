from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Contrato
from app.models_fiscalizacao import Competencia, ConclusaoAdministrativa

CSV_HEADER = (
    "cpf;nome;cargo;salario_base;total_vencimentos;base_inss;base_fgts;"
    "inss_descontado;fgts_depositado;liquido\n"
)


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


def _url_relatorio(contrato_id, competencia_id):
    return f"/contratos/{contrato_id}/competencias/{competencia_id}/relatorio-administrativo"


def _marcar_checklist_todo_ok(client, contrato_id, competencia_id):
    client.get(f"/contratos/{contrato_id}/competencias/{competencia_id}/checklist")
    db = SessionLocal()
    try:
        from app.models_fiscalizacao import ItemChecklistDocumental

        itens = db.query(ItemChecklistDocumental).filter_by(competencia_id=competencia_id).all()
        ids = [item.id for item in itens]
    finally:
        db.close()
    for item_id in ids:
        client.post(
            f"/contratos/{contrato_id}/competencias/{competencia_id}/checklist/{item_id}/alternar"
        )


def test_ce13_relatorio_bloqueado_sem_folha_importada():
    with TestClient(app) as client:
        contrato_id, competencia_id = _criar_contrato_com_competencia(client)
        resposta = client.get(_url_relatorio(contrato_id, competencia_id))
    assert resposta.status_code == 422
    assert "folha" in resposta.text.lower()


def test_req25_conclusao_sugerida_regular_quando_tudo_bate_e_checklist_ok():
    with TestClient(app) as client:
        contrato_id, competencia_id = _criar_contrato_com_competencia(client)
        client.post(
            f"/contratos/{contrato_id}/terceirizados",
            data={
                "cpf": "111.222.333-44",
                "nome": "Ana Souza",
                "cargo": "Auxiliar",
                "salario_base": "1000.00",
                "data_admissao": "2025-01-01",
                "data_desligamento": "",
            },
        )
        csv_conteudo = (
            CSV_HEADER
            + "111.222.333-44;Ana Souza;Auxiliar;1000.00;1000.00;1000.00;1000.00;75.00;80.00;925.00\n"
        )
        client.post(
            f"/contratos/{contrato_id}/competencias/{competencia_id}/folha/importar",
            files={"arquivo": ("folha.csv", csv_conteudo.encode("utf-8"), "text/csv")},
        )
        _marcar_checklist_todo_ok(client, contrato_id, competencia_id)

        pagina = client.get(_url_relatorio(contrato_id, competencia_id))
    assert pagina.status_code == 200
    assert 'value="regular" selected' in pagina.text


def test_req25_conclusao_sugerida_irregular_quando_ha_cpf_ativo_ausente_da_folha():
    with TestClient(app) as client:
        contrato_id, competencia_id = _criar_contrato_com_competencia(client)
        client.post(
            f"/contratos/{contrato_id}/terceirizados",
            data={
                "cpf": "111.222.333-44",
                "nome": "Ana Souza",
                "cargo": "Auxiliar",
                "salario_base": "1000.00",
                "data_admissao": "2025-01-01",
                "data_desligamento": "",
            },
        )
        csv_conteudo = (
            CSV_HEADER
            + "999.888.777-66;Outra Pessoa;Auxiliar;1000.00;1000.00;1000.00;1000.00;75.00;80.00;925.00\n"
        )
        client.post(
            f"/contratos/{contrato_id}/competencias/{competencia_id}/folha/importar",
            files={"arquivo": ("folha.csv", csv_conteudo.encode("utf-8"), "text/csv")},
        )

        pagina = client.get(_url_relatorio(contrato_id, competencia_id))
    assert 'value="irregular" selected' in pagina.text


def test_req25_fiscal_pode_alterar_conclusao_e_fica_salva():
    with TestClient(app) as client:
        contrato_id, competencia_id = _criar_contrato_com_competencia(client)
        csv_conteudo = (
            CSV_HEADER
            + "111.222.333-44;Ana Souza;Auxiliar;1000.00;1000.00;1000.00;1000.00;75.00;80.00;925.00\n"
        )
        client.post(
            f"/contratos/{contrato_id}/competencias/{competencia_id}/folha/importar",
            files={"arquivo": ("folha.csv", csv_conteudo.encode("utf-8"), "text/csv")},
        )

        resposta = client.post(
            f"{_url_relatorio(contrato_id, competencia_id)}/conclusao",
            data={"conclusao": "irregular"},
            follow_redirects=False,
        )
        assert resposta.status_code == 303

        db = SessionLocal()
        try:
            salvo = db.query(ConclusaoAdministrativa).filter_by(competencia_id=competencia_id).first()
            assert salvo.conclusao == "irregular"
        finally:
            db.close()

        pagina = client.get(_url_relatorio(contrato_id, competencia_id))
    assert 'value="irregular" selected' in pagina.text


def test_req26_relatorio_contem_identificacao_divergencias_checklist_e_conclusao():
    with TestClient(app) as client:
        contrato_id, competencia_id = _criar_contrato_com_competencia(client)
        csv_conteudo = (
            CSV_HEADER
            + "999.888.777-66;Sem Cadastro;Auxiliar;1000.00;1000.00;1000.00;1000.00;75.00;80.00;925.00\n"
        )
        client.post(
            f"/contratos/{contrato_id}/competencias/{competencia_id}/folha/importar",
            files={"arquivo": ("folha.csv", csv_conteudo.encode("utf-8"), "text/csv")},
        )

        pagina = client.get(_url_relatorio(contrato_id, competencia_id))
    assert "001/2026" in pagina.text
    assert "05/2026" in pagina.text
    assert "CNDT" in pagina.text
    assert "Sem Cadastro" in pagina.text or "fora da lista mestra" in pagina.text.lower()


def test_conclusao_invalida_e_bloqueada_com_422():
    with TestClient(app) as client:
        contrato_id, competencia_id = _criar_contrato_com_competencia(client)
        csv_conteudo = (
            CSV_HEADER
            + "111.222.333-44;Ana Souza;Auxiliar;1000.00;1000.00;1000.00;1000.00;75.00;80.00;925.00\n"
        )
        client.post(
            f"/contratos/{contrato_id}/competencias/{competencia_id}/folha/importar",
            files={"arquivo": ("folha.csv", csv_conteudo.encode("utf-8"), "text/csv")},
        )

        resposta = client.post(
            f"{_url_relatorio(contrato_id, competencia_id)}/conclusao",
            data={"conclusao": "nao-existe"},
        )
    assert resposta.status_code == 422


def test_relatorio_de_competencia_inexistente_retorna_404():
    with TestClient(app) as client:
        contrato_id, _ = _criar_contrato_com_competencia(client)
        resposta = client.get(_url_relatorio(contrato_id, 99999))
    assert resposta.status_code == 404
