"""Cálculo puro dos alertas antecipados do painel (Fase 3, REQ-14)."""

import calendar
from datetime import date, timedelta

from app.prazos import STATUS_ATENCAO, STATUS_DENTRO_DO_PRAZO, STATUS_VENCIDO


def alerta_certidao(
    data_referencia: date | None,
    validade_dias: int,
    antecedencia_dias: int,
    hoje: date,
) -> tuple[str, str]:
    # RN-04: sem data de referência conta como vencida — não há certidão vigente conhecida.
    if data_referencia is None:
        return STATUS_VENCIDO, "sem registro"
    vencimento = data_referencia + timedelta(days=validade_dias)
    if hoje > vencimento:
        return STATUS_VENCIDO, f"vencida em {vencimento.strftime('%d/%m/%Y')}"
    if (vencimento - hoje).days <= antecedencia_dias:
        return STATUS_ATENCAO, f"vence em {vencimento.strftime('%d/%m/%Y')}"
    return STATUS_DENTRO_DO_PRAZO, f"vence em {vencimento.strftime('%d/%m/%Y')}"


def alerta_notificacao(
    vigencia_fim: date, antecedencia_dias: int, hoje: date
) -> tuple[str, str]:
    # RN-03: ciclo em "aguardando notificação".
    inicio_janela = vigencia_fim - timedelta(days=antecedencia_dias)
    if hoje >= inicio_janela:
        return STATUS_ATENCAO, "Notificação de prorrogação a enviar"
    return (
        STATUS_DENTRO_DO_PRAZO,
        f"Notificação de prorrogação programada para {inicio_janela.strftime('%d/%m/%Y')}",
    )


def alerta_resposta(data_limite: date, hoje: date) -> tuple[str, str]:
    # RN-03: ciclo em "notificação enviada".
    if hoje > data_limite:
        return (
            STATUS_VENCIDO,
            f"Resposta da contratada em atraso desde {data_limite.strftime('%d/%m/%Y')}",
        )
    return (
        STATUS_ATENCAO,
        f"Resposta da contratada até {data_limite.strftime('%d/%m/%Y')}",
    )


def _proximo_mes(ano: int, mes: int) -> tuple[int, int]:
    return (ano + 1, 1) if mes == 12 else (ano, mes + 1)


def _ultimo_dia_do_mes(ano: int, mes: int) -> date:
    return date(ano, mes, calendar.monthrange(ano, mes)[1])


def alertas_gfd_darf(
    vigencia_inicio: date,
    vigencia_fim: date,
    dia_limite: int,
    hoje: date,
    situacao_por_mes: dict[tuple[int, int], bool],
) -> list[dict]:
    """RN-06: um alerta por mês X da vigência com GFD/DARF pendentes.

    `situacao_por_mes[(ano, mes)]` é True quando a competência existe e os itens
    "GFD paga" e "DARF pago" estão ok; mês ausente do dicionário = competência
    não registrada (CE-07), que também é cobrada.
    """
    alertas = []
    ano, mes = vigencia_inicio.year, vigencia_inicio.month
    while _ultimo_dia_do_mes(ano, mes) <= vigencia_fim:
        prox_ano, prox_mes = _proximo_mes(ano, mes)
        if situacao_por_mes.get((ano, mes)) is not True:
            data_atencao = date(prox_ano, prox_mes, 15)
            data_limite = date(prox_ano, prox_mes, dia_limite)
            status = None
            if hoje > data_limite:
                status = STATUS_VENCIDO
            elif hoje >= data_atencao:
                status = STATUS_ATENCAO
            if status is not None:
                registrada = (ano, mes) in situacao_por_mes
                alertas.append(
                    {
                        "ano": ano,
                        "mes": mes,
                        "status": status,
                        "registrada": registrada,
                    }
                )
        ano, mes = prox_ano, prox_mes
    return alertas


def relatorio_final_pendente(vigencia_fim: date, tem_parecer: bool, hoje: date) -> bool:
    # RN-09: cobrado depois que a vigência termina, enquanto não houver parecer.
    return hoje > vigencia_fim and not tem_parecer
