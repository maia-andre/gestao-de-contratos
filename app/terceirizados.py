import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation

CAMPOS_OBRIGATORIOS = {
    "cpf": "CPF",
    "nome": "Nome",
    "cargo": "Cargo",
    "salario_base": "Salário base",
    "data_admissao": "Data de admissão",
}


def normalizar_cpf(cpf: str) -> str:
    return "".join(c for c in (cpf or "") if c.isdigit())


def validar_terceirizado(dados: dict) -> tuple[list[str], dict | None]:
    erros: list[str] = []
    valores = {campo: (dados.get(campo) or "").strip() for campo in CAMPOS_OBRIGATORIOS}
    data_desligamento_str = (dados.get("data_desligamento") or "").strip()

    for campo, rotulo in CAMPOS_OBRIGATORIOS.items():
        if not valores[campo]:
            erros.append(f"{rotulo} é obrigatório.")

    cpf = normalizar_cpf(valores["cpf"])
    if valores["cpf"] and len(cpf) != 11:
        erros.append("CPF inválido: deve ter 11 dígitos.")

    salario_base = None
    if valores["salario_base"]:
        try:
            salario_base = Decimal(valores["salario_base"])
        except InvalidOperation:
            erros.append("Salário base inválido.")

    data_admissao = None
    if valores["data_admissao"]:
        try:
            data_admissao = date.fromisoformat(valores["data_admissao"])
        except ValueError:
            erros.append("Data de admissão inválida.")

    data_desligamento = None
    if data_desligamento_str:
        try:
            data_desligamento = date.fromisoformat(data_desligamento_str)
        except ValueError:
            erros.append("Data de desligamento inválida.")

    if erros:
        return erros, None

    return [], {
        "cpf": cpf,
        "nome": valores["nome"],
        "cargo": valores["cargo"],
        "salario_base": salario_base,
        "data_admissao": data_admissao,
        "data_desligamento": data_desligamento,
    }


def _parse_linha_csv(linha: dict) -> dict:
    cpf = normalizar_cpf(linha.get("cpf", ""))
    if len(cpf) != 11:
        raise ValueError("CPF inválido (deve ter 11 dígitos)")

    nome = (linha.get("nome") or "").strip()
    if not nome:
        raise ValueError("nome ausente")

    cargo = (linha.get("cargo") or "").strip()
    if not cargo:
        raise ValueError("cargo ausente")

    try:
        salario_base = Decimal((linha.get("salario_base") or "").strip())
    except InvalidOperation:
        raise ValueError("salário base inválido")

    try:
        data_admissao = date.fromisoformat((linha.get("data_admissao") or "").strip())
    except ValueError:
        raise ValueError("data de admissão inválida")

    data_desligamento_str = (linha.get("data_desligamento") or "").strip()
    data_desligamento = None
    if data_desligamento_str:
        try:
            data_desligamento = date.fromisoformat(data_desligamento_str)
        except ValueError:
            raise ValueError("data de desligamento inválida")

    return {
        "cpf": cpf,
        "nome": nome,
        "cargo": cargo,
        "salario_base": salario_base,
        "data_admissao": data_admissao,
        "data_desligamento": data_desligamento,
    }


def parsear_csv_lista_mestra(conteudo: str) -> tuple[list[dict], list[str]]:
    leitor = csv.DictReader(io.StringIO(conteudo), delimiter=";")
    validos: list[dict] = []
    erros: list[str] = []
    cpfs_vistos: set[str] = set()

    for indice, linha in enumerate(leitor, start=2):
        linha_normalizada = {(chave or "").strip().lower(): valor for chave, valor in linha.items()}
        try:
            dados = _parse_linha_csv(linha_normalizada)
        except ValueError as motivo:
            erros.append(f"Linha {indice}: {motivo}")
            continue

        if dados["cpf"] in cpfs_vistos:
            erros.append(f"Linha {indice}: CPF duplicado")
            continue

        cpfs_vistos.add(dados["cpf"])
        validos.append(dados)

    return validos, erros
