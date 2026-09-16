from datetime import date

from app.prazos import dias_restantes, status_prorrogacao


def test_dias_restantes_calcula_diferenca_em_dias():
    assert dias_restantes(date(2026, 12, 31), date(2026, 1, 1)) == 364


def test_dias_restantes_negativo_quando_vigencia_ja_vencida():
    assert dias_restantes(date(2026, 1, 1), date(2026, 1, 11)) == -10


def test_dias_restantes_zero_no_ultimo_dia():
    assert dias_restantes(date(2026, 1, 1), date(2026, 1, 1)) == 0


def test_status_dentro_do_prazo_quando_mais_de_90_dias():
    assert status_prorrogacao(91) == "Dentro do prazo"


def test_status_atencao_no_limite_exato_de_90_dias():
    assert status_prorrogacao(90) == "Atenção"


def test_status_atencao_quando_vigencia_vence_hoje():
    assert status_prorrogacao(0) == "Atenção"


def test_status_vencido_no_dia_seguinte_ao_fim_da_vigencia():
    assert status_prorrogacao(-1) == "Vencido"


def test_status_vencido_quando_vigencia_ja_passou_ha_mais_tempo():
    assert status_prorrogacao(-5) == "Vencido"
