from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Contrato
from app.models_fiscalizacao import Competencia


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


def _url_folha(contrato_id, competencia_id):
    return f"/contratos/{contrato_id}/competencias/{competencia_id}/folha"


def test_sem_divergencias_quando_folha_e_lista_mestra_batem():
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
            "cpf;nome;cargo;salario_base;total_vencimentos;base_inss;base_fgts;inss_descontado;fgts_depositado;liquido\n"
            "111.222.333-44;Ana Souza;Auxiliar;1000.00;1000.00;1000.00;1000.00;75.00;80.00;925.00\n"
        )
        client.post(
            f"{_url_folha(contrato_id, competencia_id)}/importar",
            files={"arquivo": ("folha.csv", csv_conteudo.encode("utf-8"), "text/csv")},
        )
        pagina = client.get(_url_folha(contrato_id, competencia_id))
    assert "Nenhuma divergência encontrada." in pagina.text


def test_req17_divergencia_de_ausencia_aparece_na_tela_da_folha():
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
        # nenhuma folha importada -> Ana Souza está ativa e ausente
        pagina = client.get(_url_folha(contrato_id, competencia_id))
    assert "ausencia" in pagina.text
    assert "Ana Souza" in pagina.text
    assert "não aparece na folha desta competência" in pagina.text


def test_req18_divergencia_fora_da_lista_mestra_aparece_na_tela_da_folha():
    with TestClient(app) as client:
        contrato_id, competencia_id = _criar_contrato_com_competencia(client)
        csv_conteudo = (
            "cpf;nome;cargo;salario_base;total_vencimentos;base_inss;base_fgts;inss_descontado;fgts_depositado;liquido\n"
            "999.888.777-66;Sem Cadastro;Auxiliar;1000.00;1000.00;1000.00;1000.00;75.00;80.00;925.00\n"
        )
        client.post(
            f"{_url_folha(contrato_id, competencia_id)}/importar",
            files={"arquivo": ("folha.csv", csv_conteudo.encode("utf-8"), "text/csv")},
        )
        pagina = client.get(_url_folha(contrato_id, competencia_id))
    # desde o INC-09, "fora da lista mestra" tem seu próprio bloco recolhido (REQ-20),
    # não aparece mais como um "Tipo" genérico na tabela — checa o bloco e o nome.
    assert "CPFs fora da lista mestra" in pagina.text
    assert "Sem Cadastro" in pagina.text
    assert "Sem Cadastro" in pagina.text
