from dataclasses import dataclass
from decimal import Decimal

from app.batimento import (
    calcular_fgts_esperado,
    calcular_inss_esperado,
    terceirizado_esta_ativo_na_competencia,
)

TOLERANCIA_PADRAO = Decimal("0.01")


@dataclass
class Divergencia:
    tipo: str
    cpf: str
    nome: str
    mensagem: str


def calcular_divergencias(
    itens_folha,
    terceirizados,
    ano: int,
    mes: int,
    faixas_inss,
    percentual_fgts,
    tolerancia: Decimal = TOLERANCIA_PADRAO,
    cpfs_conhecidos: dict[str, tuple[int, int]] | None = None,
) -> list[Divergencia]:
    cpfs_conhecidos = cpfs_conhecidos or {}
    divergencias: list[Divergencia] = []
    itens_por_cpf = {item.cpf: item for item in itens_folha}
    terceirizados_por_cpf = {t.cpf: t for t in terceirizados}

    for terceirizado in terceirizados:
        if not terceirizado_esta_ativo_na_competencia(terceirizado.data_desligamento, ano, mes):
            continue
        if terceirizado.cpf not in itens_por_cpf:
            divergencias.append(
                Divergencia(
                    tipo="ausencia",
                    cpf=terceirizado.cpf,
                    nome=terceirizado.nome,
                    mensagem=(
                        f"{terceirizado.nome} consta na lista mestra e está ativo, mas não "
                        "aparece na folha desta competência."
                    ),
                )
            )

    for item in itens_folha:
        if item.cpf not in terceirizados_por_cpf:
            referencia = cpfs_conhecidos.get(item.cpf)
            if referencia is not None and (ano, mes) >= referencia:
                continue
            divergencias.append(
                Divergencia(
                    tipo="fora_da_lista_mestra",
                    cpf=item.cpf,
                    nome=item.nome,
                    mensagem=f"{item.nome} consta na folha mas não está na lista mestra do contrato.",
                )
            )

    for item in itens_folha:
        fgts_esperado = calcular_fgts_esperado(item.base_fgts, percentual_fgts)
        if item.fgts_depositado == 0 and item.base_fgts > 0:
            divergencias.append(
                Divergencia(
                    tipo="fgts_zerado",
                    cpf=item.cpf,
                    nome=item.nome,
                    mensagem=(
                        f"{item.nome}: FGTS não depositado (base de R$ {item.base_fgts}, "
                        "depositado R$ 0,00)."
                    ),
                )
            )
        elif abs(item.fgts_depositado - fgts_esperado) > tolerancia:
            divergencias.append(
                Divergencia(
                    tipo="valor_fgts",
                    cpf=item.cpf,
                    nome=item.nome,
                    mensagem=(
                        f"{item.nome}: FGTS depositado (R$ {item.fgts_depositado}) difere do "
                        f"esperado (R$ {fgts_esperado})."
                    ),
                )
            )

        inss_esperado = calcular_inss_esperado(item.base_inss, faixas_inss)
        if item.inss_descontado == 0 and item.base_inss > 0:
            divergencias.append(
                Divergencia(
                    tipo="inss_zerado",
                    cpf=item.cpf,
                    nome=item.nome,
                    mensagem=(
                        f"{item.nome}: INSS não descontado (base de R$ {item.base_inss}, "
                        "descontado R$ 0,00)."
                    ),
                )
            )
        elif abs(item.inss_descontado - inss_esperado) > tolerancia:
            divergencias.append(
                Divergencia(
                    tipo="valor_inss",
                    cpf=item.cpf,
                    nome=item.nome,
                    mensagem=(
                        f"{item.nome}: INSS descontado (R$ {item.inss_descontado}) difere do "
                        f"esperado (R$ {inss_esperado})."
                    ),
                )
            )

    return divergencias
