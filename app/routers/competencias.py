from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models_fiscalizacao import Competencia
from app.routers.contratos import buscar_contrato_ou_404
from app.templating import templates

router = APIRouter(prefix="/contratos", tags=["competencias"])

NOMES_MES = [
    "",
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]


def buscar_competencia_ou_404(contrato_id: int, competencia_id: int, db: Session) -> Competencia:
    competencia = db.get(Competencia, competencia_id)
    if competencia is None or competencia.contrato_id != contrato_id:
        raise HTTPException(status_code=404, detail="Competência não encontrada.")
    return competencia


def _parse_mes_ano(mes_ano: str) -> tuple[int, int] | None:
    try:
        ano_str, mes_str = mes_ano.split("-")
        ano, mes = int(ano_str), int(mes_str)
    except (ValueError, AttributeError):
        return None
    if not (1 <= mes <= 12):
        return None
    return ano, mes


@router.get("/{contrato_id}/competencias")
def listar_competencias(contrato_id: int, request: Request, db: Session = Depends(get_db)):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    competencias = (
        db.query(Competencia)
        .filter_by(contrato_id=contrato_id)
        .order_by(Competencia.ano.desc(), Competencia.mes.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "competencias/lista.html",
        {"contrato": contrato, "competencias": competencias, "erro": None},
    )


@router.get("/{contrato_id}/competencias/nova")
def nova_competencia_form(contrato_id: int, request: Request, db: Session = Depends(get_db)):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    return templates.TemplateResponse(
        request, "competencias/form.html", {"contrato": contrato, "erro": None}
    )


@router.post("/{contrato_id}/competencias")
def criar_competencia(
    contrato_id: int,
    request: Request,
    mes_ano: str = Form(""),
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)

    ano_mes = _parse_mes_ano(mes_ano)
    if ano_mes is None:
        return templates.TemplateResponse(
            request,
            "competencias/form.html",
            {"contrato": contrato, "erro": "Informe um mês/ano válido."},
            status_code=422,
        )
    ano, mes = ano_mes

    ja_existe = (
        db.query(Competencia)
        .filter_by(contrato_id=contrato_id, ano=ano, mes=mes)
        .first()
    )
    if ja_existe is not None:
        return templates.TemplateResponse(
            request,
            "competencias/form.html",
            {
                "contrato": contrato,
                "erro": f"Já existe uma competência cadastrada para {mes:02d}/{ano} neste contrato.",
            },
            status_code=422,
        )

    competencia = Competencia(contrato_id=contrato_id, ano=ano, mes=mes)
    db.add(competencia)
    db.commit()
    return RedirectResponse(url=f"/contratos/{contrato_id}/competencias", status_code=303)


@router.get("/{contrato_id}/competencias/{competencia_id}")
def detalhe_competencia(
    contrato_id: int, competencia_id: int, request: Request, db: Session = Depends(get_db)
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    competencia = buscar_competencia_ou_404(contrato_id, competencia_id, db)
    return templates.TemplateResponse(
        request,
        "competencias/detalhe.html",
        {"contrato": contrato, "competencia": competencia},
    )
