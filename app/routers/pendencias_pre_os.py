from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models_fiscalizacao import PendenciaPreOS
from app.pendencias_pre_os import garantir_itens_padrao
from app.routers.contratos import buscar_contrato_ou_404
from app.templating import templates

router = APIRouter(prefix="/contratos", tags=["pendencias-pre-os"])


def buscar_pendencia_ou_404(contrato_id: int, pendencia_id: int, db: Session) -> PendenciaPreOS:
    pendencia = db.get(PendenciaPreOS, pendencia_id)
    if pendencia is None or pendencia.contrato_id != contrato_id:
        raise HTTPException(status_code=404, detail="Item de pendência pré-OS não encontrado.")
    return pendencia


@router.get("/{contrato_id}/pendencias-pre-os")
def listar_pendencias_pre_os(contrato_id: int, request: Request, db: Session = Depends(get_db)):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    garantir_itens_padrao(contrato_id, db)
    itens = db.query(PendenciaPreOS).filter_by(contrato_id=contrato_id).order_by(PendenciaPreOS.id).all()
    return templates.TemplateResponse(
        request, "pendencias_pre_os/lista.html", {"contrato": contrato, "itens": itens}
    )


@router.post("/{contrato_id}/pendencias-pre-os/{pendencia_id}/alternar")
def alternar_pendencia_pre_os(
    contrato_id: int, pendencia_id: int, db: Session = Depends(get_db)
):
    buscar_contrato_ou_404(contrato_id, db)
    pendencia = buscar_pendencia_ou_404(contrato_id, pendencia_id, db)
    pendencia.status = "ok" if pendencia.status == "pendente" else "pendente"
    db.commit()
    return RedirectResponse(url=f"/contratos/{contrato_id}/pendencias-pre-os", status_code=303)
