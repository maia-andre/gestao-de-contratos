from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.checklist_documental import calcular_validade_certidao, garantir_itens_padrao
from app.database import get_db
from app.models_fiscalizacao import ItemChecklistDocumental
from app.routers.competencias import buscar_competencia_ou_404
from app.routers.contratos import buscar_contrato_ou_404
from app.templating import templates

router = APIRouter(prefix="/contratos", tags=["checklist-documental"])


def buscar_item_checklist_ou_404(
    competencia_id: int, item_id: int, db: Session
) -> ItemChecklistDocumental:
    item = db.get(ItemChecklistDocumental, item_id)
    if item is None or item.competencia_id != competencia_id:
        raise HTTPException(status_code=404, detail="Item do checklist documental não encontrado.")
    return item


def _montar_linhas(competencia_id: int, db: Session) -> list[dict]:
    itens = (
        db.query(ItemChecklistDocumental)
        .filter_by(competencia_id=competencia_id)
        .order_by(ItemChecklistDocumental.id)
        .all()
    )
    hoje = date.today()
    return [
        {"item": item, "validade": calcular_validade_certidao(item.chave, item.data_referencia, hoje)}
        for item in itens
    ]


@router.get("/{contrato_id}/competencias/{competencia_id}/checklist")
def listar_checklist_documental(
    contrato_id: int, competencia_id: int, request: Request, db: Session = Depends(get_db)
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    competencia = buscar_competencia_ou_404(contrato_id, competencia_id, db)
    garantir_itens_padrao(competencia_id, db)
    return templates.TemplateResponse(
        request,
        "checklist_documental/lista.html",
        {
            "contrato": contrato,
            "competencia": competencia,
            "linhas": _montar_linhas(competencia_id, db),
        },
    )


@router.post("/{contrato_id}/competencias/{competencia_id}/checklist/{item_id}/alternar")
def alternar_item_checklist(
    contrato_id: int, competencia_id: int, item_id: int, db: Session = Depends(get_db)
):
    buscar_contrato_ou_404(contrato_id, db)
    buscar_competencia_ou_404(contrato_id, competencia_id, db)
    item = buscar_item_checklist_ou_404(competencia_id, item_id, db)
    item.status = "ok" if item.status == "pendente" else "pendente"
    db.commit()
    return RedirectResponse(
        url=f"/contratos/{contrato_id}/competencias/{competencia_id}/checklist", status_code=303
    )


@router.post("/{contrato_id}/competencias/{competencia_id}/checklist/{item_id}/data-referencia")
def definir_data_referencia(
    contrato_id: int,
    competencia_id: int,
    item_id: int,
    request: Request,
    data_referencia: str = Form(""),
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    competencia = buscar_competencia_ou_404(contrato_id, competencia_id, db)
    item = buscar_item_checklist_ou_404(competencia_id, item_id, db)

    data_referencia = data_referencia.strip()
    if not data_referencia:
        item.data_referencia = None
    else:
        try:
            item.data_referencia = date.fromisoformat(data_referencia)
        except ValueError:
            db.rollback()
            return templates.TemplateResponse(
                request,
                "checklist_documental/lista.html",
                {
                    "contrato": contrato,
                    "competencia": competencia,
                    "linhas": _montar_linhas(competencia_id, db),
                    "erro": "Data de referência inválida.",
                },
                status_code=422,
            )

    db.commit()
    return RedirectResponse(
        url=f"/contratos/{contrato_id}/competencias/{competencia_id}/checklist", status_code=303
    )
