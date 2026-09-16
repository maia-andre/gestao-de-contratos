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


def _criar_contrato(client) -> int:
    client.post("/contratos", data=_dados_contrato())
    db = SessionLocal()
    try:
        return db.query(Contrato).order_by(Contrato.id.desc()).first().id
    finally:
        db.close()


def _criar_competencia(client, contrato_id, mes_ano) -> int:
    client.post(f"/contratos/{contrato_id}/competencias", data={"mes_ano": mes_ano})
    db = SessionLocal()
    try:
        ano, mes = (int(p) for p in mes_ano.split("-"))
        return db.query(Competencia).filter_by(contrato_id=contrato_id, ano=ano, mes=mes).first().id
    finally:
        db.close()


def _importar_cpf_fora_da_lista(client, contrato_id, competencia_id, cpf="222.333.444-55", nome="Fora Da Lista"):
    csv_conteudo = (
        "cpf;nome;cargo;salario_base;total_vencimentos;base_inss;base_fgts;inss_descontado;fgts_depositado;liquido\n"
        f"{cpf};{nome};Auxiliar;1000.00;1000.00;1000.00;1000.00;75.00;80.00;925.00\n"
    )
    return client.post(
        f"/contratos/{contrato_id}/competencias/{competencia_id}/folha/importar",
        files={"arquivo": ("folha.csv", csv_conteudo.encode("utf-8"), "text/csv")},
    )


def _url_folha(contrato_id, competencia_id):
    return f"/contratos/{contrato_id}/competencias/{competencia_id}/folha"


def _url_conhecidos(contrato_id):
    return f"/contratos/{contrato_id}/cpfs-conhecidos"


def test_req20_divergencias_fora_da_lista_aparecem_em_bloco_recolhido_com_contador():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        competencia_id = _criar_competencia(client, contrato_id, "2026-05")
        _importar_cpf_fora_da_lista(client, contrato_id, competencia_id)
        pagina = client.get(_url_folha(contrato_id, competencia_id))
    assert "<details" in pagina.text
    assert "1" in pagina.text
    assert "Fora Da Lista" in pagina.text


def test_ce09_sem_cpf_fora_da_lista_bloco_nao_aparece():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        competencia_id = _criar_competencia(client, contrato_id, "2026-05")
        pagina = client.get(_url_folha(contrato_id, competencia_id))
    assert "<details" not in pagina.text


def test_req21_marcar_cpf_como_conhecido_com_motivo():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        competencia_id = _criar_competencia(client, contrato_id, "2026-05")
        _importar_cpf_fora_da_lista(client, contrato_id, competencia_id)

        response = client.post(
            _url_conhecidos(contrato_id),
            data={
                "cpf": "22233344455",
                "nome": "Fora Da Lista",
                "motivo": "Funcionário de outro contrato da mesma empresa.",
                "competencia_ano": "2026",
                "competencia_mes": "5",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

        pagina = client.get(_url_folha(contrato_id, competencia_id))
    # o nome continua na tabela da folha (foi importado); o que deve sumir é a divergência.
    assert "Nenhuma divergência encontrada." in pagina.text
    assert "<details" not in pagina.text


def test_ce10_marcar_sem_motivo_e_bloqueado():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        competencia_id = _criar_competencia(client, contrato_id, "2026-05")
        _importar_cpf_fora_da_lista(client, contrato_id, competencia_id)

        response = client.post(
            _url_conhecidos(contrato_id),
            data={
                "cpf": "22233344455",
                "nome": "Fora Da Lista",
                "motivo": "",
                "competencia_ano": "2026",
                "competencia_mes": "5",
            },
        )
    assert response.status_code == 422
    assert "obrigat" in response.text.lower()


def test_rn09_marcacao_nao_suprime_competencia_anterior_a_referencia():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        competencia_abril = _criar_competencia(client, contrato_id, "2026-04")
        competencia_maio = _criar_competencia(client, contrato_id, "2026-05")
        _importar_cpf_fora_da_lista(client, contrato_id, competencia_abril)
        _importar_cpf_fora_da_lista(client, contrato_id, competencia_maio)

        client.post(
            _url_conhecidos(contrato_id),
            data={
                "cpf": "22233344455",
                "nome": "Fora Da Lista",
                "motivo": "Funcionário de outro contrato.",
                "competencia_ano": "2026",
                "competencia_mes": "5",
            },
        )

        pagina_abril = client.get(_url_folha(contrato_id, competencia_abril))
        pagina_maio = client.get(_url_folha(contrato_id, competencia_maio))
    # abril é anterior à competência de referência (maio): divergência continua aparecendo.
    assert "<details" in pagina_abril.text
    # maio é a própria competência de referência: divergência suprimida.
    assert "<details" not in pagina_maio.text
    assert "Nenhuma divergência encontrada." in pagina_maio.text


def test_req22_tela_de_cpfs_conhecidos_lista_marcacoes():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        competencia_id = _criar_competencia(client, contrato_id, "2026-05")
        _importar_cpf_fora_da_lista(client, contrato_id, competencia_id)
        client.post(
            _url_conhecidos(contrato_id),
            data={
                "cpf": "22233344455",
                "nome": "Fora Da Lista",
                "motivo": "Funcionário de outro contrato.",
                "competencia_ano": "2026",
                "competencia_mes": "5",
            },
        )
        pagina = client.get(_url_conhecidos(contrato_id))
    assert "22233344455" in pagina.text
    assert "Fora Da Lista" in pagina.text
    assert "Funcionário de outro contrato." in pagina.text
    assert "05/2026" in pagina.text


def test_ce12_desmarcar_cpf_conhecido_volta_a_contar_em_todas_as_competencias():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        competencia_abril = _criar_competencia(client, contrato_id, "2026-04")
        competencia_maio = _criar_competencia(client, contrato_id, "2026-05")
        _importar_cpf_fora_da_lista(client, contrato_id, competencia_abril)
        _importar_cpf_fora_da_lista(client, contrato_id, competencia_maio)

        client.post(
            _url_conhecidos(contrato_id),
            data={
                "cpf": "22233344455",
                "nome": "Fora Da Lista",
                "motivo": "Funcionário de outro contrato.",
                "competencia_ano": "2026",
                "competencia_mes": "5",
            },
        )

        from app.models_fiscalizacao import CpfConhecido

        db = SessionLocal()
        try:
            conhecido_id = db.query(CpfConhecido).filter_by(contrato_id=contrato_id).first().id
        finally:
            db.close()

        response = client.post(
            f"{_url_conhecidos(contrato_id)}/{conhecido_id}/remover", follow_redirects=False
        )
        assert response.status_code == 303

        pagina_abril = client.get(_url_folha(contrato_id, competencia_abril))
        pagina_maio = client.get(_url_folha(contrato_id, competencia_maio))
    # divergência volta a aparecer em ambas as competências, passada e futura em relação à
    # antiga referência (não só o nome incidental na tabela da folha).
    assert "<details" in pagina_abril.text
    assert "<details" in pagina_maio.text


def test_ce11_cpf_conhecido_que_passa_a_constar_na_lista_mestra_nao_conta_mais_como_fora_da_lista():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        competencia_id = _criar_competencia(client, contrato_id, "2026-05")
        _importar_cpf_fora_da_lista(client, contrato_id, competencia_id)

        # cadastra o mesmo CPF na lista mestra, sem marcar como conhecido
        client.post(
            f"/contratos/{contrato_id}/terceirizados",
            data={
                "cpf": "222.333.444-55",
                "nome": "Fora Da Lista",
                "cargo": "Auxiliar",
                "salario_base": "1000.00",
                "data_admissao": "2026-05-01",
                "data_desligamento": "",
            },
        )

        pagina = client.get(_url_folha(contrato_id, competencia_id))
    assert "<details" not in pagina.text


def test_cpfs_conhecidos_de_contrato_inexistente_retorna_404():
    with TestClient(app) as client:
        response = client.get(_url_conhecidos(99999))
    assert response.status_code == 404


def test_marcar_com_competencia_ano_vazia_e_bloqueado_com_422():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        competencia_id = _criar_competencia(client, contrato_id, "2026-05")
        _importar_cpf_fora_da_lista(client, contrato_id, competencia_id)

        response = client.post(
            _url_conhecidos(contrato_id),
            data={
                "cpf": "22233344455",
                "nome": "Fora Da Lista",
                "motivo": "Motivo válido.",
                "competencia_ano": "",
                "competencia_mes": "5",
            },
        )
    assert response.status_code == 422
    assert "competência" in response.text.lower()


def test_marcar_com_competencia_mes_nao_numerica_e_bloqueado_com_422():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        competencia_id = _criar_competencia(client, contrato_id, "2026-05")
        _importar_cpf_fora_da_lista(client, contrato_id, competencia_id)

        response = client.post(
            _url_conhecidos(contrato_id),
            data={
                "cpf": "22233344455",
                "nome": "Fora Da Lista",
                "motivo": "Motivo válido.",
                "competencia_ano": "2026",
                "competencia_mes": "abc",
            },
        )
    assert response.status_code == 422
    assert "competência" in response.text.lower()


def test_marcar_com_mes_fora_do_intervalo_1_12_e_bloqueado_com_422():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        competencia_id = _criar_competencia(client, contrato_id, "2026-05")
        _importar_cpf_fora_da_lista(client, contrato_id, competencia_id)

        response = client.post(
            _url_conhecidos(contrato_id),
            data={
                "cpf": "22233344455",
                "nome": "Fora Da Lista",
                "motivo": "Motivo válido.",
                "competencia_ano": "2026",
                "competencia_mes": "13",
            },
        )
    assert response.status_code == 422
    assert "competência" in response.text.lower()


def test_marcar_com_cpf_vazio_e_bloqueado_com_422():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        competencia_id = _criar_competencia(client, contrato_id, "2026-05")
        _importar_cpf_fora_da_lista(client, contrato_id, competencia_id)

        response = client.post(
            _url_conhecidos(contrato_id),
            data={
                "cpf": "",
                "nome": "Fora Da Lista",
                "motivo": "Motivo válido.",
                "competencia_ano": "2026",
                "competencia_mes": "5",
            },
        )
    assert response.status_code == 422
    assert "cpf" in response.text.lower()


def test_marcar_com_cpf_invalido_e_bloqueado_com_422():
    with TestClient(app) as client:
        contrato_id = _criar_contrato(client)
        competencia_id = _criar_competencia(client, contrato_id, "2026-05")
        _importar_cpf_fora_da_lista(client, contrato_id, competencia_id)

        response = client.post(
            _url_conhecidos(contrato_id),
            data={
                "cpf": "abc",
                "nome": "Fora Da Lista",
                "motivo": "Motivo válido.",
                "competencia_ano": "2026",
                "competencia_mes": "5",
            },
        )
    assert response.status_code == 422
    assert "cpf" in response.text.lower()
