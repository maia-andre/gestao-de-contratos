from datetime import date

LIMIAR_DIAS_ATENCAO = 90
STATUS_DENTRO_DO_PRAZO = "Dentro do prazo"
STATUS_ATENCAO = "Atenção"
STATUS_VENCIDO = "Vencido"


def dias_restantes(vigencia_fim: date, hoje: date) -> int:
    return (vigencia_fim - hoje).days


def status_prorrogacao(dias: int) -> str:
    if dias < 0:
        return STATUS_VENCIDO
    if dias <= LIMIAR_DIAS_ATENCAO:
        return STATUS_ATENCAO
    return STATUS_DENTRO_DO_PRAZO
