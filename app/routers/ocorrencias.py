from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models_fiscalizacao import Ocorrencia
from app.routers.contratos import buscar_contrato_ou_404
from app.templating import templates

router = APIRouter(prefix="/contratos", tags=["ocorrencias"])

GRAVIDADES_VALIDAS = {
    "leve": "Leve",
    "media": "Média",
    "grave": "Grave",
}

CAMPOS_OBRIGATORIOS = {
    "data": "Data",
    "descricao": "Descrição",
    "gravidade": "Gravidade",
}


def validar_ocorrencia(dados: dict) -> tuple[list[str], dict | None]:
    erros: list[str] = []
    valores = {campo: (dados.get(campo) or "").strip() for campo in CAMPOS_OBRIGATORIOS}

    for campo, rotulo in CAMPOS_OBRIGATORIOS.items():
        if not valores[campo]:
            erros.append(f"{rotulo} é obrigatório.")

    data_ocorrencia = None
    if valores["data"]:
        try:
            data_ocorrencia = date.fromisoformat(valores["data"])
        except ValueError:
            erros.append("Data inválida.")

    if valores["gravidade"] and valores["gravidade"] not in GRAVIDADES_VALIDAS:
        erros.append("Gravidade inválida: use leve, média ou grave.")

    if erros:
        return erros, None

    return [], {
        "data": data_ocorrencia,
        "descricao": valores["descricao"],
        "gravidade": valores["gravidade"],
    }


@router.get("/{contrato_id}/ocorrencias")
def listar_ocorrencias(contrato_id: int, request: Request, db: Session = Depends(get_db)):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    ocorrencias = (
        db.query(Ocorrencia).filter_by(contrato_id=contrato_id).order_by(Ocorrencia.data.desc()).all()
    )
    return templates.TemplateResponse(
        request,
        "ocorrencias/lista.html",
        {"contrato": contrato, "ocorrencias": ocorrencias, "rotulos_gravidade": GRAVIDADES_VALIDAS},
    )


@router.get("/{contrato_id}/ocorrencias/nova")
def nova_ocorrencia_form(contrato_id: int, request: Request, db: Session = Depends(get_db)):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    return templates.TemplateResponse(
        request,
        "ocorrencias/form.html",
        {"contrato": contrato, "erros": [], "valores": {}, "gravidades": GRAVIDADES_VALIDAS},
    )


@router.post("/{contrato_id}/ocorrencias")
def criar_ocorrencia(
    contrato_id: int,
    request: Request,
    data: str = Form(""),
    descricao: str = Form(""),
    gravidade: str = Form(""),
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)

    dados = {"data": data, "descricao": descricao, "gravidade": gravidade}
    erros, dados_validos = validar_ocorrencia(dados)
    if erros:
        return templates.TemplateResponse(
            request,
            "ocorrencias/form.html",
            {"contrato": contrato, "erros": erros, "valores": dados, "gravidades": GRAVIDADES_VALIDAS},
            status_code=422,
        )

    ocorrencia = Ocorrencia(contrato_id=contrato_id, **dados_validos)
    db.add(ocorrencia)
    db.commit()
    return RedirectResponse(url=f"/contratos/{contrato_id}/ocorrencias", status_code=303)
