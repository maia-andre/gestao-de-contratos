from dataclasses import dataclass
from datetime import date

from app.checklist_documental import checklist_completo_e_valido
from app.conclusoes import (
    CONCLUSAO_IRREGULAR,
    CONCLUSAO_REGULAR,
    CONCLUSAO_REGULAR_COM_RESSALVAS,
    sugerir_conclusao_administrativa,
)
from app.divergencias import Divergencia


@dataclass
class ItemChecklistFake:
    chave: str
    status: str
    data_referencia: date | None = None


def _item_ok(chave: str, data_referencia: date | None = None) -> ItemChecklistFake:
    return ItemChecklistFake(chave=chave, status="ok", data_referencia=data_referencia)


ITENS_TODOS_OK = [
    _item_ok("cndt"),
    _item_ok("crf_fgts"),
    _item_ok("certidao_rfb_pgfn"),
    _item_ok("gfd_paga"),
    _item_ok("darf_pago"),
    _item_ok("holerites_mes"),
    _item_ok("comprovantes_salario"),
]


def test_checklist_completo_e_valido_true_quando_tudo_ok_sem_data_de_referencia():
    assert checklist_completo_e_valido(ITENS_TODOS_OK, date(2026, 6, 1)) is True


def test_checklist_completo_e_valido_false_quando_algum_item_pendente():
    itens = ITENS_TODOS_OK[:-1] + [ItemChecklistFake(chave="comprovantes_salario", status="pendente")]
    assert checklist_completo_e_valido(itens, date(2026, 6, 1)) is False


def test_checklist_completo_e_valido_false_quando_certidao_vencida():
    itens = [
        _item_ok("cndt", data_referencia=date(2026, 1, 1)),
        _item_ok("crf_fgts"),
    ]
    assert checklist_completo_e_valido(itens, hoje=date(2026, 8, 1)) is False


def test_checklist_completo_e_valido_true_quando_certidao_dentro_do_prazo():
    itens = [
        _item_ok("cndt", data_referencia=date(2026, 7, 1)),
        _item_ok("crf_fgts", data_referencia=date(2026, 7, 20)),
    ]
    assert checklist_completo_e_valido(itens, hoje=date(2026, 8, 1)) is True


def test_sugerir_conclusao_regular_quando_sem_divergencias_e_checklist_ok():
    assert sugerir_conclusao_administrativa([], checklist_ok=True) == CONCLUSAO_REGULAR


def test_sugerir_conclusao_regular_com_ressalvas_quando_checklist_incompleto_sem_divergencias():
    assert sugerir_conclusao_administrativa([], checklist_ok=False) == CONCLUSAO_REGULAR_COM_RESSALVAS


def test_sugerir_conclusao_irregular_quando_ha_divergencia_de_ausencia():
    divergencias = [Divergencia(tipo="ausencia", cpf="1", nome="A", mensagem="")]
    assert sugerir_conclusao_administrativa(divergencias, checklist_ok=True) == CONCLUSAO_IRREGULAR


def test_sugerir_conclusao_irregular_quando_ha_divergencia_de_valor_fgts():
    divergencias = [Divergencia(tipo="valor_fgts", cpf="1", nome="A", mensagem="")]
    assert sugerir_conclusao_administrativa(divergencias, checklist_ok=True) == CONCLUSAO_IRREGULAR


def test_sugerir_conclusao_irregular_quando_ha_divergencia_de_valor_inss():
    divergencias = [Divergencia(tipo="valor_inss", cpf="1", nome="A", mensagem="")]
    assert sugerir_conclusao_administrativa(divergencias, checklist_ok=True) == CONCLUSAO_IRREGULAR


def test_sugerir_conclusao_irregular_mesmo_com_checklist_ok():
    divergencias = [Divergencia(tipo="ausencia", cpf="1", nome="A", mensagem="")]
    assert sugerir_conclusao_administrativa(divergencias, checklist_ok=True) == CONCLUSAO_IRREGULAR


def test_sugerir_conclusao_regular_com_ressalvas_quando_ha_divergencia_fora_da_lista_mestra():
    divergencias = [Divergencia(tipo="fora_da_lista_mestra", cpf="1", nome="A", mensagem="")]
    assert (
        sugerir_conclusao_administrativa(divergencias, checklist_ok=True)
        == CONCLUSAO_REGULAR_COM_RESSALVAS
    )


def test_sugerir_conclusao_regular_com_ressalvas_quando_ha_divergencia_fgts_zerado():
    divergencias = [Divergencia(tipo="fgts_zerado", cpf="1", nome="A", mensagem="")]
    assert (
        sugerir_conclusao_administrativa(divergencias, checklist_ok=True)
        == CONCLUSAO_REGULAR_COM_RESSALVAS
    )


def test_sugerir_conclusao_regular_com_ressalvas_quando_ha_divergencia_inss_zerado():
    divergencias = [Divergencia(tipo="inss_zerado", cpf="1", nome="A", mensagem="")]
    assert (
        sugerir_conclusao_administrativa(divergencias, checklist_ok=True)
        == CONCLUSAO_REGULAR_COM_RESSALVAS
    )
