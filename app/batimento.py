from datetime import date
from decimal import ROUND_HALF_UP, Decimal


def calcular_fgts_esperado(base_fgts: Decimal, percentual_fgts: Decimal) -> Decimal:
    return (base_fgts * percentual_fgts).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calcular_inss_esperado(base_inss: Decimal, faixas: list[tuple[Decimal, Decimal]]) -> Decimal:
    teto = faixas[-1][0]
    base = min(base_inss, teto)
    total = Decimal("0.00")
    limite_anterior = Decimal("0.00")
    for limite, aliquota in faixas:
        if base <= limite_anterior:
            break
        parcela = min(base, limite) - limite_anterior
        total += parcela * aliquota
        limite_anterior = limite
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def terceirizado_esta_ativo_na_competencia(data_desligamento: date | None, ano: int, mes: int) -> bool:
    if data_desligamento is None:
        return True
    primeiro_dia_competencia = date(ano, mes, 1)
    return data_desligamento >= primeiro_dia_competencia
