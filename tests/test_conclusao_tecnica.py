from dataclasses import dataclass

from app.conclusao_tecnica import (
    CONCLUSAO_IRREGULAR,
    CONCLUSAO_REGULAR,
    CONCLUSAO_REGULAR_COM_RESSALVAS,
    sugerir_conclusao_tecnica,
)


@dataclass
class OcorrenciaFake:
    gravidade: str


def test_regular_quando_nao_ha_ocorrencias_recebimento_aceito_e_pendencias_ok():
    resultado = sugerir_conclusao_tecnica(
        ocorrencias_do_mes=[],
        decisao_recebimento_provisorio="aceito",
        pendencias_pre_os_ok=True,
    )
    assert resultado == CONCLUSAO_REGULAR


def test_regular_quando_recebimento_ainda_nao_registrado():
    resultado = sugerir_conclusao_tecnica(
        ocorrencias_do_mes=[], decisao_recebimento_provisorio=None, pendencias_pre_os_ok=True
    )
    assert resultado == CONCLUSAO_REGULAR


def test_irregular_quando_ha_ocorrencia_grave_no_mes():
    resultado = sugerir_conclusao_tecnica(
        ocorrencias_do_mes=[OcorrenciaFake(gravidade="grave")],
        decisao_recebimento_provisorio="aceito",
        pendencias_pre_os_ok=True,
    )
    assert resultado == CONCLUSAO_IRREGULAR


def test_irregular_quando_recebimento_provisorio_recusado():
    resultado = sugerir_conclusao_tecnica(
        ocorrencias_do_mes=[], decisao_recebimento_provisorio="recusado", pendencias_pre_os_ok=True
    )
    assert resultado == CONCLUSAO_IRREGULAR


def test_irregular_prevalece_mesmo_com_pendencias_ok_e_sem_outras_ressalvas():
    resultado = sugerir_conclusao_tecnica(
        ocorrencias_do_mes=[OcorrenciaFake(gravidade="grave")],
        decisao_recebimento_provisorio="aceito",
        pendencias_pre_os_ok=True,
    )
    assert resultado == CONCLUSAO_IRREGULAR


def test_regular_com_ressalvas_quando_ha_ocorrencia_leve_no_mes():
    resultado = sugerir_conclusao_tecnica(
        ocorrencias_do_mes=[OcorrenciaFake(gravidade="leve")],
        decisao_recebimento_provisorio="aceito",
        pendencias_pre_os_ok=True,
    )
    assert resultado == CONCLUSAO_REGULAR_COM_RESSALVAS


def test_regular_com_ressalvas_quando_ha_ocorrencia_media_no_mes():
    resultado = sugerir_conclusao_tecnica(
        ocorrencias_do_mes=[OcorrenciaFake(gravidade="media")],
        decisao_recebimento_provisorio="aceito",
        pendencias_pre_os_ok=True,
    )
    assert resultado == CONCLUSAO_REGULAR_COM_RESSALVAS


def test_regular_com_ressalvas_quando_pendencia_pre_os_ainda_pendente():
    resultado = sugerir_conclusao_tecnica(
        ocorrencias_do_mes=[], decisao_recebimento_provisorio="aceito", pendencias_pre_os_ok=False
    )
    assert resultado == CONCLUSAO_REGULAR_COM_RESSALVAS


def test_regular_com_ressalvas_quando_recebimento_aceito_com_ressalva():
    resultado = sugerir_conclusao_tecnica(
        ocorrencias_do_mes=[],
        decisao_recebimento_provisorio="aceito_com_ressalva",
        pendencias_pre_os_ok=True,
    )
    assert resultado == CONCLUSAO_REGULAR_COM_RESSALVAS
