from datetime import date, time

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models_fiscalizacao import Reuniao
from app.routers.contratos import buscar_contrato_ou_404
from app.templating import templates

router = APIRouter(prefix="/contratos", tags=["reunioes"])

CAMPOS_OBRIGATORIOS = {
    "data": "Data",
    "participantes": "Participantes",
    "resumo": "Resumo",
}


def buscar_reuniao_ou_404(contrato_id: int, reuniao_id: int, db: Session) -> Reuniao:
    reuniao = db.query(Reuniao).filter_by(id=reuniao_id, contrato_id=contrato_id).first()
    if reuniao is None:
        raise HTTPException(status_code=404, detail="Reunião não encontrada")
    return reuniao


def validar_reuniao(dados: dict) -> tuple[list[str], dict | None]:
    erros: list[str] = []
    valores = {campo: (dados.get(campo) or "").strip() for campo in CAMPOS_OBRIGATORIOS}
    hora = (dados.get("hora") or "").strip()
    local = (dados.get("local") or "").strip()

    for campo, rotulo in CAMPOS_OBRIGATORIOS.items():
        if not valores[campo]:
            erros.append(f"{rotulo} é obrigatório.")

    data_reuniao = None
    if valores["data"]:
        try:
            data_reuniao = date.fromisoformat(valores["data"])
        except ValueError:
            erros.append("Data inválida.")

    if hora:
        try:
            time.fromisoformat(hora)
        except ValueError:
            erros.append("Hora inválida.")

    if erros:
        return erros, None

    return [], {
        "data": data_reuniao,
        "hora": hora or None,
        "local": local or None,
        "participantes": valores["participantes"],
        "resumo": valores["resumo"],
    }


@router.get("/{contrato_id}/reunioes")
def listar_reunioes(contrato_id: int, request: Request, db: Session = Depends(get_db)):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    reunioes = (
        db.query(Reuniao).filter_by(contrato_id=contrato_id).order_by(Reuniao.data.desc()).all()
    )
    return templates.TemplateResponse(
        request, "reunioes/lista.html", {"contrato": contrato, "reunioes": reunioes, "erros": []}
    )


@router.get("/{contrato_id}/reunioes/nova")
def nova_reuniao_form(contrato_id: int, request: Request, db: Session = Depends(get_db)):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    return templates.TemplateResponse(
        request,
        "reunioes/form.html",
        {"contrato": contrato, "erros": [], "valores": {}, "reuniao": None},
    )


@router.post("/{contrato_id}/reunioes")
def criar_reuniao(
    contrato_id: int,
    request: Request,
    data: str = Form(""),
    hora: str = Form(""),
    local: str = Form(""),
    participantes: str = Form(""),
    resumo: str = Form(""),
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)

    dados = {"data": data, "hora": hora, "local": local, "participantes": participantes, "resumo": resumo}
    erros, dados_validos = validar_reuniao(dados)
    if erros:
        return templates.TemplateResponse(
            request,
            "reunioes/form.html",
            {"contrato": contrato, "erros": erros, "valores": dados, "reuniao": None},
            status_code=422,
        )

    reuniao = Reuniao(contrato_id=contrato_id, **dados_validos)
    db.add(reuniao)
    db.commit()
    return RedirectResponse(url=f"/contratos/{contrato_id}/reunioes", status_code=303)


@router.get("/{contrato_id}/reunioes/{reuniao_id}/editar")
def editar_reuniao_form(
    contrato_id: int, reuniao_id: int, request: Request, db: Session = Depends(get_db)
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    reuniao = buscar_reuniao_ou_404(contrato_id, reuniao_id, db)
    valores = {
        "data": reuniao.data.isoformat(),
        "hora": reuniao.hora or "",
        "local": reuniao.local or "",
        "participantes": reuniao.participantes,
        "resumo": reuniao.resumo,
    }
    return templates.TemplateResponse(
        request,
        "reunioes/form.html",
        {"contrato": contrato, "erros": [], "valores": valores, "reuniao": reuniao},
    )


@router.post("/{contrato_id}/reunioes/{reuniao_id}/editar")
def editar_reuniao(
    contrato_id: int,
    reuniao_id: int,
    request: Request,
    data: str = Form(""),
    hora: str = Form(""),
    local: str = Form(""),
    participantes: str = Form(""),
    resumo: str = Form(""),
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    reuniao = buscar_reuniao_ou_404(contrato_id, reuniao_id, db)

    dados = {"data": data, "hora": hora, "local": local, "participantes": participantes, "resumo": resumo}
    erros, dados_validos = validar_reuniao(dados)
    if erros:
        return templates.TemplateResponse(
            request,
            "reunioes/form.html",
            {"contrato": contrato, "erros": erros, "valores": dados, "reuniao": reuniao},
            status_code=422,
        )

    for campo, valor in dados_validos.items():
        setattr(reuniao, campo, valor)
    db.commit()
    return RedirectResponse(url=f"/contratos/{contrato_id}/reunioes", status_code=303)
