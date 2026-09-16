from datetime import date
from decimal import Decimal

from app.batimento import (
    calcular_fgts_esperado,
    calcular_inss_esperado,
    terceirizado_esta_ativo_na_competencia,
)

FAIXAS_2026 = [
    (Decimal("1621.00"), Decimal("0.0750")),
    (Decimal("2902.84"), Decimal("0.0900")),
    (Decimal("4354.27"), Decimal("0.1200")),
    (Decimal("8475.55"), Decimal("0.1400")),
]


def test_fgts_esperado_e_8_por_cento_da_base():
    assert calcular_fgts_esperado(Decimal("1000.00"), Decimal("0.08")) == Decimal("80.00")


def test_fgts_esperado_com_percentual_customizado():
    assert calcular_fgts_esperado(Decimal("1000.00"), Decimal("0.10")) == Decimal("100.00")


def test_inss_esperado_dentro_da_primeira_faixa():
    # base menor que 1621.00: só a primeira alíquota (7,5%) se aplica
    assert calcular_inss_esperado(Decimal("1000.00"), FAIXAS_2026) == Decimal("75.00")


def test_inss_esperado_e_progressivo_por_faixa():
    # base 3000.00 cruza 3 faixas: 1621*7,5% + (2902.84-1621)*9% + (3000-2902.84)*12%
    esperado = (
        Decimal("1621.00") * Decimal("0.075")
        + Decimal("1281.84") * Decimal("0.09")
        + Decimal("97.16") * Decimal("0.12")
    ).quantize(Decimal("0.01"))
    assert calcular_inss_esperado(Decimal("3000.00"), FAIXAS_2026) == esperado


def test_ce07_inss_esperado_limita_base_ao_teto():
    resultado_no_teto = calcular_inss_esperado(Decimal("8475.55"), FAIXAS_2026)
    resultado_acima_do_teto = calcular_inss_esperado(Decimal("50000.00"), FAIXAS_2026)
    assert resultado_acima_do_teto == resultado_no_teto


def test_rn06_terceirizado_sem_desligamento_esta_ativo():
    assert terceirizado_esta_ativo_na_competencia(None, ano=2026, mes=5) is True


def test_rn06_desligado_antes_da_competencia_esta_inativo():
    assert (
        terceirizado_esta_ativo_na_competencia(date(2026, 4, 15), ano=2026, mes=5) is False
    )


def test_rn06_desligado_dentro_do_mes_da_competencia_esta_ativo():
    assert (
        terceirizado_esta_ativo_na_competencia(date(2026, 5, 20), ano=2026, mes=5) is True
    )
