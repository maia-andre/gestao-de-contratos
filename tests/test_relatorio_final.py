from datetime import date

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Contrato, MembroEquipe
from app.models_fiscalizacao import (
    Competencia,
    ConclusaoAdministrativa,
    Ocorrencia,
    RecebimentoProvisorio,
    RelatorioTecnico,
    Reuniao,
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


def _criar_contrato(client, **overrides) -> int:
    client.post("/contratos", data=_dados_contrato(**overrides))
    db = SessionLocal()
    try:
        return db.query(Contrato).order_by(Contrato.id.desc()).first().id
    finally:
        db.close()


def _criar_membro(client, contrato_id: int, nome: str, papeis: list[str]) -> int:
    client.post(
        f"/contratos/{contrato_id}/equipe",
        data={
            "nome": nome,
            "matricula_cargo": f"999 — {nome}",
            "lotacao": "Secretaria de Administração",
            "papeis": papeis,
            "data_designacao": "2026-01-05",
            "substituto": "",
        },
    )
    db = SessionLocal()
    try:
        return (
            db.query(MembroEquipe).filter_by(contrato_id=contrato_id, nome=nome).first().id
        )
    finally:
        db.close()


def _registrar_parecer(client, contrato_id: int, **overrides):
    dados = {
        "conceito": "parcialmente",
        "justificativa": "Metas de limpeza atendidas com atrasos pontuais.",
        "licoes": "Exigir plano de férias da contratada no edital.",
    }
    dados.update(overrides)
    return client.post(f"/contratos/{contrato_id}/relatorio-final", data=dados)


def _popular_execucao(contrato_id: int, gestor_id: int) -> None:
    """Reuniões, competências, conclusões, ocorrências e recebimento direto no banco."""
    db = SessionLocal()
    try:
        db.add(Reuniao(contrato_id=contrato_id, data=date(2026, 2, 5), participantes="A", resumo="R1"))
        db.add(Reuniao(contrato_id=contrato_id, data=date(2026, 3, 5), participantes="A", resumo="R2"))
        comp = Competencia(contrato_id=contrato_id, ano=2026, mes=2)
        db.add(comp)
        db.flush()
        db.add(RelatorioTecnico(
            competencia_id=comp.id, avaliacao="ok", conclusao="regular",
            fiscal_responsavel_id=gestor_id, data_ateste=date(2026, 3, 1)))
        db.add(ConclusaoAdministrativa(competencia_id=comp.id, conclusao="regular com ressalvas"))
        db.add(RecebimentoProvisorio(
            competencia_id=comp.id, data=date(2026, 3, 2), decisao="aceito", observacao=None))
        db.add(Ocorrencia(contrato_id=contrato_id, data=date(2026, 2, 10), descricao="Falta", gravidade="leve"))
        db.add(Ocorrencia(contrato_id=contrato_id, data=date(2026, 2, 12), descricao="Dano", gravidade="grave"))
        db.commit()
    finally:
        db.close()


# REQ-10 — registrar e editar o parecer (persistido)


def test_registrar_parecer_e_ver_persistido():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = _registrar_parecer(client, contrato_id)
        assert response.status_code == 303 or response.history
        form = client.get(f"/contratos/{contrato_id}/relatorio-final")
    assert "Metas de limpeza atendidas com atrasos pontuais." in form.text
    assert "Exigir plano de férias da contratada no edital." in form.text
    assert 'value="parcialmente" selected' in form.text


def test_editar_parecer_substitui_valores():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _registrar_parecer(client, contrato_id)
        _registrar_parecer(
            client, contrato_id, conceito="alcancados", justificativa="Tudo entregue."
        )
        form = client.get(f"/contratos/{contrato_id}/relatorio-final")
    assert "Tudo entregue." in form.text
    assert 'value="alcancados" selected' in form.text
    assert "Metas de limpeza atendidas com atrasos pontuais." not in form.text


def test_parecer_sem_justificativa_rejeitado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = _registrar_parecer(client, contrato_id, justificativa="")
    assert response.status_code == 422
    assert "Justificativa do parecer é obrigatória." in response.text


def test_parecer_com_conceito_invalido_rejeitado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = _registrar_parecer(client, contrato_id, conceito="otimo")
    assert response.status_code == 422
    assert "Conceito do parecer inválido." in response.text


def test_licoes_vazias_aceitas():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = _registrar_parecer(client, contrato_id, licoes="")
        assert response.status_code == 303 or response.history


# CE-09 — documento exige parecer registrado


def test_documento_sem_parecer_bloqueado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _criar_membro(client, contrato_id, "Bruno Gestor", ["Gestor de Contratos"])
        response = client.get(f"/contratos/{contrato_id}/relatorio-final/documento")
    assert response.status_code == 422
    assert "registre o parecer" in response.text


# CE-03 (re-verificação) — equipe e emissor


def test_documento_sem_equipe_bloqueado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _registrar_parecer(client, contrato_id)
        response = client.get(f"/contratos/{contrato_id}/relatorio-final/documento")
    assert response.status_code == 422
    assert "não tem equipe cadastrada" in response.text


def test_selecao_de_emissor_preseleciona_gestor():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        _criar_membro(client, contrato_id, "Ana Fiscal", ["Fiscal Técnico"])
        gestor_id = _criar_membro(client, contrato_id, "Bruno Gestor", ["Gestor de Contratos"])
        _registrar_parecer(client, contrato_id)
        response = client.get(f"/contratos/{contrato_id}/relatorio-final/documento")
    assert response.status_code == 200
    assert f'<option value="{gestor_id}" selected>' in response.text


def test_emissor_forjado_rejeitado():
    with TestClient(app) as client:
        contrato_a = _criar_contrato(client)
        contrato_b = _criar_contrato(client, numero="002/2026")
        membro_b = _criar_membro(client, contrato_b, "Eva Externa", ["Fiscal Técnico"])
        _criar_membro(client, contrato_a, "Ana Fiscal", ["Fiscal Técnico"])
        _registrar_parecer(client, contrato_a)
        response = client.get(
            f"/contratos/{contrato_a}/relatorio-final/documento",
            params={"emissor_id": membro_b},
        )
    assert response.status_code == 404


# REQ-11 — conteúdo do documento


def test_documento_completo():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        gestor_id = _criar_membro(client, contrato_id, "Bruno Gestor", ["Gestor de Contratos"])
        _popular_execucao(contrato_id, gestor_id)
        # prorrogação para compor vigência original + histórico
        client.post(f"/contratos/{contrato_id}/prorrogacao/envio", data={"data_envio": "2026-08-04"})
        client.post(
            f"/contratos/{contrato_id}/prorrogacao/resposta",
            data={"data_resposta": "2026-08-06", "teor": "com_interesse"},
        )
        client.post(
            f"/contratos/{contrato_id}/prorrogacao/aditivo",
            data={"nova_vigencia_fim": "2027-12-31"},
        )
        _registrar_parecer(client, contrato_id)
        response = client.get(
            f"/contratos/{contrato_id}/relatorio-final/documento",
            params={"emissor_id": gestor_id},
        )
    assert response.status_code == 200
    texto = response.text
    assert "Relatório Final de Consecução de Objetivos" in texto
    # identificação
    assert "001/2026" in texto and "Limpa Tudo Serviços Ltda" in texto
    assert "150000.00" in texto and "Pregão eletrônico" in texto
    # vigência original, prorrogação e vigência final
    assert "01/01/2026" in texto and "31/12/2026" in texto and "31/12/2027" in texto
    # equipe
    assert "Bruno Gestor" in texto
    # resumo da execução
    assert "Reuniões registradas" in texto and ">2<" in texto
    assert "02/2026" in texto and "regular com ressalvas" in texto
    assert "leve" in texto and "grave" in texto
    assert "aceito" in texto
    # parecer e lições
    assert "Objetivos parcialmente alcançados" in texto
    assert "Metas de limpeza atendidas com atrasos pontuais." in texto
    assert "Exigir plano de férias da contratada no edital." in texto
    assert "documento__assinatura" in texto


def test_documento_reflete_edicao_do_parecer():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        gestor_id = _criar_membro(client, contrato_id, "Bruno Gestor", ["Gestor de Contratos"])
        _registrar_parecer(client, contrato_id)
        _registrar_parecer(
            client, contrato_id, conceito="nao_alcancados", justificativa="Contrato rescindido."
        )
        response = client.get(
            f"/contratos/{contrato_id}/relatorio-final/documento",
            params={"emissor_id": gestor_id},
        )
    assert "Objetivos não alcançados" in response.text
    assert "Contrato rescindido." in response.text


# REQ-12 — ponto de acesso na tela do contrato


def test_tela_do_contrato_tem_link_para_relatorio_final():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        response = client.get(f"/contratos/{contrato_id}")
    assert f"/contratos/{contrato_id}/relatorio-final" in response.text
