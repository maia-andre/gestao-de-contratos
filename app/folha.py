import csv
import io
from decimal import Decimal, InvalidOperation

from app.terceirizados import normalizar_cpf

CAMPOS_DECIMAIS = [
    "salario_base",
    "total_vencimentos",
    "base_inss",
    "base_fgts",
    "inss_descontado",
    "fgts_depositado",
    "liquido",
]


def _parse_linha_folha(linha: dict) -> dict:
    cpf = normalizar_cpf(linha.get("cpf", ""))
    if len(cpf) != 11:
        raise ValueError("CPF inválido (deve ter 11 dígitos)")

    nome = (linha.get("nome") or "").strip()
    if not nome:
        raise ValueError("nome ausente")

    cargo = (linha.get("cargo") or "").strip()
    if not cargo:
        raise ValueError("cargo ausente")

    valores_decimais = {}
    for campo in CAMPOS_DECIMAIS:
        bruto = (linha.get(campo) or "").strip()
        try:
            valores_decimais[campo] = Decimal(bruto)
        except InvalidOperation:
            raise ValueError(f"{campo} inválido")

    return {"cpf": cpf, "nome": nome, "cargo": cargo, **valores_decimais}


def parsear_csv_folha(conteudo: str) -> tuple[list[dict], list[str]]:
    leitor = csv.DictReader(io.StringIO(conteudo), delimiter=";")
    validos: list[dict] = []
    erros: list[str] = []
    cpfs_vistos: set[str] = set()

    for indice, linha in enumerate(leitor, start=2):
        linha_normalizada = {(chave or "").strip().lower(): valor for chave, valor in linha.items()}
        try:
            dados = _parse_linha_folha(linha_normalizada)
        except ValueError as motivo:
            erros.append(f"Linha {indice}: {motivo}")
            continue

        if dados["cpf"] in cpfs_vistos:
            erros.append(f"Linha {indice}: CPF duplicado")
            continue

        cpfs_vistos.add(dados["cpf"])
        validos.append(dados)

    return validos, erros
