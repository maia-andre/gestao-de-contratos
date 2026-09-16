from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Contrato
from app.models_fiscalizacao import Competencia, ItemFolha


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


def _url_importar(contrato_id, competencia_id):
    return f"/contratos/{contrato_id}/competencias/{competencia_id}/folha/importar"


def _url_folha(contrato_id, competencia_id):
    return f"/contratos/{contrato_id}/competencias/{competencia_id}/folha"


CSV_VALIDO = (
    "cpf;nome;cargo;salario_base;total_vencimentos;base_inss;base_fgts;inss_descontado;fgts_depositado;liquido\n"
    "123.456.789-01;Maria Silva;Auxiliar de Limpeza;1500.00;1500.00;1500.00;1500.00;112.50;120.00;1387.50\n"
)


def _upload(client, contrato_id, competencia_id, conteudo, confirmar=None, follow_redirects=True):
    data = {}
    if confirmar is not None:
        data["confirmar_substituicao"] = confirmar
    return client.post(
        _url_importar(contrato_id, competencia_id),
        data=data,
        files={"arquivo": ("folha.csv", conteudo.encode("utf-8"), "text/csv")},
        follow_redirects=follow_redirects,
    )


def test_importar_folha_valida_e_ver_valores_recalculados():
    with TestClient(app) as client:
        contrato_id, competencia_id = _criar_contrato_com_competencia(client)
        response = _upload(client, contrato_id, competencia_id, CSV_VALIDO, follow_redirects=False)
        assert response.status_code == 303
        folha = client.get(_url_folha(contrato_id, competencia_id))
    assert "Maria Silva" in folha.text
    # FGTS esperado = 8% de 1500,00 = 120,00 (bate com o informado, mas o recalculado deve aparecer)
    assert "120.00" in folha.text or "120,00" in folha.text


def test_ce08_reimportar_sem_confirmar_e_bloqueado():
    with TestClient(app) as client:
        contrato_id, competencia_id = _criar_contrato_com_competencia(client)
        _upload(client, contrato_id, competencia_id, CSV_VALIDO)

        outro_csv = CSV_VALIDO.replace("Maria Silva", "Outra Pessoa")
        response = _upload(client, contrato_id, competencia_id, outro_csv)
        assert response.status_code == 422

        folha = client.get(_url_folha(contrato_id, competencia_id))
    assert "Maria Silva" in folha.text
    assert "Outra Pessoa" not in folha.text


def test_ce08_reimportar_confirmando_substitui_a_folha():
    with TestClient(app) as client:
        contrato_id, competencia_id = _criar_contrato_com_competencia(client)
        _upload(client, contrato_id, competencia_id, CSV_VALIDO)

        outro_csv = CSV_VALIDO.replace("Maria Silva", "Outra Pessoa")
        response = _upload(
            client, contrato_id, competencia_id, outro_csv, confirmar="sim", follow_redirects=False
        )
        assert response.status_code == 303

        folha = client.get(_url_folha(contrato_id, competencia_id))
    assert "Outra Pessoa" in folha.text
    assert "Maria Silva" not in folha.text


def test_rn07_cpf_duplicado_no_csv_da_folha_so_a_primeira_linha_e_importada():
    csv_duplicado = (
        "cpf;nome;cargo;salario_base;total_vencimentos;base_inss;base_fgts;inss_descontado;fgts_depositado;liquido\n"
        "123.456.789-01;Maria Silva;Auxiliar;1500.00;1500.00;1500.00;1500.00;112.50;120.00;1387.50\n"
        "12345678901;Maria Silva Duplicada;Auxiliar;1500.00;1500.00;1500.00;1500.00;112.50;120.00;1387.50\n"
    )
    with TestClient(app) as client:
        contrato_id, competencia_id = _criar_contrato_com_competencia(client)
        response = _upload(client, contrato_id, competencia_id, csv_duplicado)
        folha = client.get(_url_folha(contrato_id, competencia_id))
    assert "CPF duplicado" in response.text
    assert "Maria Silva" in folha.text
    assert "Maria Silva Duplicada" not in folha.text


def test_linha_invalida_no_csv_da_folha_vira_erro_sem_travar_as_demais():
    csv_com_erro = (
        "cpf;nome;cargo;salario_base;total_vencimentos;base_inss;base_fgts;inss_descontado;fgts_depositado;liquido\n"
        "123.456.789-01;Maria Silva;Auxiliar;1500.00;1500.00;1500.00;1500.00;112.50;120.00;1387.50\n"
        "123;Nome Ruim;Cargo;abc;1500.00;1500.00;1500.00;112.50;120.00;1387.50\n"
    )
    with TestClient(app) as client:
        contrato_id, competencia_id = _criar_contrato_com_competencia(client)
        response = _upload(client, contrato_id, competencia_id, csv_com_erro)
        folha = client.get(_url_folha(contrato_id, competencia_id))
    assert "Linha 3" in response.text
    assert "Maria Silva" in folha.text
    assert "Nome Ruim" not in folha.text


def test_folha_de_competencia_inexistente_retorna_404():
    with TestClient(app) as client:
        contrato_id, _ = _criar_contrato_com_competencia(client)
        response = client.get(_url_folha(contrato_id, 99999))
    assert response.status_code == 404
