from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models_fiscalizacao import CpfConhecido
from app.routers.contratos import buscar_contrato_ou_404
from app.templating import templates
from app.terceirizados import normalizar_cpf

router = APIRouter(prefix="/contratos", tags=["cpfs-conhecidos"])


def buscar_cpf_conhecido_ou_404(contrato_id: int, conhecido_id: int, db: Session) -> CpfConhecido:
    conhecido = db.get(CpfConhecido, conhecido_id)
    if conhecido is None or conhecido.contrato_id != contrato_id:
        raise HTTPException(status_code=404, detail="CPF conhecido não encontrado.")
    return conhecido


@router.get("/{contrato_id}/cpfs-conhecidos")
def listar_cpfs_conhecidos(contrato_id: int, request: Request, db: Session = Depends(get_db)):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    conhecidos = (
        db.query(CpfConhecido).filter_by(contrato_id=contrato_id).order_by(CpfConhecido.nome).all()
    )
    return templates.TemplateResponse(
        request, "cpfs_conhecidos/lista.html", {"contrato": contrato, "conhecidos": conhecidos}
    )


@router.post("/{contrato_id}/cpfs-conhecidos")
def marcar_cpf_conhecido(
    contrato_id: int,
    request: Request,
    cpf: str = Form(""),
    nome: str = Form(""),
    motivo: str = Form(""),
    competencia_ano: str = Form(""),
    competencia_mes: str = Form(""),
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)

    def _erro(mensagem: str):
        return templates.TemplateResponse(
            request,
            "cpfs_conhecidos/lista.html",
            {
                "contrato": contrato,
                "conhecidos": db.query(CpfConhecido).filter_by(contrato_id=contrato_id).all(),
                "erro": mensagem,
            },
            status_code=422,
        )

    motivo = motivo.strip()
    if not motivo:
        return _erro("O motivo é obrigatório para marcar um CPF como conhecido.")

    cpf_normalizado = normalizar_cpf(cpf)
    if len(cpf_normalizado) != 11:
        return _erro("CPF inválido: deve ter 11 dígitos.")

    try:
        ano = int(competencia_ano)
        mes = int(competencia_mes)
    except ValueError:
        return _erro("Informe uma competência de referência válida.")
    if not (1 <= mes <= 12):
        return _erro("Informe uma competência de referência válida.")

    existente = (
        db.query(CpfConhecido).filter_by(contrato_id=contrato_id, cpf=cpf_normalizado).first()
    )
    if existente is None:
        existente = CpfConhecido(contrato_id=contrato_id, cpf=cpf_normalizado)
        db.add(existente)
    existente.nome = nome.strip()
    existente.motivo = motivo
    existente.competencia_referencia_ano = ano
    existente.competencia_referencia_mes = mes
    db.commit()

    return RedirectResponse(url=f"/contratos/{contrato_id}/cpfs-conhecidos", status_code=303)


@router.post("/{contrato_id}/cpfs-conhecidos/{conhecido_id}/remover")
def remover_cpf_conhecido(contrato_id: int, conhecido_id: int, db: Session = Depends(get_db)):
    buscar_contrato_ou_404(contrato_id, db)
    conhecido = buscar_cpf_conhecido_ou_404(contrato_id, conhecido_id, db)
    db.delete(conhecido)
    db.commit()
    return RedirectResponse(url=f"/contratos/{contrato_id}/cpfs-conhecidos", status_code=303)
