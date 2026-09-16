from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Contrato, MembroEquipe
from app.models_fiscalizacao import Reuniao


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


def _criar_membro(client, contrato_id: int, **overrides) -> int:
    client.post(f"/contratos/{contrato_id}/equipe", data=_dados_membro(**overrides))
    db = SessionLocal()
    try:
        return db.query(MembroEquipe).order_by(MembroEquipe.id.desc()).first().id
    finally:
        db.close()


def _dados_reuniao(**overrides):
    dados = {
        "data": "2026-02-05",
        "hora": "14:30",
        "local": "Sala de reuniões da Secretaria",
        "participantes": "João Silva — Fiscal Técnico\nMaria Oliveira — Preposta",
        "resumo": "Pauta: alinhamento inicial do escopo.",
    }
    dados.update(overrides)
    return dados


def _criar_reuniao(client, contrato_id: int, **overrides) -> int:
    client.post(f"/contratos/{contrato_id}/reunioes", data=_dados_reuniao(**overrides))
    db = SessionLocal()
    try:
        return db.query(Reuniao).order_by(Reuniao.id.desc()).first().id
    finally:
        db.close()


def test_convocacao_pede_selecao_de_emissor():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _criar_membro(client, contrato_id)
        reuniao_id = _criar_reuniao(client, contrato_id)
        response = client.get(f"/contratos/{contrato_id}/reunioes/{reuniao_id}/convocacao")
    assert response.status_code == 200
    assert "Emissor da convocação" in response.text
    assert "Maria Silva" in response.text


def test_gerar_convocacao_com_emissor():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        membro_id = _criar_membro(client, contrato_id)
        reuniao_id = _criar_reuniao(client, contrato_id)
        response = client.get(
            f"/contratos/{contrato_id}/reunioes/{reuniao_id}/convocacao",
            params={"emissor_id": membro_id},
        )
    assert response.status_code == 200
    assert "Convocação de Reunião" in response.text
    assert "001/2026" in response.text
    assert "Limpa Tudo Serviços Ltda" in response.text
    assert "05/02/2026" in response.text
    assert "14:30" in response.text
    assert "Sala de reuniões da Secretaria" in response.text
    assert "Pauta: alinhamento inicial do escopo." in response.text
    assert "Maria Silva" in response.text
    assert "12345 — Engenheira" in response.text
    assert "linha-assinatura" in response.text


def test_convocacao_sem_hora_ou_local_e_bloqueada():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _criar_membro(client, contrato_id)
        reuniao_id = _criar_reuniao(client, contrato_id, hora="", local="")
        response = client.get(f"/contratos/{contrato_id}/reunioes/{reuniao_id}/convocacao")
    assert response.status_code == 422
    assert "Não é possível gerar a convocação" in response.text
    assert "hora" in response.text
    assert "local" in response.text


def test_convocacao_so_sem_local_e_bloqueada():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _criar_membro(client, contrato_id)
        reuniao_id = _criar_reuniao(client, contrato_id, local="")
        response = client.get(f"/contratos/{contrato_id}/reunioes/{reuniao_id}/convocacao")
    assert response.status_code == 422
    assert "local" in response.text


def test_emissor_fora_da_equipe_do_contrato_e_rejeitado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _criar_membro(client, contrato_id)
        outro_contrato_id = _criar_contrato(client, numero="002/2026")
        membro_de_fora_id = _criar_membro(client, outro_contrato_id, nome="Pedro Souza")
        reuniao_id = _criar_reuniao(client, contrato_id)
        response = client.get(
            f"/contratos/{contrato_id}/reunioes/{reuniao_id}/convocacao",
            params={"emissor_id": membro_de_fora_id},
        )
    assert response.status_code == 404


def test_convocacao_reflete_edicao_da_reuniao():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        membro_id = _criar_membro(client, contrato_id)
        reuniao_id = _criar_reuniao(client, contrato_id)
        client.post(
            f"/contratos/{contrato_id}/reunioes/{reuniao_id}/editar",
            data=_dados_reuniao(local="Auditório Central", resumo="Pauta revisada."),
        )
        response = client.get(
            f"/contratos/{contrato_id}/reunioes/{reuniao_id}/convocacao",
            params={"emissor_id": membro_id},
        )
    assert "Auditório Central" in response.text
    assert "Pauta revisada." in response.text
    assert "Sala de reuniões da Secretaria" not in response.text


def test_listagem_de_reunioes_tem_link_de_convocacao():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        reuniao_id = _criar_reuniao(client, contrato_id)
        listagem = client.get(f"/contratos/{contrato_id}/reunioes")
    assert f"/contratos/{contrato_id}/reunioes/{reuniao_id}/convocacao" in listagem.text


def test_gerar_ata_com_um_participante_por_linha():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        reuniao_id = _criar_reuniao(
            client,
            contrato_id,
            participantes="João Silva — Fiscal Técnico\nMaria Oliveira — Preposta\nAna Costa — Gestora",
            resumo="Deliberado o cronograma de implantação.",
        )
        response = client.get(f"/contratos/{contrato_id}/reunioes/{reuniao_id}/ata")
    assert response.status_code == 200
    assert "Ata de Reunião" in response.text
    assert "Deliberado o cronograma de implantação." in response.text
    assert response.text.count("linha-assinatura") == 3
    assert "João Silva — Fiscal Técnico" in response.text
    assert "Maria Oliveira — Preposta" in response.text
    assert "Ana Costa — Gestora" in response.text


def test_ata_ignora_linhas_vazias_de_participantes():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        reuniao_id = _criar_reuniao(
            client, contrato_id, participantes="João Silva\n\n   \nMaria Oliveira"
        )
        response = client.get(f"/contratos/{contrato_id}/reunioes/{reuniao_id}/ata")
    assert response.text.count("linha-assinatura") == 2


def test_ata_sem_hora_e_local_e_gerada_normalmente():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        reuniao_id = _criar_reuniao(client, contrato_id, hora="", local="")
        response = client.get(f"/contratos/{contrato_id}/reunioes/{reuniao_id}/ata")
    assert response.status_code == 200
    assert "Ata de Reunião" in response.text
    assert "05/02/2026" in response.text
    assert ", às" not in response.text
    assert "Local:" not in response.text


def test_ata_com_hora_e_local_os_exibe():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        reuniao_id = _criar_reuniao(client, contrato_id)
        response = client.get(f"/contratos/{contrato_id}/reunioes/{reuniao_id}/ata")
    assert ", às 14:30" in response.text
    assert "Sala de reuniões da Secretaria" in response.text


def test_ata_de_reuniao_inexistente_retorna_404():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.get(f"/contratos/{contrato_id}/reunioes/99999/ata")
    assert response.status_code == 404


def test_listagem_de_reunioes_tem_link_de_ata():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        reuniao_id = _criar_reuniao(client, contrato_id)
        listagem = client.get(f"/contratos/{contrato_id}/reunioes")
    assert f"/contratos/{contrato_id}/reunioes/{reuniao_id}/ata" in listagem.text


def test_termo_designacao_pede_autoridade():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _criar_membro(client, contrato_id)
        response = client.get(f"/contratos/{contrato_id}/termo-designacao")
    assert response.status_code == 200
    assert "autoridade signatária" in response.text


def test_gerar_termo_designacao_com_equipe_completa():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _criar_membro(client, contrato_id)
        _criar_membro(
            client,
            contrato_id,
            nome="Carlos Pereira",
            matricula_cargo="67890 — Administrador",
            lotacao="Secretaria de Gestão",
            papeis=["Fiscal Administrativo"],
            substituto="Ana Costa",
        )
        response = client.get(
            f"/contratos/{contrato_id}/termo-designacao",
            params={"autoridade_nome": "José Santos", "autoridade_cargo": "Secretário de Gestão"},
        )
    assert response.status_code == 200
    assert "Termo de Designação" in response.text
    assert "001/2026" in response.text
    assert "Maria Silva" in response.text
    assert "12345 — Engenheira" in response.text
    assert "Secretaria de Obras" in response.text
    assert "Fiscal Técnico" in response.text
    assert "05/01/2026" in response.text
    assert "Carlos Pereira" in response.text
    assert "Fiscal Administrativo" in response.text
    assert "Ana Costa" in response.text
    assert "José Santos" in response.text
    assert "Secretário de Gestão" in response.text
    assert "linha-assinatura" in response.text


def test_termo_designacao_sem_autoridade_preenchida_e_bloqueado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _criar_membro(client, contrato_id)
        response = client.get(
            f"/contratos/{contrato_id}/termo-designacao",
            params={"autoridade_nome": "", "autoridade_cargo": "Secretário"},
        )
    assert response.status_code == 422
    assert "Nome da autoridade signatária é obrigatório." in response.text


def test_termo_designacao_sem_cargo_da_autoridade_e_bloqueado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _criar_membro(client, contrato_id)
        response = client.get(
            f"/contratos/{contrato_id}/termo-designacao",
            params={"autoridade_nome": "José Santos", "autoridade_cargo": ""},
        )
    assert response.status_code == 422
    assert "Cargo da autoridade signatária é obrigatório." in response.text


def test_termo_designacao_sem_equipe_e_bloqueado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.get(f"/contratos/{contrato_id}/termo-designacao")
    assert response.status_code == 422
    assert "não tem equipe cadastrada" in response.text


def test_termo_designacao_reflete_equipe_atual():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _criar_membro(client, contrato_id)
        _criar_membro(client, contrato_id, nome="Novo Membro", papeis=["Gestor de Contratos"])
        response = client.get(
            f"/contratos/{contrato_id}/termo-designacao",
            params={"autoridade_nome": "José Santos", "autoridade_cargo": "Secretário"},
        )
    assert "Novo Membro" in response.text
    assert "Gestor de Contratos" in response.text


def test_detalhe_do_contrato_tem_link_do_termo_designacao():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        detalhe = client.get(f"/contratos/{contrato_id}")
    assert f"/contratos/{contrato_id}/termo-designacao" in detalhe.text
