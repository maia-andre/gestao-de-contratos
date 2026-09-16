import json

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Contrato
from app.models_fiscalizacao import Competencia, ItemChecklistDocumental, PendenciaPreOS


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


def _montar_contrato_completo(client) -> tuple[int, int]:
    """Cria um contrato com pelo menos um registro em cada categoria da Fase 1."""
    client.post("/contratos", data=_dados_contrato())
    db = SessionLocal()
    try:
        contrato_id = db.query(Contrato).order_by(Contrato.id.desc()).first().id
    finally:
        db.close()

    client.post(
        f"/contratos/{contrato_id}/equipe",
        data={
            "nome": "Maria Silva",
            "matricula_cargo": "12345 - Engenheira",
            "lotacao": "Secretaria de Obras",
            "papeis": ["Fiscal Técnico"],
            "data_designacao": "2026-01-05",
            "substituto": "",
        },
    )

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

    client.post(
        f"/contratos/{contrato_id}/reunioes",
        data={"data": "2026-01-10", "participantes": "Maria Silva (Fiscal)", "resumo": "Reunião inicial."},
    )

    client.get(f"/contratos/{contrato_id}/pendencias-pre-os")
    db = SessionLocal()
    try:
        pendencia_id = db.query(PendenciaPreOS).filter_by(contrato_id=contrato_id).first().id
    finally:
        db.close()
    client.post(f"/contratos/{contrato_id}/pendencias-pre-os/{pendencia_id}/alternar")

    client.post(
        f"/contratos/{contrato_id}/ocorrencias",
        data={"data": "2026-05-10", "descricao": "Atraso leve", "gravidade": "leve"},
    )

    client.post(f"/contratos/{contrato_id}/competencias", data={"mes_ano": "2026-05"})
    db = SessionLocal()
    try:
        competencia_id = db.query(Competencia).filter_by(contrato_id=contrato_id).first().id
    finally:
        db.close()

    csv_conteudo = (
        "cpf;nome;cargo;salario_base;total_vencimentos;base_inss;base_fgts;"
        "inss_descontado;fgts_depositado;liquido\n"
        "111.222.333-44;Ana Souza;Auxiliar;1000.00;1000.00;1000.00;1000.00;75.00;80.00;925.00\n"
        "999.888.777-66;Fora Da Lista;Auxiliar;1000.00;1000.00;1000.00;1000.00;75.00;80.00;925.00\n"
    )
    client.post(
        f"/contratos/{contrato_id}/competencias/{competencia_id}/folha/importar",
        files={"arquivo": ("folha.csv", csv_conteudo.encode("utf-8"), "text/csv")},
    )

    client.post(
        f"/contratos/{contrato_id}/cpfs-conhecidos",
        data={
            "cpf": "99988877766",
            "nome": "Fora Da Lista",
            "motivo": "Funcionário de outro contrato.",
            "competencia_ano": "2026",
            "competencia_mes": "5",
        },
    )

    client.post(
        f"/contratos/{contrato_id}/competencias/{competencia_id}/recebimento-provisorio",
        data={"data": "2026-05-30", "decisao": "aceito", "observacao": ""},
    )

    client.get(f"/contratos/{contrato_id}/competencias/{competencia_id}/checklist")
    db = SessionLocal()
    try:
        item_cndt = (
            db.query(ItemChecklistDocumental)
            .filter_by(competencia_id=competencia_id, chave="cndt")
            .first()
        )
        item_cndt_id = item_cndt.id
    finally:
        db.close()
    client.post(f"/contratos/{contrato_id}/competencias/{competencia_id}/checklist/{item_cndt_id}/alternar")
    client.post(
        f"/contratos/{contrato_id}/competencias/{competencia_id}/checklist/{item_cndt_id}/data-referencia",
        data={"data_referencia": "2026-05-01"},
    )

    db = SessionLocal()
    try:
        from app.models import MembroEquipe

        fiscal_id = db.query(MembroEquipe).filter_by(contrato_id=contrato_id, nome="Maria Silva").first().id
    finally:
        db.close()
    client.post(
        f"/contratos/{contrato_id}/competencias/{competencia_id}/relatorio-tecnico",
        data={
            "avaliacao": "Cronograma dentro do previsto.",
            "conclusao": "regular",
            "fiscal_responsavel_id": str(fiscal_id),
            "data_ateste": "2026-06-01",
        },
    )

    client.post(
        f"/contratos/{contrato_id}/competencias/{competencia_id}/relatorio-administrativo/conclusao",
        data={"conclusao": "regular_com_ressalvas"},
    )

    return contrato_id, competencia_id


def test_req29_exportacao_inclui_todas_as_categorias_da_fase1():
    with TestClient(app) as client:
        contrato_id, competencia_id = _montar_contrato_completo(client)
        corpo = client.get("/exportar").json()

    contrato_exportado = next(c for c in corpo["contratos"] if c["numero"] == "001/2026")

    assert len(contrato_exportado["terceirizados"]) == 1
    assert contrato_exportado["terceirizados"][0]["cpf"] == "11122233344"

    assert len(contrato_exportado["reunioes"]) == 1
    assert contrato_exportado["reunioes"][0]["resumo"] == "Reunião inicial."

    assert len(contrato_exportado["pendencias_pre_os"]) == 2
    assert any(p["status"] == "ok" for p in contrato_exportado["pendencias_pre_os"])

    assert len(contrato_exportado["ocorrencias"]) == 1
    assert contrato_exportado["ocorrencias"][0]["gravidade"] == "leve"

    assert len(contrato_exportado["cpfs_conhecidos"]) == 1
    assert contrato_exportado["cpfs_conhecidos"][0]["cpf"] == "99988877766"

    assert len(contrato_exportado["competencias"]) == 1
    competencia_exportada = contrato_exportado["competencias"][0]
    assert competencia_exportada["ano"] == 2026
    assert competencia_exportada["mes"] == 5

    assert len(competencia_exportada["folha"]) == 2
    assert competencia_exportada["recebimento_provisorio"]["decisao"] == "aceito"
    assert len(competencia_exportada["checklist_documental"]) == 7
    cndt = next(i for i in competencia_exportada["checklist_documental"] if i["chave"] == "cndt")
    assert cndt["status"] == "ok"
    assert cndt["data_referencia"] == "2026-05-01"
    assert competencia_exportada["conclusao_administrativa"] == "regular_com_ressalvas"
    assert competencia_exportada["relatorio_tecnico"]["avaliacao"] == "Cronograma dentro do previsto."
    assert competencia_exportada["relatorio_tecnico"]["fiscal_responsavel_nome"] == "Maria Silva"


def test_req29_importar_restaura_todas_as_categorias_da_fase1():
    with TestClient(app) as client:
        contrato_id, competencia_id = _montar_contrato_completo(client)
        exportado = client.get("/exportar").json()

        conteudo = json.dumps(exportado).encode("utf-8")
        resposta = client.post(
            "/importar",
            files={"arquivo": ("contratos.json", conteudo, "application/json")},
            follow_redirects=False,
        )
        assert resposta.status_code == 303

        listagem = client.get("/contratos")
        assert listagem.text.count("001/2026") == 2

        db = SessionLocal()
        try:
            contrato_importado = (
                db.query(Contrato).filter_by(numero="001/2026").order_by(Contrato.id.desc()).first()
            )
            novo_contrato_id = contrato_importado.id
        finally:
            db.close()

        pagina_terceirizados = client.get(f"/contratos/{novo_contrato_id}/terceirizados")
        assert "Ana Souza" in pagina_terceirizados.text

        pagina_reunioes = client.get(f"/contratos/{novo_contrato_id}/reunioes")
        assert "Reunião inicial." in pagina_reunioes.text

        pagina_pendencias = client.get(f"/contratos/{novo_contrato_id}/pendencias-pre-os")
        assert "ok" in pagina_pendencias.text

        pagina_ocorrencias = client.get(f"/contratos/{novo_contrato_id}/ocorrencias")
        assert "Atraso leve" in pagina_ocorrencias.text

        pagina_conhecidos = client.get(f"/contratos/{novo_contrato_id}/cpfs-conhecidos")
        assert "99988877766" in pagina_conhecidos.text

        db = SessionLocal()
        try:
            nova_competencia = db.query(Competencia).filter_by(contrato_id=novo_contrato_id).first()
            nova_competencia_id = nova_competencia.id
        finally:
            db.close()

        pagina_folha = client.get(f"/contratos/{novo_contrato_id}/competencias/{nova_competencia_id}/folha")
        assert "Ana Souza" in pagina_folha.text

        pagina_recebimento = client.get(
            f"/contratos/{novo_contrato_id}/competencias/{nova_competencia_id}/recebimento-provisorio"
        )
        assert "Status atual: <strong>Aceito</strong>" in pagina_recebimento.text

        pagina_checklist = client.get(
            f"/contratos/{novo_contrato_id}/competencias/{nova_competencia_id}/checklist"
        )
        assert "2026-05-01" in pagina_checklist.text

        pagina_relatorio_tecnico = client.get(
            f"/contratos/{novo_contrato_id}/competencias/{nova_competencia_id}/relatorio-tecnico"
        )
        assert "Cronograma dentro do previsto." in pagina_relatorio_tecnico.text
        assert "Maria Silva" in pagina_relatorio_tecnico.text

        pagina_relatorio_administrativo = client.get(
            f"/contratos/{novo_contrato_id}/competencias/{nova_competencia_id}/relatorio-administrativo"
        )
    assert 'value="regular_com_ressalvas" selected' in pagina_relatorio_administrativo.text


def test_ce15_importar_relatorio_tecnico_com_fiscal_inexistente_e_rejeitado_sem_apagar_dados():
    with TestClient(app) as client:
        client.post("/contratos", data=_dados_contrato(numero="EXISTENTE"))

        payload = {
            "contratos": [
                {
                    "numero": "CORROMPIDO",
                    "objeto": "Objeto",
                    "contratada_razao_social": "Empresa",
                    "contratada_cnpj": "00.000.000/0001-00",
                    "vigencia_inicio": "2026-01-01",
                    "vigencia_fim": "2026-12-31",
                    "mao_de_obra_exclusiva": True,
                    "valor_global": "100.00",
                    "modalidade": "Pregão",
                    "equipe": [],
                    "terceirizados": [],
                    "reunioes": [],
                    "pendencias_pre_os": [],
                    "ocorrencias": [],
                    "cpfs_conhecidos": [],
                    "competencias": [
                        {
                            "ano": 2026,
                            "mes": 5,
                            "relatorio_tecnico": {
                                "avaliacao": "Texto",
                                "conclusao": "regular",
                                "fiscal_responsavel_nome": "Fiscal Que Não Existe",
                                "data_ateste": "2026-06-01",
                            },
                            "recebimento_provisorio": None,
                            "folha": [],
                            "checklist_documental": [],
                            "conclusao_administrativa": None,
                        }
                    ],
                }
            ]
        }
        conteudo = json.dumps(payload).encode("utf-8")
        resposta = client.post("/importar", files={"arquivo": ("c.json", conteudo, "application/json")})
        assert resposta.status_code == 422

        listagem = client.get("/contratos")
    assert "EXISTENTE" in listagem.text
    assert "CORROMPIDO" not in listagem.text


def test_ce15_importar_competencias_duplicadas_no_mesmo_contrato_e_rejeitado_sem_apagar_dados():
    with TestClient(app) as client:
        client.post("/contratos", data=_dados_contrato(numero="EXISTENTE"))

        competencia_base = {
            "ano": 2026,
            "mes": 5,
            "relatorio_tecnico": None,
            "recebimento_provisorio": None,
            "folha": [],
            "checklist_documental": [],
            "conclusao_administrativa": None,
        }
        payload = {
            "contratos": [
                {
                    "numero": "CORROMPIDO",
                    "objeto": "Objeto",
                    "contratada_razao_social": "Empresa",
                    "contratada_cnpj": "00.000.000/0001-00",
                    "vigencia_inicio": "2026-01-01",
                    "vigencia_fim": "2026-12-31",
                    "mao_de_obra_exclusiva": True,
                    "valor_global": "100.00",
                    "modalidade": "Pregão",
                    "equipe": [],
                    "terceirizados": [],
                    "reunioes": [],
                    "pendencias_pre_os": [],
                    "ocorrencias": [],
                    "cpfs_conhecidos": [],
                    "competencias": [dict(competencia_base), dict(competencia_base)],
                }
            ]
        }
        conteudo = json.dumps(payload).encode("utf-8")
        resposta = client.post("/importar", files={"arquivo": ("c.json", conteudo, "application/json")})
        assert resposta.status_code == 422

        listagem = client.get("/contratos")
    assert "EXISTENTE" in listagem.text
    assert "CORROMPIDO" not in listagem.text


def test_ce15_importar_cpfs_conhecidos_com_cpf_duplicado_no_mesmo_contrato_e_rejeitado_sem_apagar_dados():
    with TestClient(app) as client:
        client.post("/contratos", data=_dados_contrato(numero="EXISTENTE"))

        payload = {
            "contratos": [
                {
                    "numero": "CORROMPIDO",
                    "objeto": "Objeto",
                    "contratada_razao_social": "Empresa",
                    "contratada_cnpj": "00.000.000/0001-00",
                    "vigencia_inicio": "2026-01-01",
                    "vigencia_fim": "2026-12-31",
                    "mao_de_obra_exclusiva": True,
                    "valor_global": "100.00",
                    "modalidade": "Pregão",
                    "equipe": [],
                    "terceirizados": [],
                    "reunioes": [],
                    "pendencias_pre_os": [],
                    "ocorrencias": [],
                    "cpfs_conhecidos": [
                        {
                            "cpf": "11122233344",
                            "nome": "Pessoa A",
                            "motivo": "motivo 1",
                            "competencia_referencia_ano": 2026,
                            "competencia_referencia_mes": 5,
                        },
                        {
                            "cpf": "11122233344",
                            "nome": "Pessoa A Duplicada",
                            "motivo": "motivo 2",
                            "competencia_referencia_ano": 2026,
                            "competencia_referencia_mes": 6,
                        },
                    ],
                    "competencias": [],
                }
            ]
        }
        conteudo = json.dumps(payload).encode("utf-8")
        resposta = client.post("/importar", files={"arquivo": ("c.json", conteudo, "application/json")})
        assert resposta.status_code == 422

        listagem = client.get("/contratos")
    assert "EXISTENTE" in listagem.text
    assert "CORROMPIDO" not in listagem.text
